# Trace Matrix

> Requirement → enforcing component → test/evidence → runtime monitor.

| Requirement | Enforcing component | Test / evidence | Runtime monitor |
|-------------|---------------------|-----------------|-----------------|
| REQ-CONTEXT-BUDGET | [BudgetedModel](../../tradingagents/graph/budgeted_model.py), [budget_and_send](../../tradingagents/graph/context_budget.py), [CityU transport](../../tradingagents/llm_clients/deepseek_context_adapter.py) | [Budget core](../../tests/test_context_budget_core.py) and [Agent integration](../../tests/test_budget_agent_integration.py); cases below | `agent_input_budget`: `count_before`, `count_after`, `compaction_passes`, `allowed_send`, `count_unit`, `counter_exact` |
| REQ-STRUCTURED-DEBATE | `StructuredDebater` | offline test: schema validation 100% | turn schema validator |
| REQ-TRACEABILITY | `TraceRecorder` + `src/integration/trace_adapter.py` | offline tests: link auditor resolves all; `test_integration_trace.py`; `test_integration_end_to_end.py` (real scripted graph) | `guardrail_trace_<date>.json` sidecar; `traceable`/`checked_links`/`findings` |
| REQ-HARD-GUARDRAIL | `Guardrail` + `src/integration/governed_graph.py` | offline tests: zero adversarial escapes; `test_integration_graph.py`; `test_integration_end_to_end.py` (pass, oversize, missing intent) | `guardrail` audit payload; audit record; memory-log rating |
| REQ-TERMINATION-DISCIPLINE | `TerminationController` | offline test: repeats ≥ τ terminates | termination trigger log |

(TODO: map every requirement from docs/req/requirements.yaml here. This table is a seed.)

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
