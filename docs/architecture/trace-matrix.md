# Trace Matrix

> Requirement → enforcing component → test/evidence → runtime monitor.
> Reviewed 2026-11-25. The dev tree is authoritative for the context-budget and
> structured-debate implementations; the feature-c/team-app tree still carries
> the original `src/` stubs for those two elements.

| Requirement | Enforcing component | Test / evidence | Runtime monitor | Status |
|-------------|---------------------|-----------------|-----------------|--------|
| REQ-CONTEXT-BUDGET | [BudgetedModel](../../tradingagents/graph/budgeted_model.py), [budget_and_send](../../tradingagents/graph/context_budget.py), [CityU transport](../../tradingagents/llm_clients/deepseek_context_adapter.py) | [Budget core](../../tests/test_context_budget_core.py) and [Agent integration](../../tests/test_budget_agent_integration.py); cases below | `agent_input_budget`: `count_before`, `count_after`, `compaction_passes`, `allowed_send`, `count_unit`, `counter_exact` | Dev-complete (feature-z); feature-c stub |
| REQ-STRUCTURED-DEBATE | dev: `tradingagents/debate/engine.py` (`run_debate_turn`, `bind_debate_turn`), `schemas.py`, graph/agent wiring; team-app: `src/structured_debater.py` stub | dev: `tests/test_debate_opening.py`, `tests/test_structured_agents.py` | `TurnAudit`, debate metrics, `TerminationDecision` in debate state | Dev-complete (feature-f); feature-c stub |
| REQ-TRACEABILITY | `src/trace_recorder.py` (`TraceRecorder.record_snapshot/record_assertion/record_final_decision/audit`) + `src/integration/trace_adapter.py` | `test/offline/test_traceability.py`, `test/offline/test_integration_trace.py`, `test/offline/test_integration_end_to_end.py` | `guardrail_trace_<date>.json` sidecar; `traceable`, `checked_links`, `resolved_links`, `findings` | Complete (CUI Haoyu) |
| REQ-HARD-GUARDRAIL | `src/guardrail.py` (`Decision`, `GuardrailLimits`, `evaluate_decision`) + `src/integration/governed_graph.py` | `test/offline/test_guardrail.py`, `test/offline/test_integration_decision.py`, `test_integration_gate.py`, `test_integration_end_to_end.py` | `guardrail` audit payload; `audit` record; memory-log rating | Complete (CUI Haoyu) |
| REQ-TERMINATION-DISCIPLINE | `src/termination_controller.py` (constant-only stub) | `test/offline/test_termination.py` (`NotImplementedError`) | planned termination trigger log | Missing |

## Notes

- The context-budget and structured-debate rows are implemented on dev. They
  are not yet ported to the feature-c/team-app `src/` boundaries; the
  module-mapping drift is in the debt register.
- The trace and guardrail rows are implemented and tested in team-app; they
  also run through the full graph. The live run produced 34 snapshots, 170
  resolved links and zero findings.
- The termination row is a real gap: the ADR and constant exist, but there is no
  controller and no passing test.

> **CUI Haoyu note:** the trace and guardrail rows are mine and were verified
> locally. I did not claim the dev context/debate rows as mine; their owners
> confirmed the implementation in the dev docs.

## REQ-CONTEXT-BUDGET evidence

| Claim | Existing test functions |
|---|---|
| Independent thresholds and initial/final budget checks | `test_na_03_04_05_threshold_boundaries`, `test_na_06_07_cap_minus_and_equal_send`, `test_na_08_cap_plus_one_compacts_then_sends` |
| Constraints and paired source facts survive; mandatory overage stops | `test_na_19_hard_cap_preserves_all_required_facts_or_blocks`, `test_paired_news_faithfulness_on_sdk_wire` |
| All Agent model edges and Reflection; tool schemas and structured output | `test_live_graph_all_agent_edges_and_reflection_use_counted_sdk_requests` |
| Tool calls paired with results through subsequent turns and no-tool wrap-up | `test_interleaved_multiple_tool_results_are_paired_by_id`, `test_news_real_subgraph_counts_tool_turn_and_report_at_sdk_transport` |
| CityU automatic estimate, final re-count and zero HTTP on overage | `test_cityu_auto_estimate_compacts_and_enforces_local_cap`, `test_news_subgraph_blocked_requests_have_zero_http` |
| Unchanged off path and checkpoint compatibility | `test_disabled_news_graph_preserves_legacy_sdk_bytes`, `test_budget_checkpoint_resume_counts_pending_news_and_rejects_changed_counter` |

Commands, merged dev SHA and known placeholder failures are recorded in the
[verification constraints](../code-governance/verification-constraints.md#req-context-budget-evidence)
and the [personal acceptance report](../req-context-budget-acceptance.md).
