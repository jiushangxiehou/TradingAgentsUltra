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

(TODO: add the concrete test-to-requirement mapping; enforce in CI.)

## REQ-CONTEXT-BUDGET evidence

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
