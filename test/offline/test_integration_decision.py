"""OFFLINE decision-adapter tests (ADR-006, REQ-HARD-GUARDRAIL).

Requires no API, no network, no clock. The adapter is pure: the real frozen
``evaluate_decision`` is called throughout, so every verdict asserted here is
the guardrail's own.

Invariants under test
---------------------
INV-GUARDRAIL-ZERO-ESCAPE : a decision that oversteps a limit never passes.
INV-RATING-VALIDITY       : a rejection's rating is always a legal tier.

Acceptance conditions A1-A11 are the integration memo's approved policy
(A+B-strict): an explicit execution intent, fail closed when any required input
is absent, and the Trader's free-text sizing as corroboration only.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from src import integration
from src.guardrail import Trigger, evaluate_decision
from src.integration import decision_adapter
from src.integration.decision_adapter import (
    ABSENT,
    MISSING,
    PARSED,
    SUPPLIED,
    UNPARSEABLE,
    AdaptedDecision,
    ExecutionIntent,
    build_decision,
)

pytestmark = pytest.mark.offline

MODULE_PATH = pathlib.Path(decision_adapter.__file__)


# ---------------------------------------------------------------------------
# Deterministic fixtures -- no clock, no randomness, no network
# ---------------------------------------------------------------------------

def make_state(**overrides) -> dict:
    """A finished run's state, in the shape the baseline produces."""
    state = {
        "company_of_interest": "NVDA",
        "trade_date": "2026-11-24",
        "market_report": "Market report.",
        "sentiment_report": "Sentiment report.",
        "news_report": "News report.",
        "fundamentals_report": "Fundamentals report.",
        "investment_plan": "**Recommendation**: Overweight",
        "trader_investment_plan": (
            "**Action**: Buy\n\n**Reasoning**: r\n\n**Entry Price**: 100.0\n\n"
            "**Stop Loss**: 90.0\n\n**Position Sizing**: 5% of portfolio\n\n"
            "FINAL TRANSACTION PROPOSAL: **BUY**"
        ),
        "final_trade_decision": "**Rating**: Buy\n\n**Executive Summary**: buy it.",
        "final_rating": "Buy",
    }
    state.update(overrides)
    return state


_DEFAULT_INTENT = ExecutionIntent(size_pct=0.05, short_amount=0.0)


def adapt(rating: object = "Buy", intent=_DEFAULT_INTENT, cash: object = 10_000.0, state=None) -> AdaptedDecision:
    """Adapt one state. intent=None is a real case (the caller supplied no
    intent), so the default is a sentinel object, never None."""
    return build_decision(
        final_state=state if state is not None else make_state(),
        rating=rating,
        intent=intent,
        available_cash=cash,
    )


def verdict(adapted: AdaptedDecision):
    return evaluate_decision(adapted.decision)


# ---------------------------------------------------------------------------
# A0 -- offline marker
# ---------------------------------------------------------------------------

def test_file_is_marked_offline():
    """Pinned R1: every test in this file is offline-marked."""
    assert decision_adapter.ExecutionIntent
    assert pytestmark == pytest.mark.offline


# ---------------------------------------------------------------------------
# A1 -- rating mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating", ["Buy", "Overweight", "Hold", "Underweight", "Sell"])
def test_legal_rating_is_passed_through_unchanged(rating):
    """REQ-HARD-GUARDRAIL: the graph's rating reaches the guardrail verbatim."""
    adapted = adapt(rating=rating, state=make_state(final_rating=rating))
    assert adapted.decision.rating == rating
    assert verdict(adapted).passed is True


def test_rating_none_becomes_malformed_not_a_legal_tier():
    """INV-RATING-VALIDITY: no rating is not 'Hold' and not a pass."""
    result = verdict(adapt(rating=None))
    assert result.passed is False
    assert result.audit.trigger is Trigger.MALFORMED_DECISION
    assert result.decision.rating == "Hold"


# ---------------------------------------------------------------------------
# A2 -- "REVIEW" is rejected by the frozen guardrail, not by the adapter
# ---------------------------------------------------------------------------

def test_review_rating_is_rejected_as_illegal():
    """INV-RATING-VALIDITY + REQ-HARD-GUARDRAIL: upstream's unreadable-decision
    sentinel is not a legal tier, so an otherwise well-formed intent cannot
    launder it into an executable decision."""
    adapted = adapt(rating="REVIEW")
    assert adapted.decision.rating == "REVIEW"  # passed through, not rewritten
    result = verdict(adapted)
    assert result.passed is False
    assert result.audit.trigger is Trigger.ILLEGAL_RATING
    assert result.audit.observed_value == "REVIEW"


# ---------------------------------------------------------------------------
# A3 -- fail closed when a required input is absent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "intent,cash",
    [
        (ExecutionIntent(size_pct=None, short_amount=0.0), 10_000.0),
        (ExecutionIntent(size_pct=0.05, short_amount=None), 10_000.0),
        (ExecutionIntent(size_pct=0.05, short_amount=0.0), None),
        (ExecutionIntent(), 10_000.0),
        (None, 10_000.0),
        (ExecutionIntent(), None),
    ],
    ids=["no-size", "no-short", "no-cash", "no-intent-fields", "no-intent", "nothing"],
)
def test_missing_required_input_fails_closed_to_hold(intent, cash):
    """ADR-006 policy A+B-strict: no default size, no default short, no
    rating-only pass. The real guardrail calls it malformed and the decision
    that comes back is the legal Hold fallback (INV-RATING-VALIDITY)."""
    adapted = adapt(intent=intent, cash=cash)
    result = verdict(adapted)
    assert result.passed is False
    assert result.audit.trigger is Trigger.MALFORMED_DECISION
    assert result.decision.rating == "Hold"
    assert adapted.report["missing_fields"]


@pytest.mark.parametrize("chosen,field", [("size", "size_pct"), ("short", "short_amount"), ("cash", "available_cash")])
def test_each_required_input_alone_is_enough_to_fail_closed(chosen, field):
    """One missing input is not compensated by the others being present."""
    intent = ExecutionIntent(size_pct=0.05, short_amount=0.0)
    cash = 10_000.0
    if chosen == "size":
        intent = ExecutionIntent(size_pct=None, short_amount=0.0)
    elif chosen == "short":
        intent = ExecutionIntent(size_pct=0.05, short_amount=None)
    else:
        cash = None
    adapted = adapt(intent=intent, cash=cash)
    result = verdict(adapted)
    assert result.passed is False
    assert result.audit.trigger is Trigger.MALFORMED_DECISION
    assert field in adapted.report["missing_fields"]


def test_a_caller_object_of_another_type_carries_no_intent():
    """Pinned: the adapter reads ``size_pct``/``short_amount`` off anything
    duck-typed, and an object without them is a missing intent (fail closed)."""
    class NotAnIntent:
        pass

    adapted = adapt(intent=NotAnIntent())
    assert adapted.report["missing_fields"] == ["size_pct", "short_amount"]
    assert verdict(adapted).passed is False
    """Pinned: 0.0 would pass the position limit and record a position nobody
    proposed, so absence must stay ``None`` all the way to the guardrail."""
    adapted = adapt(intent=ExecutionIntent(size_pct=None, short_amount=0.0))
    assert adapted.decision.size_pct is None
    assert "size_pct" in adapted.report["missing_fields"]
    assert verdict(adapted).passed is False


def test_report_names_every_input_status_and_source():
    """The load report is the audit trail of what the gate was given."""
    report = adapt().report
    assert report["inputs"]["size_pct"]["status"] == SUPPLIED
    assert report["inputs"]["size_pct"]["source"] == "ExecutionIntent"
    assert report["inputs"]["short_amount"]["source"] == "ExecutionIntent"
    assert report["inputs"]["available_cash"]["source"] == "PortfolioContext.cash"
    assert report["inputs"]["position_sizing_text"]["status"] == PARSED
    assert report["missing_fields"] == []
    assert report["notes"] == []


# ---------------------------------------------------------------------------
# A4 -- bad values reach the guardrail untouched and are rejected there
# ---------------------------------------------------------------------------

BAD_INTENT_VALUES = [
    pytest.param("0.05", id="short-string"),
    pytest.param(None, id="none"),
    pytest.param(True, id="bool"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="inf"),
    pytest.param(-0.01, id="negative"),
    pytest.param([0.05], id="list"),
]


@pytest.mark.parametrize("bad", BAD_INTENT_VALUES)
def test_bad_size_fails_closed_through_the_guardrail(bad):
    """Pinned: the ADAPTER never raises and never coerces; the frozen guardrail
    is the single definition of 'malformed', so a bad size is a rejection."""
    adapted = adapt(intent=ExecutionIntent(size_pct=bad, short_amount=0.0))
    result = verdict(adapted)
    assert result.passed is False
    assert result.audit.trigger is Trigger.MALFORMED_DECISION
    assert result.decision.rating == "Hold"


@pytest.mark.parametrize("bad", BAD_INTENT_VALUES)
def test_bad_short_fails_closed_through_the_guardrail(bad):
    adapted = adapt(intent=ExecutionIntent(size_pct=0.05, short_amount=bad))
    assert verdict(adapted).passed is False


@pytest.mark.parametrize("bad", ["10000", True, float("nan"), float("inf"), -1.0])
def test_bad_cash_fails_closed_through_the_guardrail(bad):
    """ADR-006: a non-finite or negative cash is not a book we can check a
    short against, so it is a missing required input, not a large one."""
    assert verdict(adapt(cash=bad)).passed is False


def test_adapter_never_raises_on_any_input_shape():
    """Pinned: a gate that can raise is a gate that can be skipped."""
    for state in ({}, {"company_of_interest": 123}, {"trader_investment_plan": None},
                  {"company_of_interest": None}, {"final_trade_decision": 7},
                  None, [], "text"):
        adapted = adapt(intent=ExecutionIntent(size_pct=0.05, short_amount=0.0), state=state)
        assert isinstance(adapted, AdaptedDecision)
        verdict(adapted)  # must not raise either


# ---------------------------------------------------------------------------
# A5 -- boundaries, checked against the frozen limits (0.10 and cash x 1.0)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "size_pct,must_pass",
    [
        (0.0, True),
        (0.0999, True),
        (0.10, True),        # exactly 10% is ACCEPTED (documented boundary)
        (0.1001, False),     # 10% + epsilon is REJECTED
        (0.11, False),
        (1.0, False),
    ],
    ids=["zero", "under", "at-limit", "just-over", "over", "all-in"],
)
def test_position_boundary(size_pct, must_pass):
    """REQ-HARD-GUARDRAIL (a): a single position above 10% is rejected."""
    adapted = adapt(intent=ExecutionIntent(size_pct=size_pct, short_amount=0.0))
    result = verdict(adapted)
    assert result.passed is must_pass
    if not must_pass:
        assert result.audit.trigger is Trigger.POSITION_LIMIT


@pytest.mark.parametrize(
    "short_amount,cash,must_pass",
    [
        (0.0, 10_000.0, True),
        (10_000.0, 10_000.0, True),      # short == cash is ACCEPTED
        (9_999.99, 10_000.0, True),
        (10_000.01, 10_000.0, False),    # short > cash is REJECTED
        (0.01, 0.0, False),              # any positive short against zero cash
        (0.0, 0.0, True),
    ],
    ids=["flat", "short-equals-cash", "under", "just-over", "zero-cash-positive", "zero-both"],
)
def test_short_boundary(short_amount, cash, must_pass):
    """REQ-HARD-GUARDRAIL (b): short more than available cash is rejected."""
    adapted = adapt(intent=ExecutionIntent(size_pct=0.05, short_amount=short_amount), cash=cash)
    result = verdict(adapted)
    assert result.passed is must_pass
    if not must_pass:
        assert result.audit.trigger is Trigger.SHORT_EXCEEDS_CASH


def test_multi_violation_reports_one_record_by_precedence():
    """REQ-HARD-GUARDRAIL: exactly one audit record, named by the frozen order."""
    adapted = adapt(rating="Buy", intent=ExecutionIntent(size_pct=0.5, short_amount=50_000.0))
    result = verdict(adapted)
    assert result.passed is False
    assert result.audit.trigger is Trigger.POSITION_LIMIT


# ---------------------------------------------------------------------------
# A6 -- the Trader's free text is corroboration only
# ---------------------------------------------------------------------------

def test_corroboration_agrees_and_is_silent():
    """A parsed 5% against a supplied 0.05 is agreement: no note, no verdict."""
    adapted = adapt()  # fixture writes "**Position Sizing**: 5% of portfolio"
    entry = adapted.report["inputs"]["position_sizing_text"]
    assert (entry["status"], entry["value"]) == (PARSED, 0.05)
    assert adapted.report["notes"] == []
    assert verdict(adapted).passed is True


def test_corroboration_disagreement_notes_but_never_rejects():
    """Pinned: prose is not authority. A mismatch is recorded, and the SUPPLIED
    intent still decides the verdict (here: it passes at 0.02)."""
    adapted = adapt(intent=ExecutionIntent(size_pct=0.02, short_amount=0.0))
    notes = adapted.report["notes"]
    assert [note["code"] for note in notes] == ["SIZE_DISAGREEMENT"]
    assert notes[0]["parsed_size_pct"] == 0.05
    assert verdict(adapted).passed is True  # 0.02 is under the limit: prose never rejects


def test_corroboration_disagreement_does_not_rescue_an_oversize():
    """The converse: prose cannot make an oversize intent pass either."""
    adapted = adapt(intent=ExecutionIntent(size_pct=0.5, short_amount=0.0))
    assert [note["code"] for note in adapted.report["notes"]] == ["SIZE_DISAGREEMENT"]
    assert verdict(adapted).passed is False


def test_corroboration_within_tolerance_is_silent():
    adapted = adapt(intent=ExecutionIntent(size_pct=0.055, short_amount=0.0))
    assert adapted.report["notes"] == []  # |0.05 - 0.055| == 0.005, not greater


@pytest.mark.parametrize(
    "sizing,status,value",
    [
        ("**Position Sizing**: 5 % of portfolio", PARSED, 0.05),
        ("**Position Sizing**: 7.5%", PARSED, 0.075),
        ("**Position Sizing**: not provided", UNPARSEABLE, None),
        ("**Position Sizing**: 5% now, 10% later", UNPARSEABLE, None),
        ("**Position Sizing**: $50,000", UNPARSEABLE, None),
        ("**Position Sizing**: 100% cash", PARSED, 1.0),
    ],
    ids=["space", "decimal", "not-provided", "two-values", "currency", "all-cash"],
)
def test_corroboration_parser_states(sizing, status, value):
    """Pinned parser rule: exactly one X%/X % token, else no parsed value."""
    adapted = adapt(state=make_state(trader_investment_plan=f"{sizing}\n\nFINAL"),
                    intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    entry = adapted.report["inputs"]["position_sizing_text"]
    assert entry["status"] == status
    assert entry["value"] == value


def test_corroboration_absent_when_the_plan_is_empty():
    adapted = adapt(state=make_state(trader_investment_plan=""),
                    intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    assert adapted.report["inputs"]["position_sizing_text"]["status"] == ABSENT


def test_corroboration_absent_when_the_state_has_no_plan():
    state = make_state()
    del state["trader_investment_plan"]
    adapted = adapt(state=state, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    assert adapted.report["inputs"]["position_sizing_text"]["status"] == ABSENT


def test_missing_status_is_distinct_from_absent():
    """SUPPLIED/MISSING describe the intent; ABSENT/UNPARSEABLE the prose."""
    adapted = adapt(intent=ExecutionIntent(size_pct=None, short_amount=0.0))
    assert adapted.report["inputs"]["size_pct"]["status"] == MISSING
    assert adapted.report["inputs"]["position_sizing_text"]["status"] == PARSED
    assert MISSING != ABSENT


# ---------------------------------------------------------------------------
# A7 -- instrument identity
# ---------------------------------------------------------------------------

def test_instrument_id_comes_from_the_state():
    assert adapt().decision.instrument_id == "NVDA"


@pytest.mark.parametrize("value", [None, 123, ["NVDA"]])
def test_non_string_instrument_is_none_and_does_not_change_the_verdict(value):
    adapted = adapt(state=make_state(company_of_interest=value))
    assert adapted.decision.instrument_id is None
    assert verdict(adapted).passed is True


def test_empty_string_instrument_is_passed_through():
    """Pinned mapping: ``str`` is accepted as-is (the guardrail's own contract);
    only a non-string is narrowed, so this adapter never invents a shape the
    frozen module did not ask for."""
    adapted = adapt(state=make_state(company_of_interest=""))
    assert adapted.decision.instrument_id == ""
    assert verdict(adapted).passed is True


# ---------------------------------------------------------------------------
# A8 -- determinism
# ---------------------------------------------------------------------------

def test_two_adaptations_of_equal_inputs_are_identical():
    first, second = adapt(), adapt()
    assert first.decision == second.decision
    assert first.report == second.report
    assert verdict(first).to_dict() == verdict(second).to_dict()


def test_report_is_json_shaped():
    """The report is dumped into the state log, so every leaf is JSON-safe."""
    import json

    json.dumps(adapt(intent=ExecutionIntent(size_pct=None, short_amount=0.0)).report)
    json.dumps(adapt().report)


# ---------------------------------------------------------------------------
# A9 -- purity (AST): stdlib + src.guardrail only, no clock, no network
# ---------------------------------------------------------------------------

ALLOWED_IMPORTS = {"re", "dataclasses", "typing", "__future__", "src"}

FORBIDDEN_IMPORTS = {
    "os", "sys", "time", "datetime", "random", "uuid", "secrets", "socket",
    "requests", "httpx", "urllib", "http", "ssl", "yfinance",
    "tradingagents", "cli", "langchain", "langchain_core", "langgraph",
}

FORBIDDEN_CALLS = {
    "datetime.now", "datetime.today", "datetime.utcnow",
    "time.time", "time.monotonic", "uuid.uuid4", "uuid.uuid1",
    "uuid4", "uuid1", "random.random",
}


def _ast_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _ast_called_attributes(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            parts, base = [func.attr], func.value
            while isinstance(base, ast.Attribute):
                parts.append(base.attr)
                base = base.value
            if isinstance(base, ast.Name):
                parts.append(base.id)
            found.add(".".join(reversed(parts)))
    return found


def test_adapter_import_hygiene():
    imported = _ast_imports(MODULE_PATH)
    assert imported & FORBIDDEN_IMPORTS == set(), imported & FORBIDDEN_IMPORTS
    assert imported - ALLOWED_IMPORTS == set(), imported - ALLOWED_IMPORTS


def test_adapter_has_no_clock_or_random_calls():
    assert _ast_called_attributes(MODULE_PATH) & FORBIDDEN_CALLS == set()


def test_pure_package_modules_import_nothing_forbidden():
    """The two PURE modules must not pull the baseline or a clock in.

    Narrowed to ``decision_adapter`` and ``gate_support``: ``trace_adapter`` has
    exactly one approved lazy baseline import (inside ``default_targets()``),
    checked separately by
    ``test_integration_trace.py::test_tradingagents_is_imported_only_inside_default_targets``,
    and ``governed_graph``/``entry``/``__main__`` are the baseline-facing stage
    whose imports are the point.
    """
    package_dir = pathlib.Path(integration.__file__).parent
    pure_modules = [
        package_dir / "decision_adapter.py",
        package_dir / "gate_support.py",
    ]
    for path in pure_modules:
        assert path.is_file(), path
        imported = _ast_imports(path)
        assert imported & FORBIDDEN_IMPORTS == set(), (path.name, imported & FORBIDDEN_IMPORTS)


def test_importing_the_package_does_not_require_the_framework():
    """The package marker must stay importable without LangGraph installed."""
    package_dir = pathlib.Path(integration.__file__).parent
    init_imports = _ast_imports(package_dir / "__init__.py")
    assert "tradingagents" not in init_imports
    assert "cli" not in init_imports
