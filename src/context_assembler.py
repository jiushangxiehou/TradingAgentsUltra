"""Context assembler facade (REQ-CONTEXT-BUDGET, ADR-001, ADR-007).

The runtime implementation lives where the graph consumes it:

    tradingagents.graph.context_budget          budget core: layering, pairing,
                                                compaction, final count, one-time
                                                send permit
    tradingagents.graph.budgeted_model          the graph-agent model boundary
    tradingagents.llm_clients.deepseek_context_adapter
                                                CityU local-estimate transport

This module is the project-owned, stable entry point -- it re-exports the
runtime rather than keeping a second copy, exactly like
`src/termination_controller.py` (ADR-005). The earlier placeholder
`raise NotImplementedError` is retired by ADR-007: the element map names the
dev modules and this facade names the contract.

Invariant: INV-CONTEXT-BUDGET. `build_context` never sends an over-budget
request: `budget_and_send` raises `ContextBudgetBlocked` instead, and the
caller must not call the model.
"""

from __future__ import annotations

from typing import Any

from tradingagents.graph.context_budget import (
    REASON_DISABLED,
    ContextBudgetBlocked,
    UnverifiableCountError,
    budget_and_send,
    is_budget_enabled,
    resolve_budget,
)

__all__ = [
    "REASON_DISABLED",
    "ContextBudgetBlocked",
    "UnverifiableCountError",
    "budget_and_send",
    "build_context",
    "is_budget_enabled",
    "resolve_budget",
]


def build_context(**kwargs: Any) -> Any:
    """Compatibility entry point: prepare, budget and (optionally) send.

    Takes exactly the `budget_and_send` keyword arguments; see
    `tradingagents.graph.context_budget.budget_and_send` for the contract and
    the `BudgetDiagnostic` it returns.
    """
    return budget_and_send(**kwargs)
