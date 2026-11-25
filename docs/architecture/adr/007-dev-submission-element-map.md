# ADR-007: The Dev Submission Tree Is the Element Map

- **Status:** Accepted
- **Decision owner:** CUI Haoyu (60760270), team lead
- **Date:** 2026-11-25
- **Amends:** ADR-001 (module placement), ADR-002 (module placement and field mapping)
- **Related:** ADR-005 (facade precedent), ADR-006 (composition, not an element), ADR-008 (declared baseline overrides)

## Context

Two facts contradicted the architecture document set:

1. **The submission tree is `dev`.** D8 asks for the source and tests of the
   application; the enhanced application is the `dev` tree of
   `team-app-dev`, where the context-budget and structured-debate
   implementations live. The `feature-c` overlay is historical: it is the
   branch that added D1–D4 content and the guardrail/trace integration.
2. **The element map pointed at placeholders.** `docs/code-governance/structural-constraints.md`,
   `docs/architecture/trace-matrix.md`, `.agent/rules.md`-covered checks and
   `AGENTS.md` all mapped the context assembler to `src/context_assembler.py`
   and the structured debater to `src/structured_debater.py`. On `dev` both
   files were stubs that raised `NotImplementedError` (or declared a field-name
   list), while the runtime used `tradingagents/graph/context_budget.py`,
   `tradingagents/graph/budgeted_model.py`,
   `tradingagents/llm_clients/deepseek_context_adapter.py` and
   `tradingagents/debate/**`.

The debt register already recorded this as "architecture debt — runtime modules
do not match the feature-c element map". Leaving it open means every claim in
the trace matrix about those two elements is false, and a reviewer checking
"one element ↔ one module" finds a dead file instead of the code that runs.

## Decision

### 1. The submission tree is `dev` (root layout)

D8 is satisfied by `team-app-dev` on `dev`, not by the `feature-c` overlay.
The pinned 0.7.1 baseline is the repository root; the project's additions live
in `src/`, `test/`, `docs/`, `scripts/`, `prompts/`, `transcripts/` and
`gui/`. The earlier vendor layout and the `feature-c` stubs stay in history as
the record of how the work was sequenced; they are not the deliverable.

### 2. The element map follows the runtime

| Element | Owning module (dev) | Project-owned entry point |
|---|---|---|
| Context assembler | `tradingagents/graph/context_budget.py` (core), `tradingagents/graph/budgeted_model.py` (graph boundary), `tradingagents/llm_clients/deepseek_context_adapter.py` (CityU transport) | `src/context_assembler.py` (facade) |
| Structured debater | `tradingagents/debate/engine.py`, `schemas.py`, `evidence.py`; node wiring in `tradingagents/agents/**` and `tradingagents/graph/conditional_logic.py` | `src/structured_debater.py` (facade) |
| Trace recorder | `src/trace_recorder.py` + `src/integration/trace_adapter.py` | same |
| Guardrail | `src/guardrail.py` + `src/integration/{decision_adapter,gate_support,governed_graph}.py` | same |
| Termination controller | `tradingagents/graph/termination.py` + `src/termination_controller.py` (facade) | same |

The facades re-export the runtime; they keep no second copy. This is the
pattern ADR-005 established for the termination controller: the module the graph
consumes owns the behaviour, and `src/` exposes the stable project-owned name
that tests, reviewers and the element map refer to.

### 3. The two stubs are retired, not left to rot

`src/context_assembler.py` and `src/structured_debater.py` now re-export the
runtime (with `build_context` as the compatibility entry point for the
assembler) and document the layering. Nothing imports them yet; they exist so
the architecture artifact and the code agree, and so a reviewer has one
importable name per element.

### 4. REQ-STRUCTURED-DEBATE field mapping is recorded

The requirement names four fields; the implemented schema is typed and richer.
The mapping is now part of ADR-002 ("Field mapping as implemented") and is
repeated in `src/structured_debater.py`:

| Requirement field | Implemented field |
|---|---|
| claim | `DebateClaim.statement` |
| evidence_reference | `DebateClaim.evidence_refs` (ids from the evidence catalog) |
| counter_argument | `DebateRebuttal.target_claim_id` + `argument` |
| round_conclusion | `DebateTurn.thesis` + `round` + `changed_position` |

## Alternatives considered

- **Port the dev implementations into `src/`.** Rejected for this submission:
  it means copying ~1.6k lines away from the call sites that import them (the
  graph, the agent factories, the router), then re-wiring every import — a
  large change with no behavioural gain, and a second copy that can diverge.
- **Keep the stubs and leave the map as documentation of intent.** Rejected:
  the map would still describe code that does not run; the "one element ↔ one
  module" check cannot be enforced, and the debt register entry stays open
  forever.
- **Re-document only, without facades.** Rejected: a reviewer could no longer
  import the element by its declared name, and the structural fitness test would
  have nothing to check.
- **Declare the pinned files pristine and pretend.** Rejected: they are not
  (ADR-008 declares the 19 real differences instead).

## Consequences

- The element map, the trace matrix, `AGENTS.md` and the blueprint now describe
  the code that executes on `dev`.
- The module-mapping debt is closed; the remaining known drift is the declared
  baseline override set (ADR-008), not a silent lie.
- Because the facades import the framework, the "pure module" import rule now
  applies precisely to `src/guardrail.py` and `src/trace_recorder.py`; a
  structural test enforces that boundary instead of a blanket rule.
- The `feature-c` element map remains in history; the report records the
  sequencing honestly.

## Reopen conditions

- **R-1** The team later moves a runtime implementation into `src/` (for
  example to keep the baseline pristine) — the table above changes, and the
  facades either grow into the implementation or are replaced.
- **R-2** The pinned baseline is upgraded — re-verify the call sites, the
  facades' exports and ADR-008.
- **R-3** D8 is re-scoped to require an unmodified baseline — ADR-008 is
  withdrawn and the port alternative above becomes the plan.
- **R-4** A facade is imported by production code and the indirection becomes a
  real cost — decide whether it is the contract or a convenience.

## Verification

- `test/offline/test_structural_fitness.py` asserts each element's declared
  modules exist, the facades export their contract, only the pure modules are
  framework-free, and the declared overrides match the verifier's manifest.
- `python -m src.context_assembler`-level import check: `python -c "import
  src.context_assembler, src.structured_debater"` succeeds in the project venv.
- `pytest test/offline -m offline -q` passes unchanged (441 cases at the time
  of this decision; the count grows with the fitness tests).
- `python scripts/verify_baseline.py --strict` passes with the declared
  differences (ADR-008).
