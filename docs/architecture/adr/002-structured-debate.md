# ADR-002: Structured Eliminative Debate

- **Status:** Accepted
- **Decision owner:** feature-f owner (to confirm)
- **Date:** 2026-11-25

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

The driver is the baseline debate's free-form prose: it is bounded only by a
round counter and cannot demonstrate convergence. Candidates were the baseline
free-form debate (flexible, not convergible), a fixed round cap (predictable,
content-blind), and a schema-validated turn with an evidence reference and an
early-termination rule (selected). The dev implementation in
`tradingagents/debate/engine.py` adds `DebateTurn`/`TurnAudit` schemas, evidence
items, turn-level validation and a termination decision; it defaults to shadow
mode so the original round limit is preserved until the policy is approved. The
consequence is an auditable, cheaper debate with a constrained template; the
reopen condition is a debate that stops before a meaningful exchange.

> **CUI Haoyu note:** implementation view reconstructed from the dev branch;
> the feature-f owner should confirm the final module placement.