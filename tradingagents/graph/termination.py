"""Deterministic termination discipline for agent loops (ADR-005).

The baseline stops an analyst only at ``max_tool_rounds`` and a debate only at a
round counter. This module adds the missing self-termination signal:

* consecutive identical tool-call rounds (repeat),
* a stateful no-progress/stall counter for callers that can observe progress,
* an explicit budget-exhaustion flag.

The graph setup uses :func:`should_terminate` for the analyst tool loop; the
stateful :class:`TerminationController` is available to loops that can feed it
one observation per round. The controller never terminates on an empty round and
never raises for malformed messages; a malformed observation is treated as no
new evidence, not as a reason to run forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REPEAT_THRESHOLD = 3
STALL_THRESHOLD = 2


@dataclass(frozen=True, slots=True)
class TerminationDecision:
    """The controller's verdict for one observation or message history."""

    should_terminate: bool
    trigger: str | None
    reason: str
    rounds: int
    repeated_rounds: int = 0
    stalled_rounds: int = 0


def _tool_signature(message: Any) -> tuple:
    """A stable signature of the tool calls in one assistant message."""
    calls = getattr(message, "tool_calls", None) or []
    signature = []
    for call in calls:
        if isinstance(call, dict):
            name = str(call.get("name", ""))
            args = repr(call.get("args"))
        else:
            name = str(getattr(call, "name", ""))
            args = repr(getattr(call, "args", None))
        signature.append((name, args))
    return tuple(sorted(signature))


def tool_round_signatures(messages: list) -> list[tuple]:
    """One signature per assistant message that made at least one tool call."""
    signatures: list[tuple] = []
    for message in messages:
        if not getattr(message, "tool_calls", None):
            continue
        signature = _tool_signature(message)
        if signature:
            signatures.append(signature)
    return signatures


def should_terminate(
    messages: list,
    *,
    max_tool_rounds: int,
    repeat_threshold: int = REPEAT_THRESHOLD,
    budget_exhausted: bool = False,
) -> TerminationDecision:
    """Decide from the message history whether the loop must stop.

    The round cap is checked first; the repeat rule then catches a model that
    keeps issuing the same tool call. ``budget_exhausted`` is an explicit input
    because the context-budget layer is the component that knows the count.
    """
    signatures = tool_round_signatures(messages)
    rounds = len(signatures)
    if rounds >= max_tool_rounds:
        return TerminationDecision(
            True,
            "MAX_ROUNDS",
            f"Reached the configured tool-round limit of {max_tool_rounds}.",
            rounds,
        )

    repeated = 0
    longest = 0
    for index, signature in enumerate(signatures):
        if signature and index and signature == signatures[index - 1]:
            repeated += 1
        else:
            repeated = 1 if signature else 0
        longest = max(longest, repeated)
    if longest >= repeat_threshold:
        return TerminationDecision(
            True,
            "REPEAT",
            f"The same tool-call round repeated {longest} times (threshold {repeat_threshold}).",
            rounds,
            repeated_rounds=longest,
        )
    if budget_exhausted:
        return TerminationDecision(
            True,
            "BUDGET",
            "The context/token budget is exhausted.",
            rounds,
            repeated_rounds=longest,
        )
    return TerminationDecision(False, None, "continue", rounds, repeated_rounds=longest)


class TerminationController:
    """Stateful repeat/stall/budget controller for a loop that observes rounds."""

    def __init__(
        self,
        *,
        max_rounds: int,
        repeat_threshold: int = REPEAT_THRESHOLD,
        stall_rounds: int = STALL_THRESHOLD,
    ) -> None:
        if max_rounds <= 0:
            raise ValueError("max_rounds must be > 0")
        if repeat_threshold <= 0 or stall_rounds <= 0:
            raise ValueError("repeat/stall thresholds must be > 0")
        self.max_rounds = max_rounds
        self.repeat_threshold = repeat_threshold
        self.stall_rounds = stall_rounds
        self.rounds = 0
        self._previous: tuple | None = None
        self._repeated = 0
        self._stalled = 0

    def observe(
        self,
        signature: tuple | None = None,
        *,
        progress: bool = True,
        budget_exhausted: bool = False,
    ) -> TerminationDecision:
        """Observe one completed round and return the stop decision."""
        self.rounds += 1
        if self._previous is not None and signature is not None and signature == self._previous:
            self._repeated += 1
        else:
            self._repeated = 1 if signature else 0
        self._previous = signature
        self._stalled = 0 if progress else self._stalled + 1

        if self.rounds >= self.max_rounds:
            return TerminationDecision(
                True,
                "MAX_ROUNDS",
                f"Reached the configured round limit of {self.max_rounds}.",
                self.rounds,
                repeated_rounds=self._repeated,
                stalled_rounds=self._stalled,
            )
        if self._repeated >= self.repeat_threshold:
            return TerminationDecision(
                True,
                "REPEAT",
                f"The same round repeated {self._repeated} times.",
                self.rounds,
                repeated_rounds=self._repeated,
                stalled_rounds=self._stalled,
            )
        if self._stalled >= self.stall_rounds:
            return TerminationDecision(
                True,
                "STALL",
                f"No progress for {self._stalled} rounds.",
                self.rounds,
                repeated_rounds=self._repeated,
                stalled_rounds=self._stalled,
            )
        if budget_exhausted:
            return TerminationDecision(
                True,
                "BUDGET",
                "The context/token budget is exhausted.",
                self.rounds,
                repeated_rounds=self._repeated,
                stalled_rounds=self._stalled,
            )
        return TerminationDecision(
            False,
            None,
            "continue",
            self.rounds,
            repeated_rounds=self._repeated,
            stalled_rounds=self._stalled,
        )

    def reset(self) -> None:
        self.rounds = 0
        self._previous = None
        self._repeated = 0
        self._stalled = 0
