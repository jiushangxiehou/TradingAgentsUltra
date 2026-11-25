# ADR-005: Self-Termination Discipline

- **Status:** Accepted
- **Requirement owner:** Fan Hao (60835652) — REQ-TERMINATION-DISCIPLINE and its
  story points (repeat threshold, budget/stall signals, max-round cap).
- **Decision owner / integration:** CUI Haoyu (60760270) — the analyst-loop
  wiring, the controller and its tests.
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

## Implementation

- `tradingagents/graph/termination.py` implements `should_terminate` (tool-round
  signatures, repeat threshold, max-round cap, explicit budget flag),
  `TerminationController` (stateful repeat/stall/budget observations), and
  `TerminationDecision`.
- `tradingagents/graph/setup.py` wires the analyst tool loop to
  `should_terminate`; a repeated tool-call round now wraps up before the round
  cap. The existing max-tool-rounds wrap-up remains the hard cap.
- The feature-f debate engine already evaluates convergence/schema termination
  through `evaluate_termination`; this ADR covers the general loop signal and
  leaves the debate policy in ADR-002.
- `src/termination_controller.py` is the project-owned facade used by the
  offline tests; it re-exports the runtime implementation rather than keeping a
  second copy.
- `test/offline/test_termination.py` covers repeat, distinct rounds, max-round
  cap, budget flag, stateful stall/repeat/budget and reset.

The stall/budget signals are exposed by the controller; the analyst loop wires
repeat + max-round, the debate engine wires convergence/schema, and the context
budget blocks an over-budget send. Full per-agent wiring of the stateful
stall/budget trigger remains a follow-up, not a claim of this acceptance.

## Reopen conditions
Too many premature terminations → calibrate the threshold.

## Architectural design process

The driver is the baseline loop's turn-count-only termination: a model can repeat
near-identical tool calls and burn tokens. Candidates were turn-count only
(deadlock-prone), no termination (unbounded cost), and a controller with
repeat/stall/budget triggers (selected). The implementation adds a pure
message-history check for the analyst tool loop plus a stateful controller for
callers that can observe progress; the tests make the repeat and cap behaviour
permanent. The consequence is an earlier, logged wrap-up on a stuck loop; the
reopen condition is a measured false-termination rate.

> **CUI Haoyu note:** I implemented this integration to close the D8 termination
> gap; the original requirement/ADR was unassigned. The stall/budget API is
> tested, while the analyst loop currently wires repeat + max-round.