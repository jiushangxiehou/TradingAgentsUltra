# Invariant Register

> Every invariant is a non-negotiable rule with a zero-tolerance fit criterion.
> A missing fallback action is a defect; "fix the bug" is not a fallback.

| Invariant | Statement | Source req | Enforcing component | Verification | Operational fallback |
|-----------|-----------|-----------|---------------------|--------------|----------------------|
| INV-GUARDRAIL-ZERO-ESCAPE | No AI decision that oversteps a guardrail limit may reach execution | REQ-HARD-GUARDRAIL | `Guardrail` | offline test: boundary crossings → zero escapes | Reject + route to REVIEW/HOLD + log audit record |
| INV-CONTEXT-BUDGET | No agent call injects context above the budget | REQ-CONTEXT-BUDGET | `ContextAssembler` | offline test: instrument tokens per call ≤ budget | Compact + log re-injection warning |
| INV-TRACE-COMPLETENESS | Every critical assertion is linked to a recorded evidence snapshot | REQ-TRACEABILITY | `TraceRecorder` | offline test: auditor resolves every link | Log gap + surface in review memo |
| INV-RATING-VALIDITY | Final rating is always a member of the legal 5-tier set | REQ-HARD-GUARDRAIL | `Guardrail` | offline test: invalid rating → fallback | Fall back to REVIEW/HOLD |

(TODO: confirm each fallback is a concrete action, not "fix the bug".)