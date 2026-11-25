# Structural Constraints (D3)

> Module organization rules. Each architectural element maps to exactly one
> module; new work extends the existing baseline, never replaces it; every
> module and function references the architecture decision and invariant it
> implements.

## Module mapping (seed)
| Architectural element | Module (in `src/`) | ADR / requirement | Invariant |
|-----------------------|--------------------|-------------------|-----------|
| Context assembler | `src/context_assembler.py` | ADR-001 / REQ-CONTEXT-BUDGET | INV-CONTEXT-BUDGET |
| Structured debater | `src/structured_debater.py` | ADR-002 / REQ-STRUCTURED-DEBATE | — |
| Trace recorder | `src/trace_recorder.py` | ADR-003 / REQ-TRACEABILITY | INV-TRACE-COMPLETENESS |
| Guardrail | `src/guardrail.py` | ADR-004 / REQ-HARD-GUARDRAIL | INV-GUARDRAIL-ZERO-ESCAPE |
| Termination controller | `src/termination_controller.py` | ADR-005 / REQ-TERMINATION-DISCIPLINE | — |
| Integration composition (**not** an element) | `src/integration/**` | ADR-006 (composes ADR-003/004) | — |

## Rules
1. One architectural element ↔ exactly one module.
2. New work extends the baseline; never replaces an unchanged module without an ADR.
3. Every module and function references the architecture decision and invariant
   it implements (header docstring: `ADR-xxx`, `REQ-...`, `INV-...`).
4. Authority boundaries: architecture blueprint and covenant are authoritative.

(TODO: expand as modules are built; enforce via a structural fitness check in CI.)