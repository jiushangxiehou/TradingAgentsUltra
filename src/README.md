# `src/` — the project-owned governance layer (D8 mapping)

> The submission tree is the pinned TradingAgents 0.7.1 baseline at the
> repository root. `src/` is **not** the whole application: it is the layer this
> project owns, and it maps one-to-one onto the architectural elements. See
> [ADR-007](../docs/architecture/adr/007-dev-submission-element-map.md) for the
> decision and [`docs/code-governance/structural-constraints.md`](../docs/code-governance/structural-constraints.md)
> for the enforced map.

| Architectural element | Owning runtime module(s) | Project-owned entry point |
|---|---|---|
| Context assembler | `tradingagents/graph/context_budget.py`, `tradingagents/graph/budgeted_model.py`, `tradingagents/llm_clients/deepseek_context_adapter.py` | `src/context_assembler.py` (facade) |
| Structured debater | `tradingagents/debate/engine.py`, `schemas.py`, `evidence.py`; node wiring in `tradingagents/agents/**` | `src/structured_debater.py` (facade) |
| Trace recorder | — (this module is the implementation) | `src/trace_recorder.py` + `src/integration/trace_adapter.py` |
| Guardrail | — (this module is the implementation) | `src/guardrail.py` + `src/integration/{decision_adapter,gate_support,governed_graph}.py` |
| Termination controller | `tradingagents/graph/termination.py`; analyst loop in `tradingagents/graph/setup.py` | `src/termination_controller.py` (facade) |

**Composition, not an element:** `src/integration/` wires the guardrail and the
trace recorder into the pinned pipeline (ADR-006). It is deliberately not a
sixth element.

**Purity rule:** `src/guardrail.py` and `src/trace_recorder.py` are pure —
standard library only, no clock, no I/O, no network. The facades and
`src/integration/` may import the framework. `test/offline/test_structural_fitness.py`
and `scripts/check_safety_paths.py` enforce this boundary.

**What lives outside `src/`:** the rest of the application (`tradingagents/`),
its CLI (`cli/`), the pinned baseline tests (`tests/`), the project tests
(`test/`), the deliverable documents (`docs/`), the gate tooling (`scripts/`)
and the D1/D9 artifacts at the root.
