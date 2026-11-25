# Review Memos (D4)

> One memo per review unit. The project used feature branches plus a `dev`
> integration branch rather than GitHub pull requests, so the review units
> below are the feature-c commits and the dev merge commits. Each memo covers
> spec alignment, architecture alignment, code/test quality, operational
> metadata, and ends in a verdict.

## PR-001: feature-c project overlay and guarded CLI

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** REQ-HARD-GUARDRAIL, REQ-TRACEABILITY
- **Commit(s):** `b3d2e1c`, `f27790b`, `1f32c0a`, `1bce89f`
- **Spec alignment:** Adds the machine-readable requirements (D1), architecture
  artifacts (D2), governance (D3), offline tests (D4), and the guarded CLI. The
  declared execution intent (`size_pct`, `short_amount`, portfolio cash) is
  required; a missing input fails closed to `Hold`.
- **Architecture alignment:** `src/guardrail.py` and `src/trace_recorder.py` are
  the two owned elements; `src/integration/**` is composition, not a new
  element (ADR-006). The pinned baseline is not replaced; the CLI entry wraps
  `cli.run.TradingAgentsGraph`.
- **Code & test quality:** 429 deterministic offline tests and 9 full-graph
  end-to-end tests pass. Ruff and the requirements schema pass. The gate has
  negative tests for each trigger and a full-graph test with real LangGraph.
- **Security & efficiency:** The gate is fail-closed; `Hold` is the documented
  fallback; no key is written to logs or state. Trace evidence is run-level
  (G1), so parallel analysts do not get false per-thread attribution.
- **Operational metadata:** Baseline root layout: 208 pinned files + 5 declared
  overrides; earlier vendor layout: 213/213. CI `feature-c` run passed.
- **Verdict:** **APPROVE**

## PR-002: root-layout migration, baseline verifier and CI repair

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** REQ-HARD-GUARDRAIL, REQ-TRACEABILITY, D7 governance
- **Commit(s):** `1f32c0a`, `1bce89f`, `6aaae7e`
- **Spec alignment:** Moves the project to the root layout required by the
  feature-c repository, documents the five project-owned overrides, and makes
  the blocking-gate workflow run on the actual branches.
- **Architecture alignment:** The pinned baseline remains the package root;
  the project additions stay in `src/`, `test/`, `docs/`, and the integration
  package. No baseline file is silently replaced.
- **Code & test quality:** `scripts/verify_baseline.py` auto-detects vendor vs
  root layout; root mode verifies 208 pinned files and reports the five
  overrides separately. `pythonpath=.` fixes the CI console-script import
  failure. `ruff` and schema checks pass.
- **Security & efficiency:** The baseline gate is a clean-tree check; the
  `__pycache__` sequencing issue was found during audit and the check was rerun
  after cleaning. The AI-use log entry 008 records the CI/style changes.
- **Operational metadata:** Screenshot/CLI help verified; full offline suite
  429 passed; upstream suite collected 1,414 tests in the current tree.
- **Verdict:** **APPROVE** (with the standing baseline-drift caveat for dev;
  see debt register)

## PR-003: dev integration of feature-f (structured debate)

- **Author:** feature-f owner  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** REQ-STRUCTURED-DEBATE
- **Commit / merge:** `a871245` → `1cedaec`
- **Spec alignment:** Adds the structured debate engine, evidence items, schema
  models, conditional logic and graph wiring. The debate remains opt-in via
  config and shadow mode; it does not silently replace the existing round
  limit.
- **Architecture alignment:** Implementation lives in `tradingagents/debate/`
  and the agent/graph files. This is a dev integration; it does not follow the
  feature-c `src/structured_debater.py` module boundary and therefore creates a
  documented module-mapping debt.
- **Code & test quality:** The merge is clean; the full dev offline suite plus
  upstream suite pass. There is no dedicated feature-f test file in the
  branch, so the existing graph/agent tests and the end-to-end suite are the
  evidence.
- **Security & efficiency:** No new external data path; debate termination is
  shadow-mode by default, preserving the baseline round limit until the policy
  is approved.
- **Operational metadata:** Merge commit `1cedaec`; no conflict. The dev branch
  changes 19 pinned baseline files in total when combined with feature-z; the
  baseline verifier therefore fails on dev and needs an explicit ADR or port.
- **Verdict:** **APPROVE** for integration; **CHANGES REQUIRED** before strict
  baseline submission (module placement/ADR)

## PR-004: dev integration of feature-z (context budget)

- **Author:** feature-z owner  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** REQ-CONTEXT-BUDGET
- **Commit / merge:** `f20c6c9`, `3313ad0`, `7de8935` → `a9d23ec`
- **Spec alignment:** Adds the token-budget core, budgeted model wrapper,
  DeepSeek adapter, all-agent integration, and acceptance documents. The
  budget is disabled when no cap is configured, preserving baseline behaviour.
- **Architecture alignment:** Implementation lives in
  `tradingagents/graph/context_budget.py`, `budgeted_model.py`,
  `deepseek_context_adapter.py`, and graph/setup wiring, rather than the
  feature-c `src/context_assembler.py` boundary. This is the main architecture
  drift item; the runtime behaviour is complete on dev.
- **Code & test quality:** `tests/test_context_budget_core.py` (1,297 lines),
  `tests/test_budget_agent_integration.py` (587 lines) and fixtures pass on dev.
  The full dev suite reported 1,496 passed, 6 skipped and two
  environment-specific `PermissionError` cases in Windows Temp; both pass when
  rerun from a project-writable directory.
- **Security & efficiency:** The budget is a real token cap; unsupported
  provider paths block calls instead of sending unbounded context. No key is
  logged.
- **Operational metadata:** Merge commit `a9d23ec`; no conflict. Baseline drift
  and module-mapping debt recorded.
- **Verdict:** **APPROVE** for runtime; **CHANGES REQUIRED** for the
  architecture/baseline reconciliation

## PR-005: publish D5 transcripts and merge into dev

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** D5, REQ-HARD-GUARDRAIL, REQ-TRACEABILITY
- **Commit / merge:** `ebae615` → `a8597af`
- **Spec alignment:** Publishes the seven annotated session transcripts and
  removes the `transcripts/` ignore rule. The files are the D5 evidence for the
  supervised pipeline.
- **Architecture alignment:** Documentation/evidence only; no runtime change.
- **Code & test quality:** Secret scan of the transcripts found no API keys;
  the feature-c and dev CI runs passed after the publish.
- **Security & efficiency:** The repository is public, so the transcripts are
  now public. This was explicitly requested; the old commits still contain the
  earlier local-only history and would require a history rewrite to purge.
- **Operational metadata:** 8 files, 25,551 lines, 1.53 MB; `feature-c` CI
  success; `dev` merge CI success.
- **Verdict:** **APPROVE**

<!-- Append new memos below. No GitHub PRs were used; the review unit is the
feature commit or integration merge. -->
