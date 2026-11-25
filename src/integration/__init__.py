"""Integration layer: composing the governance modules with the baseline.

ADR-006 / REQ-HARD-GUARDRAIL / REQ-TRACEABILITY

This package is COMPOSITION, not a sixth architectural element: the guardrail
lives in ``src/guardrail.py`` and the evidence chain in ``src/trace_recorder.py``,
and both are frozen. Nothing here re-implements them; it wires them to the
pinned TradingAgents baseline, which they themselves may not import.

Import boundary
---------------
Importing this package must NOT require the framework. Only the pure modules are
imported here; the ones that touch the baseline are left for the caller to
import explicitly, so a tooling script can read the decision adapter without a
LangGraph installation:

``decision_adapter``  pure: upstream state -> guardrail ``Decision``.
``gate_support``      pure: verdict -> state mutations, fallback text, payload.
``trace_adapter``     stdlib + recorder; the baseline is imported lazily inside
                      ``default_targets()`` only.
``governed_graph``    the ``TradingAgentsGraph`` subclass (imports the baseline).
``entry``             the CLI wrapper (imports the CLI at call time).
"""

from __future__ import annotations

from src.integration.decision_adapter import (
    AdaptedDecision,
    ExecutionIntent,
    build_decision,
)
from src.integration.gate_support import (
    NOTE_GUARDRAIL_CONFIG_ERROR,
    apply_guardrail,
    config_error_result,
    fallback_text,
    guardrail_payload,
    limits_payload,
)

__all__ = [
    "NOTE_GUARDRAIL_CONFIG_ERROR",
    "AdaptedDecision",
    "ExecutionIntent",
    "apply_guardrail",
    "build_decision",
    "config_error_result",
    "fallback_text",
    "guardrail_payload",
    "limits_payload",
]
