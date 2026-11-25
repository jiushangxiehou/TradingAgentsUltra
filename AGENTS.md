# AGENTS.md — Coding-Agent Governance (D3)

> **This is the single entry point the coding agent reads.** Once the coding
> agent starts, it reads `AGENTS.md` first, then `architecture-blueprint.md`,
> then the artifacts in reading order. It must follow this file and the
> documents it points to. Human-only manual changes to it are tracked via the
> `.agent/rules.md` covenant and review memos.

## 1. Build target

- **Framework:** [TradingAgents](https://github.com/tauricresearch/tradingagents)
  (a LangGraph multi-agent LLM financial trading framework), enhanced to meet
  the five requirements in `docs/req/requirements.yaml`.
- **Language/stack:** Python ≥3.11, LangGraph, LangChain, yfinance, pandas,
  pytest. See `pyproject.toml` upstream for the baseline dependency set.
- **Do not extend VHIS.** VHIS is the lecture reference pattern, not this task.

## 2. Reading order for architecture artifacts

Read in this order before writing code:

1. `AGENTS.md` (this file) — the entry point.
2. `architecture-blueprint.md` — the master constraint document.
3. `docs/architecture/adr/*.md` — architecture decisions (esp. the AI-component
   layered-context design).
4. `docs/architecture/invariants.md` — zero-tolerance invariants.
5. `docs/architecture/trace-matrix.md` — requirement → component → evidence.
6. `docs/architecture/memory-design.md` — cross-session state.
7. `docs/architecture/authority-boundaries.md` (inside blueprint) — advisory vs
   authoritative.
8. `.opencode/rules.md`, `.agent/rules.md` — always-on behavioral rules.
9. `docs/code-governance/structural-constraints.md` + `mcp-tool-manifest.md`.

## 3. Code baseline

- **Extend, never replace.** New work extends the existing baseline; the
  upstream TradingAgents behaviour is the baseline. Do not rewrite modules that
  are unchanged unless an ADR authorises it.
- **Frozen:** the test harness semantics, the data-access contract, and any
  module that an ADR marks as frozen. Changing these requires an architecture
  decision and human approval.

## 4. What is readable / modifiable / frozen

| Path | Status |
|------|--------|
| `src/` | modifiable (under structural constraints) |
| `test/offline/` | modifiable; must stay deterministic |
| `test/live/` | modifiable |
| `AGENTS.md` | readable; changes need review |
| `docs/architecture/*.md` | readable; changes need an ADR |
| `docs/req/requirements.yaml` | readable; changes need an ADR + trace update |
| `.opencode/*`, `.agent/*`, `docs/code-governance/*` | readable; human-only edits |
| `prompts/*.yaml` | modifiable (versioned; bump on change) |

## 5. Module organization

- Each architectural element maps to **exactly one module** (see
  `docs/code-governance/structural-constraints.md`).
- Module names must match architectural elements.
- Every module and function references the architecture decision and invariant
  it implements (see `docs/architecture/trace-matrix.md`).

## 6. Integration contracts between modules

> TODO: Fill these in as modules are defined. Each contract lists the interface,
> the owning module, and the invariant it satisfies.

- `ContextAssembler` → provides compacted context to agents (REQ-CONTEXT-BUDGET).
- `StructuredDebater` → emits schema-validated debate turns (REQ-STRUCTURED-DEBATE).
- `TraceRecorder` → records assertion → evidence links (REQ-TRACEABILITY).
- `Guardrail` → deterministic decision check (REQ-HARD-GUARDRAIL).
- `TerminationController` → self-termination of agent loops (REQ-TERMINATION-DISCIPLINE).

## 7. Verification requirements the generated code must satisfy

- Every fit criterion in `docs/req/requirements.yaml` has at least one test.
- Every invariant has at least one test that **fails** when the invariant is
  violated.
- Every test references the requirement / invariant it verifies.
- Every new round of work runs all previous rounds' test suites with **zero
  regressions**.
- The test layout separates `test/offline/` (deterministic, no API) from
  `test/live/` (API-dependent).
- See `docs/code-governance/verification-constraints.md` and the CI blocking
  gates in `.github/workflows/ci.yml`.

## 8. Authority boundaries

- Advisory vs authoritative: the AI coding agent's suggestions are **advisory**;
  the architecture blueprint and the project covenant (`.agent/rules.md`) are
  **authoritative**. When they conflict, the authoritative artifact wins and the
  agent must stop and surface the conflict rather than silently proceed.
- Changing safety-critical paths requires an architecture decision and human
  approval (see `.agent/rules.md`).