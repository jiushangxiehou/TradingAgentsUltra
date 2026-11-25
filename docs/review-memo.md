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

## PR-006: Termination discipline integration

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** REQ-TERMINATION-DISCIPLINE
- **Commit(s):** dev termination integration (this review unit)
- **Spec alignment:** Adds the missing self-termination signal required by the
  requirement and ADR-005: max tool rounds, repeated tool-call rounds, and a
  stateful stall/budget controller. The analyst loop wraps up with the existing
  WRAP_UP path; the debate engine's convergence/schema termination remains in
  ADR-002.
- **Architecture alignment:** `tradingagents/graph/termination.py` owns the
  runtime implementation because the graph nodes consume it; the project-owned
  `src/termination_controller.py` is a facade, not a duplicate. The module map
  now documents this explicitly instead of calling the element missing.
- **Code & test quality:** `test/offline/test_termination.py` has 7 cases
  (repeat, distinct, cap, budget, stall, reset, invalid threshold). The offline
  suite is 441 passed; the upstream suite is 1,498 passed, 6 skipped; ruff
  passes on the changed files.
- **Security & efficiency:** The loop cannot run forever on a repeated tool
  call; a stall/budget observation is explicit and logged. The controller does
  not raise on malformed messages and does not terminate on an empty round.
- **Operational metadata:** The analyst loop logs the termination trigger;
  the stateful stall/budget API is tested but not yet wired into every loop.
- **Verdict:** **APPROVE**; full per-loop stall/budget wiring is a follow-up,
  not a claim.

## PR-007: Submission-tree reconciliation (ADR-007)

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** D8, REQ-CONTEXT-BUDGET, REQ-STRUCTURED-DEBATE, REQ-TERMINATION-DISCIPLINE
- **Review unit:** ADR-007, ADR-008, facades, verifier relaxation, element map.
- **Spec alignment:** D8 is delivered by `dev`, not by the `feature-c` overlay;
  the element map now names the modules that execute.
- **Architecture alignment:** `src/context_assembler.py` and
  `src/structured_debater.py` re-export the runtime (facade pattern from
  ADR-005). No second copy of the implementations exists.
- **Code & test quality:** `test/offline/test_structural_fitness.py` enforces the
  map, owner student IDs, the pure-module rule and the declared overrides; the
  offline suite passes unchanged apart from the new tests.
- **Security & efficiency:** the guardrail and recorder modules are untouched by
  this unit; the facades add an import path, not a runtime path.
- **Operational metadata:** ADR-007/008 written; `docs/architecture/baseline-overrides.md`
  and `scripts/baseline-overrides.json` added; README/AGENTS/blueprint/trace
  matrix/structural constraints/invariants updated; AI-use log entries 011–012.
- **Verdict:** **APPROVE** (with the standing note that the 19 pinned overrides
  remain a declared deviation, not a restoration).

## PR-008: D7 gates, type check and baseline integrity

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** D4, D7 (gates 1, 2, 4, 6 + baseline), ADR-009
- **Review unit:** `.github/workflows/ci.yml`, `scripts/gate_*.py`,
  `scripts/check_safety_paths.py`, `scripts/safety_checks.py`, `mypy.ini`,
  `docs/test-approval.yaml`, `docs/eval/fixed-set.json`, `test/offline/test_gates.py`.
- **Spec alignment:** six blocking gates plus baseline integrity; the test-approval
  gate reads the manifest at the base revision; the semantic gate replays a fixed
  set; the AI-use-log gate compares base..head.
- **Architecture alignment:** the gates are `scripts/` tooling; they do not add a
  runtime element. The type check is scoped to the project-owned modules.
- **Code & test quality:** every gate has negative tests (an unapproved test
  fails, an undeclared baseline change fails, a wrong eval expectation fails).
  `python -m mypy` reports no issues in 12 files; `check_safety_paths` is 21/21.
- **Security & efficiency:** the safety-path checks are the contract/security/
  API-surface/permission half of gate 2; the typing-only touch to the trace
  boundary is recorded in ADR-009 and covered by the existing tests.
- **Operational metadata:** branch-protection policy and CODEOWNERS added; PR
  template mirrors this memo; README gate table updated; AI-use log entry 011.
- **Verdict:** **APPROVE**; branch-protection *settings* remain a manual owner
  step and are recorded as such.

## PR-009: D4 plan, D5 consolidation and D6 integration

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** D4, D5, D6
- **Review unit:** `docs/d4-verification-plan.md`, `docs/code-governance/verification-constraints.md`,
  `transcripts/D5-team-session-transcripts.md`, `transcripts/README.md`,
  `Report.md` §1/§6, `docs/context-budget-reflection.md`,
  `transcripts/60377218-ZhuXuan-supervision-summary.md`,
  `transcripts/60835652-FanHao-session-record.md`.
- **Spec alignment:** D5 is one labelled document with each member's part; D6 is
  one report with each member's contribution and 300–500-word reflection.
- **Architecture alignment:** documentation only; no runtime change.
- **Code & test quality:** `test_structural_fitness` asserts the consolidated D5
  file exists and labels all three members; the D4 plan is the verification map.
- **Security & efficiency:** no secrets were introduced; the transcripts remain
  sanitised.
- **Operational metadata:** the two members' identities and owned elements are
  recorded in ADR-001/002, `AGENTS.md`, the report and the D5 document; the
  numeric contribution weight is the only field left to the team.
- **Verdict:** **APPROVE** for the consolidation; the two non-raw D5 parts are
  declared and tracked in the debt register.


## PR-010: Section 5 structure conformance

- **Author:** OpenCode coding agent (supervised by CUI Haoyu)  |  **Reviewer:** CUI Haoyu  |  **Date:** 2026-11-25
- **Linked requirement(s):** D5, D6, D8 (structure), D4 (records)
- **Review unit:** transcripts naming, transcripts/README.md, README.md,
  src/README.md, test/offline/test_structural_fitness.py.
- **Spec alignment:** every member now has a <student-id>-<name>.md transcript
  (ZhuXuan renamed, Fan Hao added), README documents the full suite and where
  the application source lives, and the tree matches Section 5 of the brief.
- **Architecture alignment:** documentation only; src/README.md restates the
  ADR-007 element map and adds no module boundary.
- **Code & test quality:** the structural fitness test asserts the per-member
  naming; 476 offline tests pass; ruff, mypy, schema, baseline and the gate
  scripts are green.
- **Security & efficiency:** no secrets; the two member records are the same
  declared non-raw records, not new evidence.
- **Operational metadata:** AI-use log entry 015; report, D4 plan and test
  counts updated (476 tests, 15 log entries).
- **Verdict:** **APPROVE**.

<!-- Append new memos below. No GitHub PRs were used; the review unit is the
feature commit or integration merge. -->
