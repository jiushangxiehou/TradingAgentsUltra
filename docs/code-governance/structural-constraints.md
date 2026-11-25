# Structural Constraints (D3)

> Module organization rules. Each architectural element maps to exactly one
> owning module; new work extends the existing baseline, never replaces it; every
> module and function references the architecture decision and invariant it
> implements. **Submission tree: `dev` (ADR-007).** Reviewed 2026-11-25.

## Module mapping (dev)

| Architectural element | Owning module (runtime) | Project-owned entry point | ADR / requirement | Invariant | Owner |
|---|---|---|---|---|---|
| Context assembler | `tradingagents/graph/context_budget.py` (core), `tradingagents/graph/budgeted_model.py` (graph boundary), `tradingagents/llm_clients/deepseek_context_adapter.py` (CityU transport) | `src/context_assembler.py` (facade) | ADR-001 / REQ-CONTEXT-BUDGET | INV-CONTEXT-BUDGET | ZhuXuan (60377218) |
| Structured debater | `tradingagents/debate/engine.py`, `tradingagents/debate/schemas.py`, `tradingagents/debate/evidence.py`; node wiring in `tradingagents/agents/**`, `graph/conditional_logic.py` | `src/structured_debater.py` (facade) | ADR-002 / REQ-STRUCTURED-DEBATE | — | Fan Hao (60835652) |
| Trace recorder | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | same | ADR-003 / REQ-TRACEABILITY | INV-TRACE-COMPLETENESS | CUI Haoyu (60760270) |
| Guardrail | `src/guardrail.py`, `src/integration/decision_adapter.py`, `src/integration/gate_support.py`, `src/integration/governed_graph.py` | same | ADR-004 / REQ-HARD-GUARDRAIL | INV-GUARDRAIL-ZERO-ESCAPE, INV-RATING-VALIDITY | CUI Haoyu (60760270) |
| Termination controller | `tradingagents/graph/termination.py`; analyst loop wired in `graph/setup.py` | `src/termination_controller.py` (facade) | ADR-005 / REQ-TERMINATION-DISCIPLINE | — | Fan Hao (60835652) — requirement; CUI Haoyu (60760270) — integration |
| Integration composition (**not** an element) | `src/integration/**` | — | ADR-006 (composes ADR-003/004) | — | CUI Haoyu (60760270) |

The facades re-export the runtime; they keep no second copy (ADR-007). The
twenty-four declared baseline differences are listed in
[`docs/architecture/baseline-overrides.md`](../architecture/baseline-overrides.md)
and enforced by `scripts/verify_baseline.py` (ADR-008).

## Rules

1. One architectural element ↔ exactly one owning module (a facade does not
   count as a second owner; it exposes the contract).
2. New work extends the baseline; never replaces an unchanged module without an
   ADR. A pinned file may differ only when ADR-008 declares it.
3. Every module and function references the architecture decision and invariant
   it implements (header docstring: `ADR-xxx`, `REQ-...`, `INV-...`).
4. `src/guardrail.py` and `src/trace_recorder.py` are pure: standard library
   only, no clock, no I/O, no network. Facades and composition may import the
   framework; the pure modules may not.
5. Authority boundaries: the architecture blueprint and the project covenant are
   authoritative.

## Enforcement (not a TODO any more)

| Check | Where |
|---|---|
| Element → module exists, facades export their contract | `test/offline/test_structural_fitness.py` |
| Pure modules import only their allowlist, no clock/UUID | `test/offline/test_structural_fitness.py`, `scripts/check_safety_paths.py` |
| Declared baseline differences match reality | `scripts/verify_baseline.py --strict` (CI) |
| Public API surface of the frozen modules | `docs/architecture/api-surface.json` + `scripts/check_safety_paths.py` |
| Permission model is default-deny and covers the safety files | `scripts/check_safety_paths.py` |

The earlier form of this section said the module-to-element check was a TODO and
that the dev implementations sat "outside the feature-c map". Both statements
were true for the `feature-c` overlay; ADR-007 replaced that map with the dev
tree and this file is now the enforced map.