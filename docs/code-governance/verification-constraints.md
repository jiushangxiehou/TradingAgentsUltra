# Verification Constraints (D4)

> The verification rules the verification agent applies, and the QA records the
> team maintains.

## Rules
1. Every fit criterion in `docs/req/requirements.yaml` has at least one test.
2. Every invariant has at least one test that **fails** when the invariant is
   violated.
3. Every test references the requirement or invariant it verifies.
4. Every new round of work runs all previous rounds' test suites with **zero
   regressions**.

## Three-tier verification
- **Structural:** imports, module boundaries, permissions, architectural fitness
  functions (e.g. module ↔ architectural element map).
- **Regression:** all prior suites pass (zero regressions).
- **Behavioral:** quality thresholds — faithfulness / relevancy ≥ 0.6 for the
  AI-generated explanation layer; zero safety escapes past the guardrail.

## Test layout
- `test/offline/` — deterministic tests, no API key, must pass in CI.
- `test/live/` — API-dependent tests (LLM + data vendors), require keys.

## QA records (D4)
- `docs/review-memo.md` — one per PR (spec/architecture alignment, code & test
  quality, operational metadata, security & efficiency, verdict).
- `docs/debt-register.md` — AI-era technical debt categories.
- `docs/bug-diary.md` — one entry per significant bug.

## Concrete test-to-requirement mapping (reviewed 2026-11-25)

The dev branch contains the complete implementations for context budgeting and
structured debate; the feature-c/team-app tree still carries the original `src/`
stubs for those elements. The mapping below records both facts rather than
pretending the trees are identical.

| Requirement | Implementation | Primary tests | Status |
|---|---|---|---|
| REQ-CONTEXT-BUDGET | dev: `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `llm_clients/deepseek_context_adapter.py`; team-app: `src/context_assembler.py` stub | `tests/test_context_budget_core.py`, `tests/test_budget_agent_integration.py`, `tests/news_context_budget_fixtures.py`; `test/offline/test_context_budget.py` now covers the strict config contract (5 cases) | **Implemented/tested on dev; feature-c stub** |
| REQ-STRUCTURED-DEBATE | dev: `tradingagents/debate/**`, conditional logic, researcher/risk wiring; team-app: `src/structured_debater.py` stub | `tests/test_debate_opening.py`, `tests/test_structured_agents.py`, graph E2E (dev); no dedicated team-app test | **Implemented/tested on dev; feature-c stub** |
| REQ-TRACEABILITY | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | `test/offline/test_traceability.py`, `test/offline/test_integration_trace.py`, `test/offline/test_integration_end_to_end.py` | **Complete (CUI Haoyu)** |
| REQ-HARD-GUARDRAIL | `src/guardrail.py`, `src/integration/decision_adapter.py`, `gate_support.py`, `governed_graph.py` | `test/offline/test_guardrail.py`, `test_integration_decision.py`, `test_integration_gate.py`, `test_integration_end_to_end.py` | **Complete (CUI Haoyu)** |
| REQ-TERMINATION-DISCIPLINE | `tradingagents/graph/termination.py` (`should_terminate`, `TerminationController`) + `src/termination_controller.py` facade; analyst loop wired in `setup.py` | `test/offline/test_termination.py` (7 cases: repeat, distinct, cap, budget, stall, reset, invalid threshold); debate tests | **Complete for repeat/max + controller; stall/budget API tested, full per-loop wiring follow-up** |

### Invariant evidence

| Invariant | Negative test / evidence | Status |
|---|---|---|
| `INV-GUARDRAIL-ZERO-ESCAPE` | each trigger has a rejection test; malformed/config-error tests; full-graph E2E | Complete |
| `INV-RATING-VALIDITY` | legal-rating test and `REVIEW`-never-a-rating test | Complete |
| `INV-TRACE-COMPLETENESS` | every report must be backed by evidence; no-data placeholders; trace-failure sidecar test | Complete |

### Three-tier status

- **Structural:** `scripts/verify_baseline.py --strict` passes in root layout
  (208 pinned + 5 overrides); `ruff check src test` passes for the project code.
  A module-to-element fitness check is still a TODO; the dev/team-app module
  mapping drift is recorded in the debt register.
- **Regression:** `test/offline` 441 passed (429 core + 12 termination/budget
  cases); 9 full-graph E2E passed; the dev upstream suite has 1,498 passing
  tests with six skips and no persistent failures when run from a
  project-writable directory.
- **Behavioral:** the threshold remains faithfulness/relevancy ≥ 0.6, but
  `test/live/test_live_prose.py` is still a `NotImplementedError` stub and the
  semantic-evaluation CI gate is absent. This is the main unmet D4/D7 item.

## REQ-CONTEXT-BUDGET evidence (feature-z acceptance)

- **Structural:** Graph setup installs [BudgetedModel](../../tradingagents/graph/budgeted_model.py)
  for the existing agent factories. Test coverage includes tool exchanges,
  structured schemas, Reflection and checkpoint recovery. Case identifiers
  are linked in the [trace matrix](../architecture/trace-matrix.md#req-context-budget-evidence).
- **Regression:** Merged dev `a8597af236bbedaa862d7a3a3c1a7d0d2a9984ae` was
  tested in a network-isolated environment with the following invocations.

  ```bash
  python -m pytest -q -p no:cacheprovider -m "not live and not integration" tests/test_context_budget_core.py test/offline/test_context_budget.py
  python -m pytest -q -p no:cacheprovider -m "not live and not integration" tests/test_budget_agent_integration.py
  python -m pytest -q -p no:cacheprovider -m "not live and not integration" test/offline tests
  ```

  The first command recorded 73 core passes and the team's unimplemented
  `test_context_within_budget` placeholder failed with `NotImplementedError`.
  The second recorded 18 passes. The third recorded 1932 passes, 2 failures,
  1 skip, 1 deselection and 100 passing subtests. Its second failure was the
  team's `test_terminates_on_repeat` placeholder. The existing CI offline
  marker selection does not cover the budget files in `tests/`; the commands
  above record direct evidence, without claiming a CI change.
- **Behavioral:** SDK Mock HTTP proves final-body identity and zero sends on
  an over-cap request. The paired fixture preserved 2/2 facts and 5/5 standing
  constraints. This evidence concerns synthetic input faithfulness and local
  estimates. The model output quality gate and provider token parity were not
  run in this acceptance.

> **CUI Haoyu note:** the guardrail and traceability rows and their negative
> tests are mine and were verified locally. The context-budget evidence is the
> feature-z owner's acceptance run; it is recorded here as team evidence, not
> as my test result. I added the termination controller/test integration and
> the offline context-budget config test; the historical feature-z acceptance
> above predates those two fill-ins.
