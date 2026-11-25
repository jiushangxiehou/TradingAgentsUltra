"""OFFLINE context-budget configuration tests (REQ-CONTEXT-BUDGET, ADR-001).

The full compaction/transport tests live in ``tests/test_context_budget_core.py``
and ``tests/test_budget_agent_integration.py`` on dev. This file keeps the
project's offline test layout honest: it exercises the strict configuration
contract that turns the budget on or off.
"""

import pytest

from tradingagents.graph.context_budget import is_budget_enabled, resolve_budget

pytestmark = pytest.mark.offline


def test_unset_budget_is_disabled():
    assert resolve_budget({}) == (None, None)
    assert is_budget_enabled({}) is False


def test_valid_pair_is_returned_and_enabled():
    config = {
        "context_input_hard_cap_tokens": 8000,
        "context_input_compaction_threshold_tokens": 6000,
    }
    assert resolve_budget(config) == (8000, 6000)
    assert is_budget_enabled(config) is True


def test_partial_configuration_fails_closed():
    with pytest.raises(ValueError, match="BOTH"):
        resolve_budget({"context_input_hard_cap_tokens": 8000})


def test_threshold_above_cap_is_invalid():
    with pytest.raises(ValueError, match="threshold"):
        resolve_budget(
            {
                "context_input_hard_cap_tokens": 100,
                "context_input_compaction_threshold_tokens": 200,
            }
        )


def test_invalid_value_is_rejected_not_silently_disabled():
    with pytest.raises(ValueError):
        resolve_budget(
            {
                "context_input_hard_cap_tokens": 0,
                "context_input_compaction_threshold_tokens": 1,
            }
        )
