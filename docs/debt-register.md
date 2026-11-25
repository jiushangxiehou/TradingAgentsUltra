# Debt Register (D4)

> Technical debt tracked across AI-era categories. Last reviewed: 2026-11-25.
> Status values: open / mitigated / closed. Where the owner is not yet
> confirmed, the team should replace `owner (to confirm)` with a name.

| Category | Debt | Where | Severity | Mentor / owner | Mitigation / status |
|----------|------|-------|----------|----------------|---------------------|
| Guardrail debt | The frozen gate checks limits, not rating/intent **direction**. A `Sell`/`Underweight` rating with a declared long intent and `short_amount=0` passes if size ≤ 10%. | `src/guardrail.py`, `src/integration/decision_adapter.py` | H | CUI Haoyu | Displayed as an amber operator note in the local GUI; a policy decision/ADR is required before making it a hard trigger. **Open** (scope limit documented in ADR-006). |
| Guardrail debt | The trader's free-text sizing is only corroboration; `SIZE_DISAGREEMENT` is recorded but never rejects. | `src/integration/decision_adapter.py` | M | CUI Haoyu | Declared `ExecutionIntent` is authoritative; the note is shown in the report/GUI. **Accepted by design** (A+B-strict). |
| Baseline debt | Dev contains 19 altered pinned files from feature-f/feature-z; `verify_baseline.py --strict` fails on dev. | `tradingagents/agents/**`, `tradingagents/graph/**`, `tradingagents/llm_clients/**` | H | module owners (to confirm) | Either port the changes into the project-owned `src/` layer and restore the pinned files, or approve a controlled override ADR. **Open**. |
| Architecture debt | Runtime modules do not match the feature-c element map: context budget lives in `tradingagents/graph/context_budget.py`; structured debate lives in `tradingagents/debate/`; `src/context_assembler.py` and `src/structured_debater.py` remain stubs. | `tradingagents/graph/**`, `tradingagents/debate/**`, `src/*_assembler.py`, `src/structured_debater.py` | H | feature-f / feature-z owners (to confirm) | Reconcile the element map or move the implementations behind the declared `src/` interfaces. **Open**. |
| Evaluation debt | Termination discipline has no implementation and no passing test. | `src/termination_controller.py`, `test/offline/test_termination.py` | H | owner (to confirm) | Implement a controller (repeat/stall/budget) and add a failing-then-passing invariant test. **Open**. |
| Evaluation debt | `test/live/test_live_prose.py` is a `NotImplementedError` stub. | `test/live/test_live_prose.py` | M | owner (to confirm) | Add the DeepEval faithfulness/relevancy run or declare it a non-blocking phase. **Open**. |
| CI debt | `static-analysis` is an `echo` placeholder; it does not run ruff, type checking, dependency checks, or safety-path checks. | `.github/workflows/ci.yml` | H | owner (to confirm) | Wire `ruff`, `pip check`/`pip-audit`, and the selected type checker; make the job blocking. **Open**. |
| CI debt | Test-approval and semantic-evaluation gates are absent/placeholder; branch protection is not configured. | `.github/workflows/ci.yml`, GitHub settings | H | team lead | Implement the two gates, configure required checks + human review, and require an ADR for safety paths. **Open**. |
| CI debt | The AI-use-log gate compares only `HEAD^..HEAD`, so a multi-commit push can bypass it. | `.github/workflows/ci.yml` | M | owner (to confirm) | Compare the push/PR base..head diff for `src/`/`prompts/` changes. **Open**. |
| Process debt | D4 review memos, debt register and bug diary were templates until this pass. | `docs/review-memo.md`, `docs/debt-register.md`, `docs/bug-diary.md` | M | CUI Haoyu | Populated with the integration review units and recorded defects; keep appending per change. **Mitigated / ongoing**. |
| Environment debt | yfinance's default curl_cffi Chrome fingerprint stalls on `fc.yahoo.com` on this Windows host. | local GUI worker; data path | M | CUI Haoyu | Local-only `requests` session adapter in `gui/worker.py`; not a pipeline change. Documented; **mitigated locally**. |
| Documentation debt | Point 12 was misread as a report section; it means 12-point font. | `Report.md` | L | CUI Haoyu | Report header corrected and section 12 placeholder removed. **Closed**. |

## Notes

- The debt list is deliberately conservative: it records the current gaps rather
  than assuming the dev branch will be merged into the strict feature-c
  baseline.
- A debt that changes a safety invariant must update
  `docs/architecture/invariants.md` and add a regression test.
