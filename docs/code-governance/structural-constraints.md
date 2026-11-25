# Structural Constraints (D3)

> Module organization rules. Each architectural element maps to exactly one
> module; new work extends the existing baseline, never replaces it; every
> module and function references the architecture decision and invariant it
> implements. Reviewed 2026-11-25.

## Module mapping

| Architectural element | Implementation | ADR / requirement | Invariant | Status |
|---|---|---|---|---|
| Context assembler | dev: `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `llm_clients/deepseek_context_adapter.py`; team-app: `src/context_assembler.py` stub | ADR-001 / REQ-CONTEXT-BUDGET | INV-CONTEXT-BUDGET | Implemented on dev; not ported to team-app |
| Structured debater | dev: `tradingagents/debate/**`, graph/agent wiring; team-app: `src/structured_debater.py` stub | ADR-002 / REQ-STRUCTURED-DEBATE | — | Implemented on dev; not ported to team-app |
| Trace recorder | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | ADR-003 / REQ-TRACEABILITY | INV-TRACE-COMPLETENESS | Complete (CUI Haoyu) |
| Guardrail | `src/guardrail.py`, `src/integration/decision_adapter.py`, `gate_support.py`, `governed_graph.py` | ADR-004 / REQ-HARD-GUARDRAIL | INV-GUARDRAIL-ZERO-ESCAPE | Complete (CUI Haoyu) |
| Termination controller | `tradingagents/graph/termination.py` (`should_terminate`, `TerminationController`); `src/termination_controller.py` facade; analyst loop wired in `setup.py` | ADR-005 / REQ-TERMINATION-DISCIPLINE | — | Implemented: repeat/max wired; stall/budget API tested |
| Integration composition (**not** an element) | `src/integration/**` | ADR-006 (composes ADR-003/004) | — | Complete (CUI Haoyu) |

## Rules

1. One architectural element ↔ exactly one module.
2. New work extends the baseline; never replaces an unchanged module without an
   ADR.
3. Every module and function references the architecture decision and invariant
   it implements (header docstring: `ADR-xxx`, `REQ-...`, `INV-...`).
4. Authority boundaries: the architecture blueprint and the project covenant are
   authoritative.

## Known drift and enforcement

- The dev feature-f/feature-z implementations live in `tradingagents/` rather
  than the feature-c `src/` boundaries. That is a real module-mapping debt, not
  a documentation typo. The team must either port the code behind the declared
  interfaces or approve a revised element map in an ADR.
- The dev features modify 19 pinned baseline files; the strict
  `scripts/verify_baseline.py --strict` therefore fails on dev. This is recorded
  in `docs/debt-register.md`.
- The structural fitness check is not yet a CI gate. The current automated
  structural checks are the baseline verifier and `ruff`; the module-to-element
  check remains a TODO. Do not claim it is enforced.

> **CUI Haoyu note:** the trace/guardrail/integration rows are mine and are
> implemented in the declared `src/` modules. The context/debate rows are the
> dev owners' implementations and still need the module-boundary decision.
