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