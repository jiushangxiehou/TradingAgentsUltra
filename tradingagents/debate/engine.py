"""Structured turn execution, validation, metrics, and termination policy."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from tradingagents.agents.structured import bind_structured
from tradingagents.dataflows.config import get_config

from .evidence import EvidenceItem, evidence_ids
from .schemas import DebateTurn, TerminationDecision, TurnAudit

logger = logging.getLogger(__name__)

SPEAKER_PREFIX = {
    "Bull Analyst": "bull",
    "Bear Analyst": "bear",
    "Aggressive Analyst": "aggressive",
    "Conservative Analyst": "conservative",
    "Neutral Analyst": "neutral",
}


def bind_debate_turn(llm: Any, agent_name: str) -> Any | None:
    return bind_structured(llm, DebateTurn, agent_name)


def debate_audits(debate_state: Mapping[str, Any]) -> list[TurnAudit]:
    output: list[TurnAudit] = []
    for raw in debate_state.get("turns") or []:
        try:
            output.append(TurnAudit.model_validate(raw))
        except ValidationError:
            continue
    return output


def _normalize_statement(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def _prior_claim_ids(audits: list[TurnAudit]) -> set[str]:
    return {
        claim.claim_id
        for audit in audits
        if audit.turn is not None
        for claim in audit.turn.claims
    }


def _prior_statements(audits: list[TurnAudit]) -> set[str]:
    return {
        _normalize_statement(claim.statement)
        for audit in audits
        if audit.turn is not None
        for claim in audit.turn.claims
    }


def _normalize_and_validate(
    turn: DebateTurn,
    *,
    sequence: int,
    evidence: list[EvidenceItem],
    previous_audits: list[TurnAudit],
) -> tuple[TurnAudit, str]:
    allowed_evidence = evidence_ids(evidence)
    previous_claims = _prior_claim_ids(previous_audits)
    previous_statements = _prior_statements(previous_audits)
    errors: list[str] = []
    new_claim_count = 0
    claims_with_evidence = 0
    valid_evidence_claim_count = 0
    current_statements: set[str] = set()
    prefix = SPEAKER_PREFIX.get(turn.speaker, "speaker")

    for index, claim in enumerate(turn.claims, start=1):
        claim.claim_id = f"{prefix}-r{turn.round}-c{index}"
        invalid_refs = sorted(set(claim.evidence_refs) - allowed_evidence)
        if invalid_refs:
            errors.append(
                f"{claim.claim_id}: unknown evidence refs {', '.join(invalid_refs)}"
            )
        if claim.evidence_refs:
            claims_with_evidence += 1
            if not invalid_refs:
                valid_evidence_claim_count += 1
        normalized = _normalize_statement(claim.statement)
        if normalized not in previous_statements and normalized not in current_statements:
            new_claim_count += 1
        current_statements.add(normalized)

    invalid_rebuttals = []
    valid_rebuttal_count = 0
    for rebuttal in turn.rebuttals:
        target_valid = rebuttal.target_claim_id in previous_claims
        if not target_valid:
            invalid_rebuttals.append(rebuttal.target_claim_id)
        invalid_refs = sorted(set(rebuttal.evidence_refs) - allowed_evidence)
        if invalid_refs:
            errors.append(
                f"rebuttal {rebuttal.target_claim_id}: unknown evidence refs "
                f"{', '.join(invalid_refs)}"
            )
        if target_valid and not invalid_refs:
            valid_rebuttal_count += 1
    if invalid_rebuttals:
        errors.append(
            "rebuttals target unknown claim ids: " + ", ".join(invalid_rebuttals)
        )

    audit = TurnAudit(
        sequence=sequence,
        round=turn.round,
        speaker=turn.speaker,
        turn=turn,
        schema_valid=True,
        evidence_valid=not any("evidence refs" in error for error in errors),
        rebuttal_valid=valid_rebuttal_count == len(turn.rebuttals),
        new_claim_count=new_claim_count,
        claims_with_evidence=claims_with_evidence,
        valid_evidence_claim_count=valid_evidence_claim_count,
        rebuttal_count=len(turn.rebuttals),
        valid_rebuttal_count=valid_rebuttal_count,
        valid_claim_ids=[claim.claim_id for claim in turn.claims],
        errors=errors,
    )
    return audit, render_turn_markdown(turn, audit)


def run_debate_turn(
    *,
    structured_llm: Any | None,
    plain_llm: Any,
    prompt: str,
    speaker: str,
    round_number: int,
    sequence: int,
    debate_state: Mapping[str, Any],
    evidence: list[EvidenceItem],
) -> tuple[TurnAudit, str]:
    """Invoke one speaker, validate its turn, and retain a transparent fallback."""
    previous = debate_audits(debate_state)
    structured_error: Exception | None = None
    if structured_llm is not None:
        try:
            candidate = structured_llm.invoke(prompt)
            if isinstance(candidate, DebateTurn):
                turn = candidate
            elif isinstance(candidate, Mapping):
                turn = DebateTurn.model_validate(candidate)
            else:
                raise TypeError("structured debate output was not a DebateTurn")
            turn = turn.model_copy(
                update={"speaker": speaker, "round": round_number},
                deep=True,
            )
            return _normalize_and_validate(
                turn,
                sequence=sequence,
                evidence=evidence,
                previous_audits=previous,
            )
        except Exception as exc:  # noqa: BLE001 - fallback marks schema failure
            structured_error = exc
            logger.warning("Structured debate output failed for %s: %s", speaker, exc)

    response = plain_llm.invoke(prompt)
    raw = response.content if isinstance(response.content, str) else str(response.content)
    error = (
        f"structured output failed: {structured_error}"
        if structured_error is not None
        else "provider does not support structured debate output"
    )
    audit = TurnAudit(
        sequence=sequence,
        round=round_number,
        speaker=speaker,
        raw_output=raw,
        schema_valid=False,
        evidence_valid=False,
        rebuttal_valid=False,
        errors=[error],
    )
    markdown = f"### {speaker} - Round {round_number}\n\n{raw}"
    return audit, markdown


def render_turn_markdown(turn: DebateTurn, audit: TurnAudit) -> str:
    lines = [
        f"### {turn.speaker} - Round {turn.round}",
        "",
        f"**Stance**: {turn.stance}",
        "",
        f"**Thesis**: {turn.thesis}",
    ]
    if turn.claims:
        lines.extend(["", "**Claims**"])
        for claim in turn.claims:
            evidence = ", ".join(claim.evidence_refs) or "no evidence reference"
            lines.append(
                f"- `{claim.claim_id}` {claim.statement} (Evidence: {evidence}; "
                f"confidence: {claim.confidence})"
            )
    if turn.rebuttals:
        lines.extend(["", "**Rebuttals**"])
        for rebuttal in turn.rebuttals:
            evidence = ", ".join(rebuttal.evidence_refs) or "no evidence reference"
            lines.append(
                f"- Responds to `{rebuttal.target_claim_id}`: {rebuttal.argument} "
                f"(Evidence: {evidence})"
            )
    if turn.concessions:
        lines.extend(["", "**Concessions**"])
        lines.extend(f"- {item}" for item in turn.concessions)
    if turn.open_questions:
        lines.extend(["", "**Open Questions**"])
        lines.extend(f"- {item}" for item in turn.open_questions)
    lines.extend(
        [
            "",
            f"**Changed Position**: {'yes' if turn.changed_position else 'no'}",
            f"**Confidence**: {turn.confidence}",
        ]
    )
    if audit.errors:
        lines.extend(["", "**Validation Notes**"])
        lines.extend(f"- {error}" for error in audit.errors)
    return "\n".join(lines)


def render_prior_turns(audits: list[TurnAudit], limit: int = 8) -> str:
    recent = audits[-limit:]
    if not recent:
        return "(No previous structured turns.)"
    rendered = []
    for audit in recent:
        if audit.turn is None:
            rendered.append(
                f"### {audit.speaker} - Round {audit.round} (UNSTRUCTURED)\n"
                f"{audit.raw_output}"
            )
        else:
            rendered.append(render_turn_markdown(audit.turn, audit))
    return "\n\n".join(rendered)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def debate_metrics(audits: list[TurnAudit]) -> dict[str, float | int]:
    claims = [
        claim
        for audit in audits
        if audit.turn is not None
        for claim in audit.turn.claims
    ]
    rebuttals = [
        rebuttal
        for audit in audits
        if audit.turn is not None
        for rebuttal in audit.turn.rebuttals
    ]
    return {
        "turn_count": len(audits),
        "schema_validity_rate": _rate(
            sum(audit.schema_valid for audit in audits), len(audits)
        ),
        "evidence_coverage": _rate(
            sum(audit.valid_evidence_claim_count for audit in audits), len(claims)
        ),
        "rebuttal_coverage": _rate(
            sum(audit.valid_rebuttal_count for audit in audits),
            len(rebuttals),
        ),
        "new_claim_count": sum(audit.new_claim_count for audit in audits),
        "claim_count": len(claims),
        "rebuttal_count": len(rebuttals),
    }


def evaluate_termination(
    *,
    debate_type: str,
    audits: list[TurnAudit],
    participants: int,
    max_rounds: int,
    config: Mapping[str, Any] | None = None,
) -> TerminationDecision:
    """Evaluate the deterministic stop policy after complete debate cycles."""
    cfg = dict(config or get_config())
    metrics = debate_metrics(audits)
    count = len(audits)
    completed_cycles = count // participants
    full_cycle = count > 0 and count % participants == 0

    if count >= participants * max_rounds:
        return TerminationDecision(
            code="MAX_ROUNDS_REACHED",
            reason=f"Reached the configured limit of {max_rounds} rounds.",
            recommended=True,
            effective=True,
            shadow_mode=False,
            after_round=completed_cycles,
            metrics=metrics,
        )

    min_rounds = max(1, int(cfg.get("debate_min_rounds", 1)))
    if not full_cycle or completed_cycles < min_rounds:
        return TerminationDecision(
            code="CONTINUE",
            reason="The debate has not completed the minimum evaluation window.",
            after_round=completed_cycles,
            metrics=metrics,
        )

    convergence_cycles = max(2, int(cfg.get("debate_convergence_cycles", 2)))
    window = audits[-participants * convergence_cycles :]
    if len(window) < participants * convergence_cycles:
        return TerminationDecision(
            code="CONTINUE",
            reason="Not enough complete cycles for convergence evaluation.",
            after_round=completed_cycles,
            metrics=metrics,
        )

    schema_failures = sum(not audit.schema_valid for audit in window)
    max_schema_failures = max(1, int(cfg.get("debate_max_schema_failures", 2)))
    code = "CONTINUE"
    reason = "New claims and evidence are still being introduced."
    if schema_failures >= max_schema_failures:
        code = "SCHEMA_FAILURE"
        reason = (
            f"{schema_failures} structured debate turns failed validation in the "
            "last evaluation window."
        )
    elif sum(audit.new_claim_count for audit in window) == 0:
        stances: dict[str, set[str]] = {}
        changed = False
        for audit in window:
            if audit.turn is None:
                changed = True
                continue
            stances.setdefault(audit.speaker, set()).add(audit.turn.stance)
            changed = changed or audit.turn.changed_position
        if not changed and all(len(values) == 1 for values in stances.values()):
            code = "CONSENSUS_REACHED"
            reason = (
                "No new claims or evidence were introduced across the evaluation "
                "window, and participant stances remained stable."
            )
        else:
            code = "NO_NEW_CLAIMS"
            reason = (
                "No new claims were introduced across the evaluation window, but "
                "one or more positions changed."
            )

    recommended = code != "CONTINUE"
    shadow_mode = bool(cfg.get("debate_shadow_mode", True))
    enabled = bool(cfg.get("debate_early_termination", False))
    return TerminationDecision(
        code=code,
        reason=reason,
        recommended=recommended,
        effective=recommended and enabled and not shadow_mode,
        shadow_mode=shadow_mode,
        after_round=completed_cycles,
        metrics=metrics,
    )

