"""OFFLINE termination-discipline tests (REQ-TERMINATION-DISCIPLINE, ADR-005)."""

import pytest
from langchain_core.messages import AIMessage

from src.termination_controller import (
    REPEAT_THRESHOLD,
    TerminationController,
    should_terminate,
)
from tradingagents.graph.termination import tool_round_signatures

pytestmark = pytest.mark.offline


def _round(name="get_stock_data", args=None, index=0):
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": name,
                "args": args or {"symbol": "NVDA"},
                "id": f"call_{index}",
                "type": "tool_call",
            }
        ],
    )


def test_repeat_terminates_at_threshold():
    messages = [_round(index=i) for i in range(REPEAT_THRESHOLD)]
    decision = should_terminate(messages, max_tool_rounds=10)
    assert decision.should_terminate is True
    assert decision.trigger == "REPEAT"
    assert decision.repeated_rounds == REPEAT_THRESHOLD


def test_distinct_calls_do_not_terminate():
    messages = [
        _round("get_stock_data", {"symbol": "NVDA", "day": i}, i)
        for i in range(3)
    ]
    decision = should_terminate(messages, max_tool_rounds=10)
    assert decision.should_terminate is False
    assert decision.trigger is None
    assert decision.rounds == 3


def test_round_cap_still_terminates():
    messages = [_round(args={"symbol": "NVDA", "day": i}, index=i) for i in range(2)]
    decision = should_terminate(messages, max_tool_rounds=2)
    assert decision.should_terminate is True
    assert decision.trigger == "MAX_ROUNDS"


def test_budget_exhaustion_terminates():
    decision = should_terminate([], max_tool_rounds=10, budget_exhausted=True)
    assert decision.should_terminate is True
    assert decision.trigger == "BUDGET"


def test_tool_round_signatures_ignore_non_tool_messages():
    messages = [AIMessage(content="report"), _round(index=0)]
    assert len(tool_round_signatures(messages)) == 1


def test_stateful_controller_repeat_stall_budget_and_reset():
    controller = TerminationController(max_rounds=10, repeat_threshold=2, stall_rounds=2)
    assert controller.observe(("same",)).should_terminate is False
    repeated = controller.observe(("same",))
    assert repeated.trigger == "REPEAT"

    controller.reset()
    assert controller.observe(("a",), progress=False).should_terminate is False
    stalled = controller.observe(("b",), progress=False)
    assert stalled.trigger == "STALL"

    controller.reset()
    budget = controller.observe(("c",), budget_exhausted=True)
    assert budget.trigger == "BUDGET"

    controller.reset()
    assert controller.observe(("d",)).rounds == 1


def test_controller_rejects_invalid_thresholds():
    with pytest.raises(ValueError):
        TerminationController(max_rounds=0)
