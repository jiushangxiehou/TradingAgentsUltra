# Evaluation Logbook

> Accumulated evidence behind architecture choices. Dates are the recorded run
> dates, not retrospective estimates. Reviewed 2026-11-25.

| Date | Evaluation | Observation | Consequence |
|---|---|---|---|
| 2026-11-24 | Baseline pin and layout | Vendor layout verified 213/213 pinned files; root layout later verified 208 pinned + 5 declared overrides | Root layout selected for feature-c; verifier made dual-layout |
| 2026-11-24 | Guardrail trigger matrix | Negative tests exercised malformed input, position limit, short/cash, illegal rating and config error; all rejected with one audit record | Gate kept fail-closed; `Hold` is the fallback |
| 2026-11-24 | Trace evidence coverage | Link auditor resolves every assertion to a snapshot; no-data and trace-failure cases recorded | G1 run-level evidence set selected over per-thread attribution |
| 2026-11-25 | Offline regression | 429 offline tests passed, 2 deselected; 9 full-graph end-to-end tests passed | Guardrail/trace integration retained |
| 2026-11-25 | Dev integration regression | Dev upstream suite 1,496 passed, 6 skipped; two Windows Temp `PermissionError` cases passed when rerun outside Temp | Environment issue, not a code regression; module/baseline debt remains |
| 2026-11-25 | Live guarded run | NVDA 2026-11-20, four analysts, 14m28s; `Underweight`; guardrail PASS; 34 snapshots, 170/170 links, 0 findings; FRED/Reddit/StockTwits recorded as no-data | Runtime integration works; no-data evidence is visible |
| 2026-11-25 | Static analysis | `ruff check src test` PASS; 97 packages compatible via `uv pip check` | Lint + dependency layer wired into CI; type/safety checks still follow-up |
| 2026-11-25 | Report formatting clarification | “Point 12” confirmed as 12-point font, not a section | D6 placeholder removed; formatting/page requirement recorded |

| 2026-11-25 | Termination controller | 7 offline cases: repeat, distinct, cap, budget, stall, reset, invalid threshold; analyst loop wires repeat+max | D8 termination gap reduced; full per-loop stall/budget wiring remains a follow-up |

## What this log does not claim

- It does not claim the semantic-evaluation gate or the live prose threshold is
  enforced; both are still open.
- It does not treat the two Windows `PermissionError` cases as application
  failures; the passing rerun is recorded.
- It does not claim the dev baseline is byte-identical to the pinned tree; the
  19-file drift is explicit debt.
