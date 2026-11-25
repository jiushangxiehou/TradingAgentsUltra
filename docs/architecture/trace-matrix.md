# Trace Matrix

> Requirement → enforcing component → test/evidence → runtime monitor.
> **Submission tree: `dev` (ADR-007).** Reviewed 2026-11-25.

| Requirement | Enforcing component | Test / evidence | Runtime monitor | Owner / status |
|---|---|---|---|---|
| REQ-CONTEXT-BUDGET | `tradingagents/graph/context_budget.py` (`budget_and_send`), `budgeted_model.py`, `llm_clients/deepseek_context_adapter.py`; facade `src/context_assembler.py` | `tests/test_context_budget_core.py` (40), `tests/test_budget_agent_integration.py` (13), `test/offline/test_context_budget.py` (5) | `agent_input_budget`: `count_before`, `count_after`, `compaction_passes`, `allowed_send`, `count_unit`, `counter_exact` | ZhuXuan (60377218) — implemented, dev |
| REQ-STRUCTURED-DEBATE | `tradingagents/debate/engine.py` (`run_debate_turn`, `bind_debate_turn`, `evaluate_termination`), `schemas.py`, `evidence.py`; node wiring; facade `src/structured_debater.py` | `tests/test_debate_opening.py` (5), `tests/test_structured_agents.py` (35), graph E2E | `TurnAudit`, `debate_metrics`, `TerminationDecision` in the debate state | Fan Hao (60835652) — implemented, dev |
| REQ-TRACEABILITY | `src/trace_recorder.py` (`record_snapshot/record_assertion/record_final_decision/audit`) + `src/integration/trace_adapter.py` | `test/offline/test_traceability.py` (40), `test_integration_trace.py` (51), `test_integration_end_to_end.py` (9) | `guardrail_trace_<date>.json` sidecar; `traceable`, `checked_links`, `resolved_links`, `findings` | CUI Haoyu (60760270) — complete |
| REQ-HARD-GUARDRAIL | `src/guardrail.py` (`evaluate_decision`) + `src/integration/decision_adapter.py`, `gate_support.py`, `governed_graph.py` | `test/offline/test_guardrail.py` (39), `test_integration_decision.py` (32), `test_integration_gate.py` (27), E2E | `guardrail` payload: verdict, audit record, decision, limits, original rating | CUI Haoyu (60760270) — complete |
| REQ-TERMINATION-DISCIPLINE | `tradingagents/graph/termination.py` (`should_terminate`, `TerminationController`) + `src/termination_controller.py` facade; analyst loop in `graph/setup.py` | `test/offline/test_termination.py` (7); debate termination via `tests/test_debate_opening.py` | `TerminationDecision` trigger/reason in the wrap-up log; debate `termination` state | Fan Hao (60835652) — requirement; CUI Haoyu (60760270) — integration. Implemented; stall/budget API tested, per-loop wiring follow-up |

## Field mapping for REQ-STRUCTURED-DEBATE (ADR-002 / ADR-007)

| Requirement field | Implemented field |
|---|---|
| claim | `DebateClaim.statement` |
| evidence_reference | `DebateClaim.evidence_refs` (catalog ids) |
| counter_argument | `DebateRebuttal.target_claim_id` + `argument` |
| round_conclusion | `DebateTurn.thesis` + `round` + `changed_position` |

## Notes

- Every row now names the module that executes on the submission tree. The
  `feature-c` stubs are retired by ADR-007; this matrix no longer claims that
  the implementation is "somewhere else".
- The trace and guardrail rows are implemented and tested through the full
  graph; a live run produced 34 snapshots, 170 resolved links and zero
  findings (see `artifacts/live`).
- The termination row is implemented for the analyst repeat/max-round path and
  for debate convergence/schema termination. The stateful stall/budget signals
  are tested in the controller but not yet wired into every loop; that remains a
  follow-up rather than a silent claim.
- Test counts are the function counts of the named files; the parametrised
  totals are in the verification section below.

## REQ-CONTEXT-BUDGET evidence

| Claim | Test functions |
|---|---|
| Independent thresholds and initial/final budget checks | `test_na_03_04_05_threshold_boundaries`, `test_na_06_07_cap_minus_and_equal_send`, `test_na_08_cap_plus_one_compacts_then_sends` |
| Constraints and paired source facts survive; mandatory overage stops | `test_na_19_hard_cap_preserves_all_required_facts_or_blocks`, `test_paired_news_faithfulness_on_sdk_wire` |
| All Agent model edges and Reflection; tool schemas and structured output | `test_live_graph_all_agent_edges_and_reflection_use_counted_sdk_requests` |
| Tool calls paired with results through subsequent turns and no-tool wrap-up | `test_interleaved_multiple_tool_results_are_paired_by_id`, `test_news_real_subgraph_counts_tool_turn_and_report_at_sdk_transport` |
| CityU automatic estimate, final re-count and zero HTTP on overage | `test_cityu_auto_estimate_compacts_and_enforces_local_cap`, `test_news_subgraph_blocked_requests_have_zero_http` |
| Unchanged off path and checkpoint compatibility | `test_disabled_news_graph_preserves_legacy_sdk_bytes`, `test_budget_checkpoint_resume_counts_pending_news_and_rejects_changed_counter` |

Commands and the merged-dev evidence are recorded in the
[verification constraints](../code-governance/verification-constraints.md#req-context-budget-evidence)
and the [personal acceptance report](../req-context-budget-acceptance.md).