"""Gate support: turn a ``GuardrailResult`` into state mutations and a payload.

ADR-006 / REQ-HARD-GUARDRAIL / INV-GUARDRAIL-ZERO-ESCAPE / INV-RATING-VALIDITY

``apply_guardrail`` is the ONE place a rejected decision becomes visible. It
returns a new state (a shallow copy; nothing upstream is mutated in place, so a
caller holding the original state still sees what the agents produced) and the
``guardrail`` payload the state log carries.

Pinned semantics (integration memo)
-----------------------------------
Pass       ``final_rating`` is NOT rewritten and ``final_trade_decision`` is NOT
           touched. Only the ``guardrail`` payload is added.
Reject     ``final_rating`` is exactly ``"Hold"`` -- a legal tier, so
           INV-RATING-VALIDITY holds -- and the audit action is exactly
           ``"REVIEW/HOLD"``. ``"REVIEW"`` is never written as a rating: upstream
           reserves it for an unreadable decision (``agents/rating.py``).
Banner     The original decision text is preserved VERBATIM below a
           deterministic banner. The two rating labels therefore disagree by
           construction, and ``extract_rating``/``parse_rating`` return ``None``
           (``"REVIEW"`` for ``parse_rating``) for the combined text. The
           pipeline stays correct because every baseline consumer calls
           ``run_rating``, which prefers the explicit ``final_rating`` we set to
           ``Hold`` over the text. That is the reason, not label agreement.
Preserved  Every other state key is untouched: the reports, the debate
           histories, the trader's plan and the investment plan are the evidence
           the rejection is audited against.
Config     A guardrail that cannot run (``GuardrailError``) is still a
           rejection: ``config_error_result`` builds the same Hold fallback with
           the fault on the record. A gate that cannot run never passes, and
           it never raises into the caller either.
"""

from __future__ import annotations

import hashlib
from typing import Final

from src.guardrail import (
    AUDIT_ACTION_REVIEW_HOLD,
    FALLBACK_RATING,
    AuditRecord,
    Decision,
    GuardrailLimits,
    GuardrailResult,
    Trigger,
)

# The state keys the gate owns. Pinned so the mutation table is testable.
GATE_KEYS: Final[tuple[str, ...]] = ("guardrail",)

# Note codes the gate can attach. Deterministic strings, never sentences.
NOTE_GUARDRAIL_CONFIG_ERROR: Final[str] = "GUARDRAIL_CONFIG_ERROR"


def _record_id(trigger: Trigger, observed: object, limit: object, action: str) -> str:
    """``record_id`` derived from content alone -- no clock, no counter.

    Mirrors the frozen module's own rule (``src/guardrail.py``) so a record this
    integration builds is indistinguishable in shape from one the guardrail
    builds, and is equally reproducible.
    """
    payload = "|".join(
        [trigger.value, _render_value(observed), _render_value(limit), action]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"gr-{digest[:16]}"


def config_error_result(exc: BaseException, limits: GuardrailLimits | None = None) -> GuardrailResult:
    """A rejection for a guardrail that could not run at all.

    REQ-HARD-GUARDRAIL / INV-RATING-VALIDITY. ``evaluate_decision`` raises
    ``GuardrailError`` when its *configuration* is unusable. That is not a pass
    -- a gate that cannot run must not wave the decision through -- so this
    builds the same fail-closed fallback a malformed decision gets: rating
    ``Hold``, trigger ``MALFORMED_DECISION``, action ``REVIEW/HOLD``, and the
    exception text as the observed value so the reason is on the record.

    Pure: the record id is content-derived, so equal faults give equal records.
    """
    checked = limits if isinstance(limits, GuardrailLimits) else GuardrailLimits()
    observed = f"{type(exc).__name__}: {exc}"
    limit = checked.as_dict()
    decision = Decision(
        rating=FALLBACK_RATING,
        size_pct=None,  # type: ignore[arg-type]  # nothing was evaluated
        short_amount=None,  # type: ignore[arg-type]
        available_cash=None,  # type: ignore[arg-type]
        instrument_id=None,
    )
    audit = AuditRecord(
        record_id=_record_id(Trigger.MALFORMED_DECISION, observed, limit, AUDIT_ACTION_REVIEW_HOLD),
        trigger=Trigger.MALFORMED_DECISION,
        observed_value=observed,
        configured_limit=limit,
        action=AUDIT_ACTION_REVIEW_HOLD,
    )
    return GuardrailResult(decision=decision, passed=False, audit=audit)


def limits_payload(limits: GuardrailLimits | None) -> dict[str, object]:
    """The limits this run was judged against, for the state and the sidecar."""
    checked = limits if isinstance(limits, GuardrailLimits) else GuardrailLimits()
    return dict(checked.as_dict())


def _render_value(value: object) -> str:
    """A deterministic, human-readable rendering of one audit value.

    Floats keep their shortest round-tripping form (``0.1001``, not
    ``0.10009999999999999``); containers are sorted, because the legal-rating
    set is unordered and ``str(set)`` would order by hash seed.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value!r}"
    if isinstance(value, (set, frozenset)):
        return "{" + ", ".join(sorted(_render_value(item) for item in value)) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    return repr(value)


def fallback_text(result: GuardrailResult, *, original: object) -> str:
    """The rejected run's ``final_trade_decision``: banner, then the original.

    Byte-identical for equal inputs: the banner is built only from the audit
    record's own fields, and the original text is appended unchanged.
    """
    audit = result.audit
    if audit is None:  # pragma: no cover - a rejection always carries one
        raise ValueError("fallback_text requires a rejected GuardrailResult")

    banner = "\n".join(
        [
            f"**Rating**: {FALLBACK_RATING}",
            "",
            f"> **Guardrail: {AUDIT_ACTION_REVIEW_HOLD} \u2014 rejected before execution.**",
            f"> trigger: {audit.trigger.value}",
            f"> observed: {_render_value(audit.observed_value)}",
            f"> limit: {_render_value(audit.configured_limit)}",
            f"> record: {audit.record_id}",
            "> The original decision is preserved below for audit; it is not the executed rating.",
        ]
    )
    if isinstance(original, str) and original:
        return f"{banner}\n\n---\n\n{original}"
    return banner


def guardrail_payload(result: GuardrailResult, *, notes: tuple[str, ...] = ()) -> dict[str, object]:
    """The ``guardrail`` state key: the verdict, its audit record and any notes.

    The audit record is copied field by field, rendering a set-valued limit
    (the legal-rating set) as the same deterministic ``{a, b, c}`` string the
    banner shows. ``AuditRecord.to_dict`` returns that set raw, and a raw set is
    neither ordered nor JSON-serialisable -- so the state log would differ run to
    run for an identical rejection. No ``json`` import is needed: nothing here
    serialises.
    """
    audit = result.audit
    audit_dict: dict[str, object] | None = None
    if audit is not None:
        audit_dict = audit.to_dict()
        audit_dict["observed_value"] = _render_value(audit.observed_value)
        audit_dict["configured_limit"] = _render_value(audit.configured_limit)
    return {
        "passed": result.passed,
        "action": None if result.passed else AUDIT_ACTION_REVIEW_HOLD,
        "audit": audit_dict,
        "decision": result.to_dict()["decision"],
        "notes": list(notes),
    }


def apply_guardrail(
    result: GuardrailResult, final_state: dict, *, notes: tuple[str, ...] = ()
) -> tuple[dict, dict[str, object]]:
    """Apply one verdict: return ``(mutated_state, payload)``.

    ``mutated_state`` is a shallow copy of ``final_state`` with the gate's
    mutations applied; the caller's mapping is never modified.
    """
    state_out = dict(final_state)
    payload = guardrail_payload(result, notes=notes)

    if result.passed:
        # Pass: the decision stands. Adding the payload is the only change.
        state_out["guardrail"] = payload
        return state_out, payload

    state_out["final_rating"] = FALLBACK_RATING
    state_out["final_trade_decision"] = fallback_text(
        result, original=final_state.get("final_trade_decision")
    )
    state_out["guardrail"] = payload
    return state_out, payload
