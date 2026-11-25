# Trace Matrix

> Requirement → enforcing component → test/evidence → runtime monitor.
> Reviewed 2026-11-25. The dev tree is authoritative for the context-budget and
> structured-debate implementations; the feature-c/team-app tree still carries
> the original `src/` stubs for those two elements.

| Requirement | Enforcing component | Test / evidence | Runtime monitor | Status |
|-------------|---------------------|-----------------|-----------------|--------|
| REQ-CONTEXT-BUDGET | dev: `tradingagents/graph/context_budget.py` (`budget_and_send`, `BudgetedModel`), `deepseek_context_adapter.py`; team-app: `src/context_assembler.py` stub | dev: `tests/test_context_budget_core.py`, `tests/test_budget_agent_integration.py`; team-app: `test/offline/test_context_budget.py` is a stub | `BudgetDiagnostic` / budget result; blocked-call diagnostic; per-call token count | Dev-complete; port pending |
| REQ-STRUCTURED-DEBATE | dev: `tradingagents/debate/engine.py` (`run_debate_turn`, `bind_debate_turn`), `schemas.py`, graph/agent wiring; team-app: `src/structured_debater.py` stub | dev: `tests/test_debate_opening.py`, `tests/test_structured_agents.py` | `TurnAudit`, debate metrics, `TerminationDecision` in debate state | Dev-complete; port pending |
| REQ-TRACEABILITY | `src/trace_recorder.py` (`TraceRecorder.record_snapshot/record_assertion/record_final_decision/audit`) + `src/integration/trace_adapter.py` | `test/offline/test_traceability.py`, `test/offline/test_integration_trace.py`, `test/offline/test_integration_end_to_end.py` | `guardrail_trace_<date>.json` sidecar; `traceable`, `checked_links`, `resolved_links`, `findings` | Complete (CUI Haoyu) |
| REQ-HARD-GUARDRAIL | `src/guardrail.py` (`Decision`, `GuardrailLimits`, `evaluate_decision`) + `src/integration/governed_graph.py` | `test/offline/test_guardrail.py`, `test/offline/test_integration_decision.py`, `test_integration_gate.py`, `test_integration_end_to_end.py` | `guardrail` audit payload; `audit` record; memory-log rating | Complete (CUI Haoyu) |
| REQ-TERMINATION-DISCIPLINE | `src/termination_controller.py` (constant-only stub) | `test/offline/test_termination.py` (`NotImplementedError`) | planned termination trigger log | Missing |

## Notes

- The context-budget and structured-debate rows are based on the dev feature
  branches. They are not yet ported to the feature-c/team-app `src/` boundaries;
  the module-mapping drift is in the debt register.
- The trace and guardrail rows are implemented and tested in team-app; they
  also run through the full graph. The live run produced 34 snapshots, 170
  resolved links and zero findings.
- The termination row is a real gap: the ADR and constant exist, but there is no
  controller and no passing test.

> **CUI Haoyu note:** the trace and guardrail rows are mine and were verified
> locally. I did not claim the dev context/debate rows as mine; their owners
> should confirm the final module placement.
