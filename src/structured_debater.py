"""Structured debater facade (REQ-STRUCTURED-DEBATE, ADR-002, ADR-007).

The runtime implementation lives in `tradingagents/debate/` because the five
debate nodes and the router consume it:

    tradingagents.debate.schemas     DebateTurn / DebateClaim / DebateRebuttal /
                                     TurnAudit / TerminationDecision
    tradingagents.debate.evidence    stable evidence ids from the analyst reports
    tradingagents.debate.engine      turn binding, validation, metrics, the
                                     deterministic termination policy

This module is the project-owned, stable entry point -- it re-exports the
runtime instead of keeping a second copy (ADR-007), the same pattern as
`src/termination_controller.py` (ADR-005).

Field mapping (the requirement names four fields; the typed schema is the
implemented shape, ADR-002 "Field mapping as implemented"):

    claim               -> DebateClaim.statement
    evidence_reference  -> DebateClaim.evidence_refs (ids from the catalog)
    counter_argument    -> DebateRebuttal.target_claim_id + argument
    round_conclusion    -> DebateTurn.thesis + round + changed_position
"""

from __future__ import annotations

from tradingagents.debate.engine import (
    bind_debate_turn,
    debate_audits,
    debate_metrics,
    evaluate_termination,
    render_prior_turns,
    render_turn_markdown,
    run_debate_turn,
)
from tradingagents.debate.evidence import (
    EvidenceItem,
    build_evidence_registry,
    evidence_ids,
    render_evidence_catalog,
)
from tradingagents.debate.schemas import (
    DebateClaim,
    DebateRebuttal,
    DebateTurn,
    TerminationDecision,
    TurnAudit,
)

__all__ = [
    "DebateClaim",
    "DebateRebuttal",
    "DebateTurn",
    "EvidenceItem",
    "TerminationDecision",
    "TurnAudit",
    "bind_debate_turn",
    "build_evidence_registry",
    "debate_audits",
    "debate_metrics",
    "evaluate_termination",
    "evidence_ids",
    "render_evidence_catalog",
    "render_prior_turns",
    "render_turn_markdown",
    "run_debate_turn",
]
