# ADR-004: Deterministic Decision Guardrail (Safety Boundary)

- **Status:** Accepted
- **Decision owner:** CUI Haoyu (60760270)
- **Date:** 2026-11-24

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

The driver is the project's zero-escape safety boundary. The iteration compared
a prompt-only rule (not deterministic), rating-only checking (leaves size
unchecked), current-book sizing (policy C; a new oversized Buy passes at zero
position), and an explicit execution intent (selected in ADR-006). The selected
gate checks the declared `size_pct`, `short_amount`, available cash and legal
rating; missing or malformed inputs fail closed to `Hold`, and one audit record
is emitted per rejection. The policy decision deliberately keeps the model's
prose as corroboration only. The consequence is a conservative gate that can
reject a legitimate aggressive decision; the reopen condition is a measured
false-rejection rate, with limits configurable rather than silently bypassed.

> **CUI Haoyu note:** I own this element and implemented it in
> `src/guardrail.py`; the declared-intent boundary is ADR-006.