# Invariant Register

> Every invariant is a non-negotiable rule with a zero-tolerance fit criterion.
> A missing fallback action is a defect; "fix the bug" is not a fallback.
> **Submission tree: `dev` (ADR-007).** Reviewed 2026-11-25.

| Invariant | Statement | Source req | Enforcing component | Verification | Operational fallback | Status |
|-----------|-----------|-----------|---------------------|--------------|----------------------|--------|
| INV-GUARDRAIL-ZERO-ESCAPE | No AI decision that oversteps a guardrail limit may reach execution | REQ-HARD-GUARDRAIL | `Guardrail` + `src/integration/governed_graph.py` | offline boundary tests (39); decision/gate tests (59); full-graph E2E (9) | Reject, set `final_rating=Hold`, add a `REVIEW/HOLD` audit record and the deterministic banner; never pass the original | Complete (CUI Haoyu) |
| INV-CONTEXT-BUDGET | No agent call injects context above the budget | REQ-CONTEXT-BUDGET | `tradingagents/graph/context_budget.py` (`budget_and_send`) + `budgeted_model.py`; facade `src/context_assembler.py` | dev tests: per-request count ≤ configured cap; overage/zero-send tests; `test/offline/test_context_budget.py` config contract | Compact first; if still over budget or the count is unverifiable, block the model call (`ContextBudgetBlocked`/`UnverifiableCountError`) and log the content-free diagnostic | Complete on dev (ZhuXuan) |
| INV-TRACE-COMPLETENESS | Every critical assertion is linked to a recorded evidence snapshot | REQ-TRACEABILITY | `TraceRecorder` + `src/integration/trace_adapter.py` | offline link auditor (40); integration trace tests (51); live run 170/170 links | Set `traceable=false`, write `trace_error` and `unbacked_reports` to the sidecar, keep the rating unchanged, and raise the gap in review | Complete (CUI Haoyu) |
| INV-RATING-VALIDITY | Final rating is always a member of the legal 5-tier set | REQ-HARD-GUARDRAIL | `Guardrail` | offline legal/illegal rating tests; fallback tests | Use `Hold` (`REVIEW` is never a rating) and record the `ILLEGAL_RATING` audit record | Complete (CUI Haoyu) |

## Notes

- The guardrail fallback is a concrete action: the state is rewritten to
  `Hold`, the original decision text is preserved, and the audit record names
  the trigger, observed value and configured limit.
- The trace fallback is deliberately not a rejection: a trace failure cannot
  change a decision, but it must be visible in the sidecar and review record.
- The context-budget row is enforced by the dev modules and named through the
  `src/context_assembler.py` facade (ADR-007). The earlier note "if the
  team-app tree is the submission, port it behind the stub" is obsolete: the
  submission tree is `dev`, and the runtime path is the enforced one.
- No invariant is enforced by prompt text alone.
