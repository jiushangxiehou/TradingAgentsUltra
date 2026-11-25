# ADR-004: Deterministic Decision Guardrail (Safety Boundary)

- **Status:** Proposed
- **Decision owner:** (fill in)
- **Date:** (fill in)

## Context
The AI produces the final trade rating with no deterministic post-check; this is
a financial-decision domain, so AI output must be constrained by deterministic
code (a safety-relevant boundary per the project requirement).

## Decision
Introduce a `Guardrail` that hard-checks every decision before execution: single
position ≤ 10% of portfolio value; short ≤ available cash; rating ∈ the legal
5-tier set, else fall back to REVIEW/HOLD. Zero tolerance (no escape).

## Alternatives considered
- No guardrail (baseline) — unsafe.
- Soft prompt-based boundary — not enforced deterministically.

## Consequences
- Supports REQ-HARD-GUARDRAIL (invariant, zero escape).
- Conservative guardrail may reject a legitimate aggressive decision; limits are
  configurable and rejection path logs an audit record.

## Reopen conditions
A measured false-rejection rate is too high → tune limits; guardrail limits are
configurable.

## Architectural design process
(TODO.)