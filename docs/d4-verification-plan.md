# D4 — Verification Improvement Plan and Execution Record

> **Scope:** the verification governance deliverable (D4) and the blocking-gate
> evidence it feeds (D7). **Submission tree:** `dev` (ADR-007).
> **Status:** executed 2026-11-25; the execution record is §4 below.

## 1. Where D4 stood when this plan started

D4 asks for verification rules, three-tier verification and current QA records.
The repository had the rules and the records, but three things were not true yet:

| Gap | Evidence at the time |
|---|---|
| The structural tier was a TODO | `structural-constraints.md` said "the module-to-element check remains a TODO"; the map pointed at two stubs |
| The behavioural tier did not run | `test/live/test_live_prose.py` raised `NotImplementedError` |
| The gate tier was partial | no test-approval gate, no semantic gate, the AI-use-log gate compared one commit |
| The QA records were thin | review memos covered the old units; no memo for the reconciliation round |

## 2. Design

### 2.1 The three tiers, made concrete

| Tier | Question it answers | Mechanism | Blocking |
|---|---|---|---|
| **Structural** | Does the code match the architecture? | element map fitness test, pure-module import rules, API-surface pin, permission model, baseline verifier | yes (offline + CI) |
| **Regression** | Does anything that worked stop working? | offline suite (deterministic), 9 full-graph E2E, upstream suite | yes |
| **Behavioural** | Is the output still good enough? | guardrail zero-escape replay, prompt-constraint retention, live faithfulness/relevancy proxy >= 0.6 | deterministic half yes; live half needs a key |

### 2.2 Rules kept from D4

1. Every fit criterion has at least one test.
2. Every invariant has at least one test that fails when it is violated.
3. Every test references the requirement/invariant it verifies.
4. Every round runs the prior suites with zero regressions.
5. Offline tests stay deterministic and key-free; live tests carry the keys.

### 2.3 Evidence the plan requires

- a command and its output for every claim (not a recollection);
- a mapping from requirement → implementation → test → monitor;
- a negative test for every gate, because a gate that cannot fail is not a gate;
- a record in `review-memo.md`, `debt-register.md` or `bug-diary.md` for every
  change that affects a requirement, an invariant, a module boundary or a gate.

## 3. Work items and acceptance

| # | Work item | Acceptance | Owner |
|---|---|---|---|
| D4-1 | Structural fitness test | element map, facade contract, pure-module rule, owner IDs, baseline declaration all asserted; a violation fails | CUI Haoyu |
| D4-2 | Gate tests | every gate has a negative and a positive case; the suite passes offline | CUI Haoyu |
| D4-3 | Verification map | requirement → module → test → monitor, with owners; no "somewhere else" row | CUI Haoyu |
| D4-4 | Behavioural tier | deterministic replay blocks in CI; live proxy implemented with documented thresholds | CUI Haoyu / ZhuXuan |
| D4-5 | QA records | a memo for each new review unit; debt statuses updated; new defects recorded | CUI Haoyu |
| D4-6 | Evidence table | the report's verification table quotes commands and outputs | CUI Haoyu |

## 4. Execution record (2026-11-25)

| Item | Result |
|---|---|
| D4-1 | `test/offline/test_structural_fitness.py` — 15 cases incl. element→module, facade exports, pure-module imports, owner student IDs, override completeness, D5 labels and per-member file naming |
| D4-2 | `test/offline/test_gates.py` — 20 cases: approval matching/glob/bootstrap rules, AI-use-log classification, semantic replay with a wrong expectation, impure-module detection, default-allow permission detection, altered-vs-declared baseline consistency, strict verifier exit code |
| D4-3 | `docs/code-governance/verification-constraints.md` rewritten with owners and named tests |
| D4-4 | `scripts/gate_semantic_eval.py` (deterministic replay: prompt constraints 1.00, 9/9 decisions, 0 escapes) and `test/live/test_live_prose.py` (proxy >= 0.6, skips without a key) |
| D4-5 | review memos PR-007/008/009; debt register re-reviewed with accepted/closed/open statuses; bug diary Bug-009…012 |
| D4-6 | `Report.md` §7 and Appendix F quote the commands and results |

### Verification evidence

```text
$ python -m pytest test/offline -m offline -q
476 passed                        (441 prior + 20 gate + 15 fitness)
$ python -m mypy
Success: no issues found in 12 source files
$ python scripts/check_safety_paths.py --quiet
check-safety-paths: PASS (contract, security, API surface, permission)
$ python scripts/gate_semantic_eval.py
semantic-eval: PASS (deterministic replay; live faithfulness/relevancy lives in test/live)
$ python scripts/verify_baseline.py --strict
baseline-verify: PASS (pinned baseline matches; declared differences only)
```

The suite is the authority for the total; the split above is the composition
(441 prior + 20 gate + 14 fitness).

## 5. What this plan does not claim

- The live prose proxy is a proxy: it measures number grounding and term
  overlap, not a semantic judge. The boundary is in the test docstring and the
  debt register.
- The structural tier checks the map, not every internal invariant of every
  module; the guardrail and recorder have their own contract tests.
- Branch protection settings are a GitHub action, not a test; the policy and the
  workflow are in the repository, the settings are an owner step.
