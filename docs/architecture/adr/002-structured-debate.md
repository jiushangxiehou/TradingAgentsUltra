# ADR-002: Structured Eliminative Debate

- **Status:** Proposed
- **Decision owner:** (fill in)
- **Date:** (fill in)

## Context
The baseline bull/bear debate is free-form prose bounded only by round count; it
is unstructured and consumes tokens without guaranteed convergence.

## Decision
Replace the free-form debate with a `StructuredDebater` that emits per-round,
schema-validated turns exposing four forced fields — claim / evidence_reference
/ counter_argument / round_conclusion — and permits early termination when the
positions converge within a divergence threshold (default: converges at a
configurable bound; minimum-rounds guard default 1).

## Alternatives considered
- Free-form (baseline) — flexible but not convergible.
- Fixed round cap only — no content-based stop.

## Consequences
- Supports REQ-STRUCTURED-DEBATE; debate is auditable and cheaper.
- Template constrains fluency; mitigated by the evidence_reference field.

## Reopen conditions
A debate that frequently stops before a meaningful exchange → raise the
divergence threshold or minimum rounds.

## Architectural design process
(TODO: add ADD iteration — drivers → candidates → selection → consequence.)