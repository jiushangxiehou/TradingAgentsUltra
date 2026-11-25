# Verification Constraints (D4)

> The verification rules the verification agent applies, the QA records the team
> maintains, and the evidence for each requirement.
> **Submission tree: `dev` (ADR-007).** Reviewed 2026-11-25.

## Rules

1. Every fit criterion in `docs/req/requirements.yaml` has at least one test.
2. Every invariant has at least one test that **fails** when the invariant is
   violated.
3. Every test references the requirement or invariant it verifies.
4. Every new round of work runs all previous rounds' test suites with **zero
   regressions**.
5. A test under `test/` or `tests/` must be approved before the implementation it
   guards is merged (`docs/test-approval.yaml`, D7 gate 1).
6. Every claim in a report quotes the command and its output
   (`.agent/rules.md` covenant 7).

## Three-tier verification

| Tier | Checks | Where |
|---|---|---|
| **Structural** | imports, module boundaries, permissions, element-map fitness, API surface, baseline declaration | `test/offline/test_structural_fitness.py`, `scripts/check_safety_paths.py`, `scripts/verify_baseline.py` |
| **Regression** | offline deterministic suite, 9 full-graph E2E, upstream suite | `pytest test/offline -m offline`, `pytest test/offline/test_integration_end_to_end.py`, `pytest tests -m "not integration"` |
| **Behavioural** | guardrail zero-escape replay, prompt-constraint retention, live faithfulness/relevancy >= 0.6 | `scripts/gate_semantic_eval.py`, `test/live/test_live_prose.py` |

## Test layout

- `test/offline/` — deterministic tests, no API key, must pass in CI.
- `test/live/` — API-dependent tests (LLM + data vendors), require keys; the
  live prose test skips, rather than fails, without a key.
- `tests/` — the pinned baseline's own suite plus the two feature owners' tests
  (`test_context_budget_core.py`, `test_budget_agent_integration.py`,
  `test_debate_opening.py`, `test_structured_agents.py`).

## QA records (D4)

- `docs/review-memo.md` — one memo per review unit; PR-001…PR-009.
- `docs/debt-register.md` — AI-era debt with owner and status.
- `docs/bug-diary.md` — one entry per significant bug; Bug-001…Bug-012.
- `docs/d4-verification-plan.md` — this round's plan and execution record.

## Test-to-requirement mapping (submission tree)

| Requirement | Implementation | Primary tests | Owner / status |
|---|---|---|---|
| REQ-CONTEXT-BUDGET | `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `llm_clients/deepseek_context_adapter.py`; facade `src/context_assembler.py` | `tests/test_context_budget_core.py` (40), `tests/test_budget_agent_integration.py` (13), `test/offline/test_context_budget.py` (5) | ZhuXuan (60377218) — complete |
| REQ-STRUCTURED-DEBATE | `tradingagents/debate/engine.py`, `schemas.py`, `evidence.py`; facade `src/structured_debater.py` | `tests/test_debate_opening.py` (5), `tests/test_structured_agents.py` (35) | Fan Hao (60835652) — complete |
| REQ-TRACEABILITY | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | `test/offline/test_traceability.py` (40), `test_integration_trace.py` (51), E2E (9) | CUI Haoyu (60760270) — complete |
| REQ-HARD-GUARDRAIL | `src/guardrail.py`, `src/integration/decision_adapter.py`, `gate_support.py`, `governed_graph.py` | `test/offline/test_guardrail.py` (39), `test_integration_decision.py` (32), `test_integration_gate.py` (27), E2E | CUI Haoyu — complete |
| REQ-TERMINATION-DISCIPLINE | `tradingagents/graph/termination.py`; facade `src/termination_controller.py`; analyst loop in `setup.py` | `test/offline/test_termination.py` (7); debate termination tests | Fan Hao (60835652) — requirement; CUI Haoyu (60760270) — integration. Repeat/max wired; stall/budget API tested |

### Invariant evidence

| Invariant | Negative test / evidence | Status |
|---|---|---|
| `INV-GUARDRAIL-ZERO-ESCAPE` | each trigger rejects; malformed/config-error cases; a guardrail patched to always pass fails the zero-escape test; full-graph E2E | Complete |
| `INV-RATING-VALIDITY` | legal-rating test and the `REVIEW`-is-never-a-rating test | Complete |
| `INV-TRACE-COMPLETENESS` | every critical link must resolve; no-data placeholders; trace-failure sidecar test | Complete |
| `INV-CONTEXT-BUDGET` | over-cap and unverifiable-count calls block before HTTP; the config contract fails closed | Complete on dev |

## Blocking-gate mapping (D7)

| Gate | Script / workflow job | Negative test |
|---|---|---|
| 1. Test approval | `scripts/gate_test_approval.py` | `test_gates.py::test_unapproved_test_change_fails_the_gate` |
| 2. Static analysis | `ruff`, `python -m mypy`, `pip check` | mypy failure is the negative signal |
| 2b. Safety paths | `scripts/check_safety_paths.py` | `test_gates.py::test_pure_module_with_a_forbidden_import_is_reported` |
| 3. Schema | `scripts/verify_schema.py` | schema violation exits 1 |
| 4. Semantic evaluation | `scripts/gate_semantic_eval.py` | `test_gates.py::test_wrong_expectation_fails_the_replay` |
| 5. Regression | offline suite + upstream suite | any failure |
| 6. AI-use log | `scripts/gate_ai_use_log.py` | `test_gates.py::test_code_change_without_log_fails` |
| Baseline integrity (ADR-008) | `scripts/verify_baseline.py --strict` | `test_gates.py::test_every_altered_pinned_file_is_declared_and_vice_versa` |

## Three-tier status (2026-11-25)

- **Structural:** element map and facades enforced by
  `test/offline/test_structural_fitness.py`; `check_safety_paths` 21/21;
  `verify_baseline.py --strict` PASS on 213 pinned files with 24 declared
  differences; `mypy` clean on 12 source files.
- **Regression:** the offline suite (441 before this round + the gate/fitness
  cases) passes; 9 full-graph E2E pass; the upstream suite is 1,498 passed with
  6 skips on dev.
- **Behavioural:** the deterministic replay passes (prompt retention 1.00, 9/9
  decisions, 0 escapes, model baseline unchanged); the live prose proxy is
  implemented and skips without a key, so a live result is still owed.

## REQ-CONTEXT-BUDGET evidence (feature-z acceptance)

- **Structural:** `Graph` setup installs `BudgetedModel` for the agent
  factories; the adapter is selected by provider/model. Test coverage includes
  tool exchanges, structured schemas, Reflection and checkpoint recovery.
- **Regression:** on merged dev `a8597af` the isolated runs recorded 73 core
  passes and 18 Agent-integration passes; the combined offline run recorded
  1,932 passes with two team placeholders failing, which are now implemented.
- **Behavioural:** SDK Mock HTTP proves final-body identity and zero sends on an
  over-cap request; the paired fixture preserved 2/2 facts and 5/5 standing
  constraints. Real CityU token parity and model-output quality are not claimed.

## Notes

- The debug/GUI run artifacts under `artifacts/` are not tests; the live run is
  evidence in `Report.md` §7.
- A test that only checks the happy path is not evidence for a safety feature;
  the fail-closed cases are the ones that matter.