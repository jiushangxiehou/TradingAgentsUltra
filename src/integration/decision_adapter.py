"""Decision adapter: upstream final state -> guardrail ``Decision`` (ADR-006).

ADR-006 / REQ-HARD-GUARDRAIL / INV-GUARDRAIL-ZERO-ESCAPE / INV-RATING-VALIDITY

The baseline produces no structured order intent: the Trader's
``position_sizing`` is optional free text and the Portfolio Manager publishes a
rating with no numeric size. The integration therefore takes the execution
intent as an EXPLICIT input at the guarded boundary (policy A+B-strict, ADR-006)
and refuses to pass a rating that comes without one.

Mapping (pinned by the integration memo)
----------------------------------------
rating          The graph's ``run_rating(final_state)``, supplied by the caller
                (the adapter never imports the baseline). ``"REVIEW"`` is passed
                through unchanged so the frozen guardrail rejects it with
                ``ILLEGAL_RATING``.
size_pct        ``ExecutionIntent.size_pct`` verbatim: a FRACTION of portfolio
                value, i.e. ``0.05`` is 5%, compared against the 0.10 limit.
short_amount    ``ExecutionIntent.short_amount`` verbatim: absolute notional in
                the same currency as cash.
available_cash  ``PortfolioContext.cash`` supplied by the caller.
instrument_id   ``final_state["company_of_interest"]`` when it is a ``str``.

Missing input  There is NO default size and NO default short. A missing
               required input becomes ``None`` in the ``Decision`` and the real
               ``evaluate_decision`` returns ``MALFORMED_DECISION``; the gate
               writes ``Hold``. Zero is never substituted for "not supplied",
               because 0.0 would pass the position limit and record a position
               nobody proposed.
Bad input      Intent values pass through untouched -- including bad types, NaN,
               negative numbers. The frozen guardrail, not this adapter, decides
               what is malformed, so there is exactly one definition of a
               malformed decision.

Corroboration (never enforcement)
---------------------------------
The Trader's free-text ``Position Sizing`` is parsed only as a cross-check. The
parse succeeds only when the rendered line holds exactly one ``X%``/``X %``
token; a disagreement larger than ``SIZE_DISAGREEMENT_TOLERANCE`` adds a
deterministic ``SIZE_DISAGREEMENT`` note and NEVER rejects, because the text is
LLM prose and the supplied intent is the authoritative proposal.

Purity  No clock, no I/O, no network, no ``tradingagents`` import: only the
        standard library and the frozen ``src.guardrail`` types.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from src.guardrail import Decision

# Load statuses for one input. A frozen vocabulary, so a report is diffable.
SUPPLIED: Final[str] = "SUPPLIED"
MISSING: Final[str] = "MISSING"
PARSED: Final[str] = "PARSED"
UNPARSEABLE: Final[str] = "UNPARSEABLE"
ABSENT: Final[str] = "ABSENT"

# The Decision fields the gate cannot do without, in a pinned order so the
# missing-fields list is deterministic.
REQUIRED_DECISION_FIELDS: Final[tuple[str, ...]] = ("size_pct", "short_amount", "available_cash")

# A corroboration disagreement larger than half a percentage point is reported.
SIZE_DISAGREEMENT_TOLERANCE: Final[float] = 0.005

NOTE_SIZE_DISAGREEMENT: Final[str] = "SIZE_DISAGREEMENT"

# The Trader's rendered sizing line, as ``render_trader_proposal`` writes it.
_SIZING_LINE_RE = re.compile(r"\*\*Position Sizing\*\*:[ \t]*([^\r\n]*)", re.IGNORECASE)
# One percentage token: digits, an optional decimal part, then the % sign. The
# sign is what makes it a percentage, so "5%" and "5 %" both match, while a bare
# "5" does not. Any text between the sign and the next digit -- "of portfolio",
# "max" -- is irrelevant to the match.
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?|\d+\.)\s*%")


@dataclass(frozen=True, slots=True)
class ExecutionIntent:
    """What the decision proposes to execute: the explicit guardrail input.

    Fields are typed loosely on purpose: a programmatic caller may pass a bad
    value and the frozen guardrail must be the one to reject it as malformed.
    """

    size_pct: object = None
    short_amount: object = None

    def to_dict(self) -> dict[str, object]:
        return {"size_pct": _show(self.size_pct), "short_amount": _show(self.short_amount)}


@dataclass(frozen=True, slots=True)
class AdaptedDecision:
    """The guardrail decision plus how it was assembled. ``report`` keeps the
    adapter's own bookkeeping out of the ``Decision`` (which carries no
    timestamp and no provenance by design)."""

    decision: Decision
    rating: object
    report: dict[str, object]


def _show(value: object) -> dict[str, object]:
    """A JSON-safe description of a possibly-typed-as-anything value."""
    return {"type": type(value).__name__, "repr": repr(value)}


def _is_absent(value: object) -> bool:
    return value is None


def build_decision(
    *,
    final_state: dict,
    rating: object,
    intent: ExecutionIntent | None,
    available_cash: object,
) -> AdaptedDecision:
    """Assemble the guardrail decision from the state, the intent and the cash.

    Never raises: every missing or malformed input is passed to the frozen
    guardrail as-is (``None`` when absent), so the verdict is the guardrail's.

    A ``final_state`` that is not a mapping is treated as ``{}``: the gate still
    has the rating, the intent and the cash to judge the decision by, so a
    wrongly-typed state degrades the *evidence* (no instrument id, no reading of
    the trader's plan) and never the verdict. A gate that can raise is a gate
    that can be skipped.
    """
    state: dict = final_state if isinstance(final_state, dict) else {}

    if not isinstance(intent, ExecutionIntent):
        # A caller-supplied object of another type carries a readable intent
        # only through the fields this class defines; anything else is absent.
        intent = ExecutionIntent(
            size_pct=getattr(intent, "size_pct", None),
            short_amount=getattr(intent, "short_amount", None),
        )

    instrument_id = state.get("company_of_interest")
    if not isinstance(instrument_id, str):
        instrument_id = None

    supplied = {
        "size_pct": not _is_absent(intent.size_pct),
        "short_amount": not _is_absent(intent.short_amount),
        "available_cash": not _is_absent(available_cash),
    }
    values = {
        "size_pct": intent.size_pct,
        "short_amount": intent.short_amount,
        "available_cash": available_cash,
    }
    missing_fields = [name for name in REQUIRED_DECISION_FIELDS if not supplied[name]]

    decision = Decision(
        rating=rating,
        size_pct=values["size_pct"],
        short_amount=values["short_amount"],
        available_cash=values["available_cash"],
        instrument_id=instrument_id,
    )

    parsed = _parse_trader_size(state.get("trader_investment_plan"))
    notes: list[dict[str, object]] = []
    if (
        parsed is not None
        and supplied["size_pct"]
        and isinstance(values["size_pct"], (int, float))
        and not isinstance(values["size_pct"], bool)
        and abs(parsed - values["size_pct"]) > SIZE_DISAGREEMENT_TOLERANCE
    ):
        notes.append(
            {
                "code": NOTE_SIZE_DISAGREEMENT,
                "parsed_size_pct": parsed,
                "supplied_size_pct": _show(values["size_pct"]),
                "tolerance": SIZE_DISAGREEMENT_TOLERANCE,
            }
        )

    report = {
        "inputs": {
            "rating": {"status": SUPPLIED, "value": _show(rating)},
            "size_pct": {
                "status": SUPPLIED if supplied["size_pct"] else MISSING,
                "value": _show(values["size_pct"]),
                "source": "ExecutionIntent",
            },
            "short_amount": {
                "status": SUPPLIED if supplied["short_amount"] else MISSING,
                "value": _show(values["short_amount"]),
                "source": "ExecutionIntent",
            },
            "available_cash": {
                "status": SUPPLIED if supplied["available_cash"] else MISSING,
                "value": _show(values["available_cash"]),
                "source": "PortfolioContext.cash",
            },
            "position_sizing_text": {
                "status": PARSED if parsed is not None
                else (_parse_status(state.get("trader_investment_plan"))),
                "value": parsed,
            },
            "instrument_id": {
                "status": SUPPLIED if instrument_id is not None else ABSENT,
                "value": instrument_id,
            },
        },
        "missing_fields": missing_fields,
        "notes": notes,
        "evidence_only": False,
    }
    return AdaptedDecision(decision=decision, rating=rating, report=report)


def _parse_status(text: object) -> str:
    """``ABSENT`` when the trader wrote nothing, else ``UNPARSEABLE``.

    The line exists but carries no single percentage, or no line at all in a
    plan that was written: both mean "no readable size", and the distinction is
    kept so a reader can tell a missing plan from a plan without a number.
    """
    if not isinstance(text, str) or not text.strip():
        return ABSENT
    return UNPARSEABLE


def _parse_trader_size(text: object) -> float | None:
    """The single size fraction on the Trader's sizing line, else ``None``.

    Succeeds only when the rendering names exactly one percentage. Two
    percentages ("5% now, 10% later") and a percentage plus a range are not one
    number, so the parse declines rather than picks a branch -- a corroboration
    signal we are unsure of must stay silent, not guess.
    """
    if not isinstance(text, str):
        return None
    match = _SIZING_LINE_RE.search(text)
    if match is None:
        return None
    found = _PERCENT_RE.findall(match.group(1))
    if len(found) != 1:
        return None
    value = found[0]
    try:
        return float(value) / 100.0
    except (TypeError, ValueError):  # pragma: no cover - the regex only admits digits
        return None
