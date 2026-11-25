"""Termination controller facade (REQ-TERMINATION-DISCIPLINE, ADR-005).

The runtime implementation lives in ``tradingagents.graph.termination`` because
the analyst tool loop and the debate engine are part of the pinned application
graph. This module is the project-owned, stable entry point used by the offline
tests and by callers that should not import a graph-internal module directly.
"""

from __future__ import annotations

from tradingagents.graph.termination import (
    REPEAT_THRESHOLD,
    STALL_THRESHOLD,
    TerminationController,
    TerminationDecision,
    should_terminate,
    tool_round_signatures,
)

__all__ = [
    "REPEAT_THRESHOLD",
    "STALL_THRESHOLD",
    "TerminationController",
    "TerminationDecision",
    "should_terminate",
    "tool_round_signatures",
]
