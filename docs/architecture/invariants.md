# Invariant Register

> Every invariant is a non-negotiable rule with a zero-tolerance fit criterion.
> A missing fallback action is a defect; “fix the bug” is not a fallback.
> Reviewed 2026-11-25.

| Invariant | Statement | Source req | Enforcing component | Verification | Operational fallback | Status |
|-----------|-----------|-----------|---------------------|--------------|----------------------|--------|
| INV-GUARDRAIL-ZERO-ESCAPE | No AI decision that oversteps a guardrail limit may reach execution | REQ-HARD-GUARDRAIL | `Guardrail` + `src/integration/governed_graph.py` | offline boundary tests: each trigger rejects; full-graph E2E | Reject, set `final_rating=Hold`, add a `REVIEW/HOLD` audit record and the deterministic banner; never pass the original | Complete (CUI Haoyu) |
| INV-CONTEXT-BUDGET | No agent call injects context above the budget | REQ-CONTEXT-BUDGET | dev `ContextBudget` / `BudgetedModel` | dev tests: instrument tokens per call ≤ cap; blocked-call tests | Compact first; if still over budget or the count is unverifiable, block the model call (`ContextBudgetBlocked`/`UnverifiableCountError`) and log the diagnostic | Dev-complete; team-app port pending |
| INV-TRACE-COMPLETENESS | Every critical assertion is linked to a recorded evidence snapshot | REQ-TRACEABILITY | `TraceRecorder` + `src/integration/trace_adapter.py` | offline link auditor; no-data and trace-failure tests; live run 170/170 links | Set `traceable=false`, write `trace_error` and `unbacked_reports` to the sidecar, keep the rating unchanged, and raise the gap in review | Complete (CUI Haoyu) |
| INV-RATING-VALIDITY | Final rating is always a member of the legal 5-tier set | REQ-HARD-GUARDRAIL | `Guardrail` | offline invalid-rating test; fallback test | Use `Hold` (`REVIEW` is never a rating) and record the `ILLEGAL_RATING` audit record | Complete (CUI Haoyu) |

## Notes

- The guardrail fallback is a concrete action: the state is rewritten to
  `Hold`, the original decision text is preserved, and the audit record names
  the trigger, observed value and configured limit.
- The trace fallback is deliberately not a rejection: a trace failure cannot
  change a decision, but it must be visible in the sidecar and review record.
- The context-budget row is based on the dev implementation. If the team-app
  tree is the submission, the module must be ported behind
  `src/context_assembler.py` and the row re-verified there.
- No invariant is enforced by prompt text alone.

> **CUI Haoyu note:** the guardrail/trace invariants and their negative tests
> are mine; the context-budget enforcement is the feature-z owner's work.
