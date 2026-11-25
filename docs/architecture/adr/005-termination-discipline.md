# ADR-005: Self-Termination Discipline

- **Status:** Proposed (implementation missing)
- **Decision owner:** unassigned (to confirm)
- **Date:** 2026-11-25

## Context
Agent loops terminate only on a turn counter; no stall / repeat / budget
detection, so a model can regenerate near-identical positions and burn tokens.

## Decision
Adopt a `TerminationController` that lets each loop stop itself: terminate on
consecutive repeats ≥ REPEAT_THRESHOLD (default 3), stalled progress, or budget
exhaustion, always logging the trigger. Hard cap ties to max tool rounds.

## Alternatives considered
- Turn-count only (baseline) — deadlock-prone.
- No termination — unbounded cost.

## Consequences
- Supports REQ-TERMINATION-DISCIPLINE.
- Risk of premature stop; mitigated by a configurable threshold + audit trail.

## Reopen conditions
Too many premature terminations → calibrate the threshold.

## Architectural design process

The driver is the baseline loop's turn-count-only termination: a model can repeat
near-identical positions and burn tokens. Candidates were turn-count only
(deadlock-prone), no termination (unbounded cost), and a controller with
repeat/stall/budget triggers (selected in principle). The current tree has only
the `REPEAT_THRESHOLD` constant and a `test/offline/test_termination.py` stub;
there is no controller, no trigger log and no passing test. This ADR therefore
remains **Proposed**, not Accepted. The consequence is a real D8 gap; the
reopen condition is the implementation review, not a threshold experiment.

> **CUI Haoyu note:** this is deliberately left unimplemented; the existing dev
> code does not provide a termination controller to document as complete.