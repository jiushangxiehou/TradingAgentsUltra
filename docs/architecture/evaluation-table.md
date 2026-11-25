# Candidate Evaluation Table

> Comparison that justifies the selected architecture. Scores are 1–5
> (1 = poor, 5 = strong). The weights are the team's stated priorities:
> safety 30%, token cost 25%, auditability 20%, maintainability 15%,
> convergence 10%. Reviewed 2026-11-25.

| Candidate | Token cost (25%) | Auditability (20%) | Safety (30%) | Convergence (10%) | Maintainability (15%) | Weighted score | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| A. Baseline monolith: full history, no deterministic gate, report text only | 1 | 1 | 1 | 1 | 5 | 1.60 | Rejected: unsafe and unauditable |
| B. Prompt-only guardrail, full history, raw report logging | 1 | 2 | 2 | 2 | 4 | 2.05 | Rejected: a prompt is not a boundary |
| C. Rating-only gate + current-book sizing, partial trace | 3 | 3 | 2 | 2 | 4 | 2.75 | Rejected: a new oversized Buy passes at `size_pct=0`; risk-reducing Sell can be rejected |
| D. Layered context + explicit execution intent + G1 run-level trace + deterministic gate | 4 | 5 | 5 | 4 | 3 | **4.35** | **Selected** |
| E. Full per-token provenance + per-thread attribution + layered context | 4 | 5 | 5 | 5 | 1 | 4.15 | Rejected: the audit benefit does not justify the complexity/attribution ambiguity |

## Why D wins

- **Safety:** D is the only option that makes the execution intent explicit and
  rejects a missing/malformed input before execution. C is superficially similar
  but its size source is the current book, not the proposed order.
- **Auditability:** D records one evidence set for the run and links every
  critical assertion to it. E is slightly richer per assertion but much harder
  to maintain and falsely precise when the analysts run in parallel.
- **Token cost:** D enforces a per-agent budget with compaction; A/B do not.
- **Convergence:** structured debate and termination policy are separate
  elements; D composes them without making the guardrail depend on model prose.
- **Maintainability:** D's `src/` boundaries and ADRs are easier to test and
  review than E's per-token machinery; the remaining 19-file dev drift is a
  known implementation debt, not a reason to choose E.

## Consequences and reopen conditions

D accepts a conservative guardrail and a run-level evidence set. If the
false-rejection rate is too high, tune the limits rather than removing the gate.
If the run-level set proves too coarse for an audit, add a finer evidence
dimension through a new ADR and tests; do not silently switch to per-thread
attribution.

> **CUI Haoyu note:** the guardrail/trace rows (C/D/E) reflect the decisions I
> owned; the context/debate candidate descriptions come from ADR-001/002 and the
> dev implementations.
