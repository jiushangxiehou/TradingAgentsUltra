"""OFFLINE guarded-graph tests (ADR-006, REQ-HARD-GUARDRAIL, REQ-TRACEABILITY).

No LLM, no network, no graph: the subject is the guarded ``record_decision``
boundary and the capture lifecycle around it. Instances are built with
``object.__new__`` so the upstream ``__init__`` (which builds a graph and a
checkpointer) never runs, and every inherited method that would do real work is
stubbed on the INSTANCE except the ones under test.

Invariants under test
---------------------
INV-GUARDRAIL-ZERO-ESCAPE : a rejected decision never leaves the state executable.
INV-RATING-VALIDITY       : whatever happened, ``final_rating`` is a legal tier.
INV-TRACE-COMPLETENESS    : the evidence chain is attached and written beside the run.
"""

from __future__ import annotations

import json
import pathlib
from types import SimpleNamespace

import pytest

pytest.importorskip("tradingagents")

from src.guardrail import FALLBACK_RATING, GuardrailLimits
from src.integration import governed_graph
from src.integration.decision_adapter import ExecutionIntent
from src.integration.governed_graph import EXECUTION_INTENT, GuardedTradingAgentsGraph

pytestmark = pytest.mark.offline

TRADE_DATE = "2026-11-24"
TICKER = "NVDA"
INSTANT = "2026-11-24T00:00:00+00:00"
ORIGINAL_DECISION = "**Rating**: Buy\n\n**Executive Summary**: add aggressively."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FakeMemoryLog:
    """Records what the memory log was told, in order."""

    def __init__(self) -> None:
        self.stored: list[dict] = []

    def store_decision(self, *, ticker, trade_date, final_trade_decision, rating):
        self.stored.append(
            {"ticker": ticker, "trade_date": trade_date,
             "final_trade_decision": final_trade_decision, "rating": rating}
        )


def make_state(**overrides) -> dict:
    state = {
        "company_of_interest": TICKER,
        "trade_date": TRADE_DATE,
        "market_report": "Market report body.",
        "sentiment_report": "Sentiment report body.",
        "news_report": "News report body.",
        "fundamentals_report": "Fundamentals report body.",
        "investment_debate_state": {"bull_history": "b", "bear_history": "s",
                                    "history": "h", "current_response": "c"},
        "investment_plan": "**Recommendation**: Overweight",
        "trader_investment_plan": "**Action**: Buy\n\n**Position Sizing**: 5% of portfolio",
        "risk_debate_state": {"aggressive_history": "a", "conservative_history": "c",
                              "neutral_history": "n", "history": "h"},
        "final_trade_decision": ORIGINAL_DECISION,
        "final_rating": "Buy",
    }
    state.update(overrides)
    return state


EVENTS: list[str] = []


def build_graph(tmp_path, *, intent=None, cash=10_000.0, limits=None, calls=None):
    """A guarded graph with the inherited machinery stubbed on the instance."""
    graph = object.__new__(GuardedTradingAgentsGraph)
    graph.execution_intent = intent
    graph.guardrail_limits = limits if limits is not None else GuardrailLimits()
    graph.portfolio = SimpleNamespace(cash=cash) if cash is not None else None
    graph.started_at = INSTANT
    graph.last_trace = None
    graph._capture = None
    graph._capture_calls = tuple(calls or ())
    graph._capture_errors = []
    graph._capture_finished = True
    graph.memory_log = FakeMemoryLog()
    graph.config = {"results_dir": str(tmp_path), "llm_provider": "openai",
                    "selected_analysts": ["market", "news"]}

    def fake_super_record_decision(company_name, trade_date, final_state):
        EVENTS.append("super.record_decision")
        if final_state.get("final_trade_decision"):
            graph.memory_log.store_decision(
                ticker=company_name, trade_date=trade_date,
                final_trade_decision=final_state["final_trade_decision"],
                rating=final_state.get("final_rating"),
            )

    # Bind the upstream implementation's stub where super() would resolve.
    object.__setattr__(graph, "_super_record_decision", fake_super_record_decision)
    return graph


@pytest.fixture(autouse=True)
def _reset_events():
    EVENTS.clear()
    yield
    EVENTS.clear()


def run_record_decision(monkeypatch, graph, state):
    """Call the guarded ``record_decision`` with ``super()`` replaced by a stub."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    def upstream_stub(self, company_name, trade_date, final_state):
        return graph._super_record_decision(company_name, trade_date, final_state)

    monkeypatch.setattr(Upstream, "record_decision", upstream_stub)
    GuardedTradingAgentsGraph.record_decision(graph, TICKER, TRADE_DATE, state)


def sidecar(tmp_path, trade_date=TRADE_DATE) -> pathlib.Path:
    return (pathlib.Path(tmp_path) / TICKER / "TradingAgentsStrategy_logs"
            / f"guardrail_trace_{trade_date}.json")


# ---------------------------------------------------------------------------
# G1 -- a rejection is written in place, and audited
# ---------------------------------------------------------------------------

def make_calls():
    """Three deterministic captured calls, so the trace has real evidence."""
    from src.integration.trace_adapter import CapturedCall

    return tuple(
        CapturedCall(method=method, data_source=source, args_digest=f"{i}" * 12,
                     result_digest=f"{(i + 1) % 10}" * 12, result_kind="ok")
        for i, (method, source) in enumerate(
            (("get_stock_data", "yfinance"), ("get_news", "alpha_vantage"), ("reddit", "reddit"))
        )
    )


def test_g1_reject_mutates_in_place_to_hold(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.5, short_amount=0.0),
                        calls=make_calls())
    state = make_state()
    identity = id(state)

    run_record_decision(monkeypatch, graph, state)

    assert id(state) == identity                      # the SAME object the CLI holds
    assert state["final_rating"] == FALLBACK_RATING == "Hold"
    assert state["final_trade_decision"] != ORIGINAL_DECISION
    assert ORIGINAL_DECISION in state["final_trade_decision"]  # preserved verbatim
    payload = state["guardrail"]
    assert payload["passed"] is False
    assert payload["audit"]["action"] == "REVIEW/HOLD"
    assert payload["audit"]["trigger"] == "POSITION_LIMIT"
    assert payload["original_rating"] == "Buy"
    assert payload["limits"] == GuardrailLimits().as_dict()
    assert payload["load_report"]["missing_fields"] == []
    assert payload["trace"]["traceable"] is True
    assert payload["trace"] is not None


def test_g1_sidecar_exists_and_parses(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.5, short_amount=0.0))
    state = make_state()

    run_record_decision(monkeypatch, graph, state)

    path = sidecar(tmp_path)
    assert path.is_file()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert set(body) == {"guardrail", "trace"}
    assert body["guardrail"]["audit"]["action"] == "REVIEW/HOLD"
    assert body["trace"]["decision_id"] == f"decision:{TICKER}:{TRADE_DATE}:Hold"
    assert state["guardrail"]["sidecar"] == str(path)


# ---------------------------------------------------------------------------
# G2 -- a pass leaves the decision alone
# ---------------------------------------------------------------------------

def test_g2_pass_does_not_rewrite_the_rating(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0),
                        cash=10_000.0)
    state = make_state(final_rating="Overweight",
                       final_trade_decision="**Rating**: Overweight\n\nGo.")

    run_record_decision(monkeypatch, graph, state)

    assert state["final_rating"] == "Overweight"
    assert state["final_trade_decision"] == "**Rating**: Overweight\n\nGo."
    assert state["guardrail"]["passed"] is True
    assert state["guardrail"]["action"] is None
    assert state["guardrail"]["trace"] is not None
    assert sidecar(tmp_path).is_file()


def test_g2_a_pass_is_logged_with_its_own_rating(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    run_record_decision(monkeypatch, graph, make_state(final_rating="Overweight"))
    assert graph.memory_log.stored[-1]["rating"] == "Overweight"


# ---------------------------------------------------------------------------
# G3 -- the memory log is written BEFORE the trace
# ---------------------------------------------------------------------------

def test_g3_super_record_decision_runs_before_build_trace(monkeypatch, tmp_path):
    order: list[str] = []
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.5, short_amount=0.0))

    real_record = graph._super_record_decision

    def logging_record(company_name, trade_date, final_state):
        order.append("super.record_decision")
        return real_record(company_name, trade_date, final_state)

    graph._super_record_decision = logging_record

    def logging_trace(**kwargs):
        order.append("build_trace")
        return dict.fromkeys(("traceable", "checked_links", "resolved_links", "findings", "decision_id", "snapshot_count", "table", "unbacked_reports", "capture_errors", "trace_error"))

    monkeypatch.setattr(governed_graph, "build_trace", logging_trace)
    run_record_decision(monkeypatch, graph, make_state())

    assert order == ["super.record_decision", "build_trace"]


def test_g3_the_memory_log_sees_the_guarded_state(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.5, short_amount=0.0))
    run_record_decision(monkeypatch, graph, make_state())
    stored = graph.memory_log.stored[-1]
    assert stored["rating"] == "Hold"
    assert ORIGINAL_DECISION in stored["final_trade_decision"]


# ---------------------------------------------------------------------------
# G4 -- a missing intent or cash fails closed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "intent,cash",
    [(None, 10_000.0), (ExecutionIntent(0.05, 0.0), None), (ExecutionIntent(), 10_000.0)],
    ids=["no-intent", "no-cash", "empty-intent"],
)
def test_g4_missing_required_input_is_malformed_and_held(monkeypatch, tmp_path, intent, cash):
    graph = build_graph(tmp_path, intent=intent, cash=cash)
    state = make_state()

    run_record_decision(monkeypatch, graph, state)

    assert state["final_rating"] == "Hold"
    assert state["guardrail"]["audit"]["trigger"] == "MALFORMED_DECISION"
    assert state["guardrail"]["load_report"]["missing_fields"]


def test_g4_the_context_var_supplies_the_intent_when_the_graph_has_none(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=None)
    token = EXECUTION_INTENT.set(ExecutionIntent(size_pct=0.05, short_amount=0.0))
    try:
        state = make_state()
        run_record_decision(monkeypatch, graph, state)
    finally:
        EXECUTION_INTENT.reset(token)
    assert state["guardrail"]["passed"] is True


def test_g4_an_explicit_constructor_intent_wins_over_the_context_var(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.5, short_amount=0.0))
    token = EXECUTION_INTENT.set(ExecutionIntent(size_pct=0.05, short_amount=0.0))
    try:
        state = make_state()
        run_record_decision(monkeypatch, graph, state)
    finally:
        EXECUTION_INTENT.reset(token)
    assert state["final_rating"] == "Hold"      # the graph's intent, not the var's


# ---------------------------------------------------------------------------
# G5 -- a guardrail that cannot run does not raise and does not pass
# ---------------------------------------------------------------------------

def test_g5_guardrail_error_holds_with_a_config_error_note(monkeypatch, tmp_path):
    from src.guardrail import GuardrailError

    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    state = make_state()

    def explode(decision, limits=None):
        raise GuardrailError("limits must be GuardrailLimits")

    monkeypatch.setattr(governed_graph, "evaluate_decision", explode)
    run_record_decision(monkeypatch, graph, state)   # must not raise

    assert state["final_rating"] == "Hold"
    payload = state["guardrail"]
    assert payload["passed"] is False
    assert payload["action"] == "REVIEW/HOLD"
    assert "GUARDRAIL_CONFIG_ERROR" in payload["notes"]
    assert "limits must be GuardrailLimits" in payload["audit"]["observed_value"]


def test_g5_a_bad_limits_object_is_the_same_fault(monkeypatch, tmp_path):
    """The real ``evaluate_decision`` raises for a bad object; the gate holds."""
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    graph.guardrail_limits = {"max_position_pct": 0.1}     # not a GuardrailLimits
    state = make_state()
    run_record_decision(monkeypatch, graph, state)
    assert state["final_rating"] == "Hold"
    assert "GUARDRAIL_CONFIG_ERROR" in state["guardrail"]["notes"]


# ---------------------------------------------------------------------------
# G6 -- a trace failure never changes the decision
# ---------------------------------------------------------------------------

def test_g6_trace_failure_leaves_the_rating_and_memory_log_intact(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    state = make_state(final_rating="Overweight")

    def broken_trace(**kwargs):
        return {"traceable": False, "checked_links": 0, "resolved_links": 0,
                "findings": [], "decision_id": "decision:x", "snapshot_count": 0,
                "table": [], "unbacked_reports": [], "capture_errors": [],
                "trace_error": "TraceError: bad instant"}

    monkeypatch.setattr(governed_graph, "build_trace", broken_trace)
    run_record_decision(monkeypatch, graph, state)

    assert state["final_rating"] == "Overweight"          # the guardrail's verdict stands
    assert state["guardrail"]["passed"] is True
    assert state["guardrail"]["trace"]["traceable"] is False
    assert graph.memory_log.stored[-1]["rating"] == "Overweight"


def test_g6_a_raising_trace_builder_is_contained(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    state = make_state(final_rating="Overweight")

    def boom(**kwargs):
        raise RuntimeError("trace exploded")

    monkeypatch.setattr(governed_graph, "build_trace", boom)
    run_record_decision(monkeypatch, graph, state)

    assert state["final_rating"] == "Overweight"
    assert state["guardrail"]["trace"]["traceable"] is False
    assert "RuntimeError" in state["guardrail"]["trace"]["trace_error"]


# ---------------------------------------------------------------------------
# G7 -- run settings
# ---------------------------------------------------------------------------

def test_g7_run_settings_adds_the_guardrail_keys_and_keeps_the_upstream_ones(monkeypatch):
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    upstream = {"version": "0.7.1", "llm_provider": "openai", "analysts": ["market"]}
    monkeypatch.setattr(Upstream, "run_settings", lambda self: dict(upstream))
    graph = build_graph(pathlib.Path("."), intent=None)

    settings = GuardedTradingAgentsGraph.run_settings(graph)

    assert set(upstream) <= set(settings)
    assert settings["guardrail_limits"] == GuardrailLimits().as_dict()
    assert settings["trace_enabled"] is True


def test_g7_custom_limits_are_reported(monkeypatch):
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    monkeypatch.setattr(Upstream, "run_settings", lambda self: {})
    graph = build_graph(pathlib.Path("."), limits=GuardrailLimits(max_position_pct=0.02))

    settings = GuardedTradingAgentsGraph.run_settings(graph)

    assert settings["guardrail_limits"]["max_position_pct"] == 0.02


# ---------------------------------------------------------------------------
# G8 -- capture lifecycle
# ---------------------------------------------------------------------------

class FakeCapture:
    def __init__(self, calls=(), errors=(), fail_close=False):
        self._calls = tuple(calls)
        self._errors = tuple(errors)
        self.finish_count = 0
        self.fail_close = fail_close

    def finish(self):
        self.finish_count += 1
        if self.fail_close:
            raise OSError("restore failed")
        return self._calls

    @property
    def capture_errors(self):
        return self._errors


def test_g8_a_failing_super_record_decision_still_restores_the_patched_functions(
    monkeypatch, tmp_path
):
    """The capture must be closed even when the run dies in the memory log."""
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.05, short_amount=0.0))
    fake = FakeCapture(calls=[("a",)])
    graph._capture = fake
    graph._capture_finished = False

    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    def upstream_stub(self, company_name, trade_date, final_state):
        raise RuntimeError("state log failed")

    monkeypatch.setattr(Upstream, "record_decision", upstream_stub)
    with pytest.raises(RuntimeError):
        GuardedTradingAgentsGraph.record_decision(graph, TICKER, TRADE_DATE, make_state())

    assert fake.finish_count == 1            # closed exactly once...
    assert graph._capture is None            # ...and forgotten
    assert graph._capture_finished is True


def test_g8_finish_capture_is_idempotent():
    graph = build_graph(pathlib.Path("."), intent=None)
    fake = FakeCapture()
    graph._capture = fake
    graph._capture_finished = False

    graph._finish_capture()
    graph._finish_capture()
    graph._finish_capture()

    assert fake.finish_count == 1


def test_g8_a_finishing_capture_that_fails_is_journalled_not_raised():
    graph = build_graph(pathlib.Path("."), intent=None)
    graph._capture = FakeCapture(fail_close=True)
    graph._capture_finished = False

    graph._finish_capture()                  # must not raise

    assert any("capture-finish: OSError" in error for error in graph._capture_errors)
    assert graph._capture_finished is True


def test_g8_an_abandoned_capture_is_closed_before_the_next_run(monkeypatch, tmp_path):
    """A run that never reached record_decision must not leak into the next."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    graph = build_graph(tmp_path, intent=None)
    first = FakeCapture()
    graph._capture = first
    graph._capture_finished = False

    monkeypatch.setattr(Upstream, "propagate", lambda self, *a, **k: ("state", "Hold"))
    monkeypatch.setattr(GuardedTradingAgentsGraph, "create_run_state",
                        lambda self, *a, **k: {})

    GuardedTradingAgentsGraph.propagate(graph, TICKER, TRADE_DATE)

    assert first.finish_count >= 1
    assert graph._capture is None


def test_g8_create_run_state_takes_one_instant_and_opens_a_capture(monkeypatch, tmp_path):
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    graph = build_graph(tmp_path, intent=None)
    graph._capture_finished = True
    opened: list[str] = []

    class Inert:
        capture_errors: tuple = ()

        def finish(self):
            return ()

    monkeypatch.setattr(Upstream, "create_run_state", lambda self, *a, **k: {"ok": True})
    monkeypatch.setattr(governed_graph, "begin_capture",
                        lambda instant: (opened.append(instant), Inert())[1])

    state = GuardedTradingAgentsGraph.create_run_state(graph, TICKER, TRADE_DATE)

    assert state == {"ok": True}
    assert len(opened) == 1
    assert opened[0] == graph.started_at
    assert opened[0].endswith("+00:00")
    assert graph._capture_finished is False


def test_g8_create_run_state_closes_the_capture_when_it_fails(monkeypatch, tmp_path):
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    graph = build_graph(tmp_path, intent=None)
    fake = FakeCapture()

    def boom(self, *a, **k):
        raise ValueError("bad trade date")

    monkeypatch.setattr(Upstream, "create_run_state", boom)
    monkeypatch.setattr(governed_graph, "begin_capture", lambda instant: fake)

    with pytest.raises(ValueError):
        GuardedTradingAgentsGraph.create_run_state(graph, TICKER, "not-a-date")

    assert fake.finish_count == 1
    assert graph._capture_finished is True


def test_g8_a_capture_that_cannot_start_does_not_stop_the_run(monkeypatch, tmp_path):
    from tradingagents.graph.trading_graph import TradingAgentsGraph as Upstream

    graph = build_graph(tmp_path, intent=None)

    def no_capture(instant):
        raise RuntimeError("patching failed")

    monkeypatch.setattr(Upstream, "create_run_state", lambda self, *a, **k: {"ok": True})
    monkeypatch.setattr(governed_graph, "begin_capture", no_capture)

    assert GuardedTradingAgentsGraph.create_run_state(graph, TICKER, TRADE_DATE) == {"ok": True}
    assert any("capture-start: RuntimeError" in error for error in graph._capture_errors)


# ---------------------------------------------------------------------------
# G9 -- a sidecar that cannot be written is recorded, never raised
# ---------------------------------------------------------------------------

def test_g9_an_unwritable_sidecar_does_not_raise(monkeypatch, tmp_path):
    graph = build_graph(tmp_path, intent=ExecutionIntent(size_pct=0.5, short_amount=0.0))
    state = make_state()

    def refuses(self, *args, **kwargs):
        raise PermissionError("read-only directory")

    monkeypatch.setattr(pathlib.Path, "write_text", refuses)
    run_record_decision(monkeypatch, graph, state)      # must not raise

    assert state["guardrail"]["sidecar"] is None
    assert "PermissionError" in state["guardrail"]["sidecar_error"]
    assert state["final_rating"] == "Hold"              # the verdict is unaffected


def test_g9_a_ticker_that_is_not_a_path_component_is_refused(tmp_path):
    graph = build_graph(tmp_path, intent=None)
    with pytest.raises(ValueError):
        GuardedTradingAgentsGraph.sidecar_path(graph, "../../etc", TRADE_DATE)


# ---------------------------------------------------------------------------
# G10 -- "REVIEW" is never a rating
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "rating,intent",
    [
        ("REVIEW", ExecutionIntent(0.05, 0.0)),          # upstream's own sentinel
        ("Buy", ExecutionIntent(0.5, 0.0)),              # oversize
        (None, None),                                    # nothing to judge
        ("Buy", None),                                   # no intent
    ],
    ids=["review-sentinel", "oversize", "no-rating", "no-intent"],
)
def test_g10_review_is_never_written_as_a_rating(monkeypatch, tmp_path, rating, intent):
    graph = build_graph(tmp_path, intent=intent)
    state = make_state(final_rating=rating, final_trade_decision="**Rating**: Buy")

    run_record_decision(monkeypatch, graph, state)

    assert state["final_rating"] != "REVIEW"
    assert state["final_rating"] == "Hold"
    assert state["guardrail"]["action"] == "REVIEW/HOLD"


def test_g10_the_legal_tier_survives_every_rejection_path(monkeypatch, tmp_path):
    from src.guardrail import VALID_RATINGS

    for intent in (ExecutionIntent(0.5, 0.0), None, ExecutionIntent(-1, 0.0)):
        graph = build_graph(tmp_path, intent=intent)
        state = make_state()
        run_record_decision(monkeypatch, graph, state)
        assert state["final_rating"] in VALID_RATINGS
