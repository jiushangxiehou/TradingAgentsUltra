# Debt Register (D4)

> Technical debt tracked across AI-era categories. Last reviewed: 2026-11-25
> (submission-reconciliation round: ADR-007/008/009, the D7 gates, the D4
> records and the D5/D6 consolidation).
> Status values: open / mitigated / accepted / closed. Owners are people.

| Category | Debt | Where | Severity | Owner | Mitigation / status |
|----------|------|-------|----------|-------|---------------------|
| Guardrail debt | The frozen gate checks limits, not rating/intent **direction**. A `Sell`/`Underweight` rating with a declared long intent and `short_amount=0` passes if size ≤ 10%. | `src/guardrail.py`, `src/integration/decision_adapter.py` | H | CUI Haoyu (60760270) | Displayed as an amber operator note in the local GUI; a policy decision/ADR is required before making it a hard trigger. **Open** (scope limit documented in ADR-006). |
| Guardrail debt | The trader's free-text sizing is only corroboration; `SIZE_DISAGREEMENT` is recorded but never rejects. | `src/integration/decision_adapter.py` | M | CUI Haoyu | Declared `ExecutionIntent` is authoritative (policy A+B-strict, ADR-006). **Accepted by design**. |
| Baseline debt | 19 pinned files differ from 0.7.1 on `dev`, so the strict verifier used to fail there. | `tradingagents/**` | H | Fan Hao (60835652), ZhuXuan (60377218), CUI Haoyu | Each difference is declared with owner, requirement, commit and ADR in `scripts/baseline-overrides.json`; the verifier passes on declared drift and fails undeclared or stale drift (ADR-008). **Declared / accepted**; reopen by porting into `src/` and restoring the pinned files. |
| Architecture debt | The element map named `src/context_assembler.py` and `src/structured_debater.py` as owners while the runtime lived in `tradingagents/`. | `tradingagents/graph/**`, `tradingagents/debate/**` | H | all three owners | The map names the runtime modules, the two stubs are facades, and `test/offline/test_structural_fitness.py` enforces it (ADR-007). **Closed**. |
| Evaluation debt | Termination is implemented and tested for the analyst repeat/max-round path and the debate convergence/schema path; the stateful stall/budget signals are tested but not wired into every loop. | `tradingagents/graph/termination.py`, `src/termination_controller.py`, `setup.py` | M | CUI Haoyu | Wire the stateful trigger into the remaining loops; the 7-case regression test stays. **Mitigated / ongoing**. |
| Evaluation debt | The live prose evaluation needs `DEEPSEEK_API_KEY` to produce a result. | `test/live/test_live_prose.py` | M | CUI Haoyu | A faithfulness/relevancy proxy with documented thresholds (>= 0.6) replaces the `NotImplementedError` stub; it skips without a key. **Mitigated**; the live result is still missing. |
| Evaluation debt | The semantic gate's deterministic half measures prompt-constraint retention and guardrail replay, not model-output quality. | `scripts/gate_semantic_eval.py` | M | CUI Haoyu | Stated in the gate output and `docs/eval/fixed-set.json`; the live half is the test above. **Accepted with a named boundary**. |
| CI debt | Branch protection settings are not applied on GitHub. | GitHub settings | H | team lead | `docs/architecture/branch-protection.md` states the required checks and reviews; `.github/CODEOWNERS` requests the reviewers; applying the settings is a manual owner step. **Open (manual)**. |
| CI debt | The test-approval gate falls back to the head manifest on the first commit (BOOTSTRAP). | `scripts/gate_test_approval.py`, `docs/test-approval.yaml` | M | CUI Haoyu | The fallback prints BOOTSTRAP, still requires a named approver and date, and CODEOWNERS requires review on the manifest. **Accepted with a compensating control**. |
| CI debt | mypy checks `src/` only; the baseline and the dynamic graph are treated as `Any`. | `mypy.ini` | M | CUI Haoyu | Scope decision recorded in ADR-009, with the reopen trigger (a defect that escaped because a seam was `Any`). **Accepted**. |
| D5 debt | Two of three member records are not raw session exports: Part B is a retrospective reconstruction, Part C is a supervision summary. | `transcripts/D5-team-session-transcripts.md` | H | Fan Hao, ZhuXuan | The D5 document states the fidelity of each part; the owners must supply raw exports or the submission must declare them as summaries. **Open**. |
| Process debt | D4 records were templates for most of the project. | `docs/review-memo.md`, `docs/debt-register.md`, `docs/bug-diary.md` | M | CUI Haoyu | Populated with the review units and the defects; new work appends a memo. **Mitigated / ongoing**. |
| Environment debt | yfinance's default curl_cffi Chrome fingerprint stalls on `fc.yahoo.com` on this Windows host. | local GUI worker | M | CUI Haoyu | Local-only `requests` session adapter in `gui/worker.py`; not a pipeline change. **Mitigated locally**. |
| Documentation debt | Point 12 was misread as a report section. | `Report.md` | L | CUI Haoyu | Corrected: 12-point font. **Closed**. |
| Documentation debt | `.env.example` omitted the `debate_*` / `context_input_*` keys. | `.env.example` | L | CUI Haoyu | Documented with defaults and the local-estimate caveat (Bug-010). **Closed**. |

## Notes

- The list is deliberately conservative: a debt marked **accepted** names the
  decision that accepts it and the condition that reopens it; it is not a way of
  saying the problem does not exist.
- A debt that changes a safety invariant must update
  `docs/architecture/invariants.md` and add a regression test.
