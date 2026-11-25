"""OFFLINE full-graph tests: the guarded graph on the real LangGraph.

ADR-006 / REQ-HARD-GUARDRAIL / REQ-TRACEABILITY / INV-GUARDRAIL-ZERO-ESCAPE /
INV-RATING-VALIDITY / INV-TRACE-COMPLETENESS

The earlier suites test each seam with stubs. These run the WHOLE graph -- every
analyst, both debates, the trader, the portfolio manager, the memory log -- with
a scripted model and every vendor answering locally, and then check that the
guardrail and the evidence chain hold on what the real run actually produced.
That is the difference between "the wiring is testable" and "the wiring works".

The scripted-model harness replicates the shape of the upstream end-to-end test
(``vendor/tradingagents-0.7.x/tests/test_graph_end_to_end.py``) rather than
importing it: the vendored tree is pinned byte-exactly and its tests are
private to it.

The evidence checks are deliberately about INVARIANTS, not counts. How many
vendor calls a run makes is an upstream detail; what must be true is that every
report the run produced is backed by evidence, the chain has no findings, and
the same run twice produces the same chain.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pandas as pd
import pytest

pytest.importorskip("tradingagents")

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field
from tradingagents.agents import context, schemas
from tradingagents.agents.analysts import sentiment_analyst
from tradingagents.dataflows import router
from tradingagents.dataflows.vendors.yahoo import market as yahoo_market
from tradingagents.dataflows.vendors.yahoo import snapshot
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph import trading_graph
from tradingagents.portfolio import PortfolioContext

from src.guardrail import FALLBACK_RATING
from src.integration.decision_adapter import ExecutionIntent
from src.integration.governed_graph import EXECUTION_INTENT, GuardedTradingAgentsGraph

pytestmark = pytest.mark.offline

TICKER = "NVDA"
TRADE_DATE = "2026-01-09"

# Enough for every free-text reader: the PM's labelled rating and the trader's
# closing proposal line.
TEXT = "Report.\n\n**Rating**: Overweight\n\nFINAL TRANSACTION PROPOSAL: **BUY**"

# The rating the Portfolio Manager's own structured output states. The
# free-text TEXT says Overweight too, so the two cannot disagree.
STRUCTURED = {
    schemas.ResearchPlan: schemas.ResearchPlan(
        recommendation=schemas.PortfolioRating.OVERWEIGHT, rationale="r", strategic_actions="a"),
    schemas.TraderProposal: schemas.TraderProposal(
        action=schemas.TraderAction.BUY, reasoning="r"),
    schemas.PortfolioDecision: schemas.PortfolioDecision(
        rating=schemas.PortfolioRating.OVERWEIGHT, executive_summary="s",
        investment_thesis="Street consensus rating: Buy (28 of 35 analysts)."),
    schemas.SentimentReport: schemas.SentimentReport(
        overall_band=schemas.SentimentBand.NEUTRAL, overall_score=5.0,
        confidence="low", narrative="n"),
}

ARGS = {
    "symbol": TICKER, "ticker": TICKER, "curr_date": TRADE_DATE, "start_date": "2026-01-02",
    "end_date": TRADE_DATE, "indicator": "rsi", "topic": "Fed rate cut", "freq": "quarterly",
}

# What every analyst must have asked for before it can write a report.
TOOL_METHODS = {
    "get_stock_data", "get_indicators", "get_news", "get_global_news", "get_macro_indicators",
    "get_prediction_markets", "get_fundamentals", "get_balance_sheet", "get_cashflow",
    "get_income_statement", "get_insider_transactions", "ohlcv",
}


# ---------------------------------------------------------------------------
# The scripted model
# ---------------------------------------------------------------------------

class ScriptedModel(BaseChatModel):
    """Calls every bound tool once, then answers with TEXT (or STRUCTURED)."""

    structured: bool = True
    tools: tuple = ()
    calls: list = Field(default_factory=list)   # shared across bound copies

    @property
    def _llm_type(self):
        return "scripted-guarded"

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tools": tuple(tools)})

    def with_structured_output(self, schema, **kwargs):
        """Only models that opted in are offered a schema; raise otherwise."""
        if not self.structured:
            raise NotImplementedError
        return RunnableLambda(lambda _: self.calls.append(1) or STRUCTURED[schema])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(1)
        if self.tools and not isinstance(messages[-1], ToolMessage):
            # Every bound tool once, with only the arguments it declares.
            requests = [
                {
                    "name": tool.name,
                    "id": f"call_{index}",
                    "args": {
                        key: value
                        for key, value in ARGS.items()
                        if key in tool.tool_call_schema.model_json_schema()["properties"]
                    },
                }
                for index, tool in enumerate(self.tools)
            ]
            message = AIMessage(content="", tool_calls=requests)
        else:
            message = AIMessage(content=TEXT)
        return ChatResult(generations=[ChatGeneration(message=message)])


class _Client:
    """The one method the graph asks a tier client for."""

    def __init__(self, model) -> None:
        self.model = model

    def get_llm(self):
        return self.model


# ---------------------------------------------------------------------------
# Offline vendors
# ---------------------------------------------------------------------------

@pytest.fixture
def offline(monkeypatch):
    """Every vendor answers locally; returns the set of router methods called."""
    called: set[str] = set()
    for method, vendors in router.VENDOR_METHODS.items():
        for vendor in vendors:
            monkeypatch.setitem(
                vendors, vendor, lambda *a, _m=method, **k: called.add(_m) or f"{_m} data"
            )
    prices = pd.DataFrame(
        {
            "Date": pd.bdate_range(end=TRADE_DATE, periods=60),
            "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.5, "Volume": 1_000_000,
        }
    )
    monkeypatch.setattr(snapshot, "load_ohlcv", lambda *a, **k: called.add("ohlcv") or prices.copy())
    monkeypatch.setattr(sentiment_analyst, "fetch_stocktwits_messages", lambda *a, **k: "no posts")
    monkeypatch.setattr(sentiment_analyst, "fetch_reddit_posts", lambda *a, **k: "no posts")
    monkeypatch.setattr(
        yahoo_market.yf, "Ticker", lambda s: type("T", (), {"info": {"longName": "NVIDIA"}})()
    )
    context._identity.cache_clear()
    return called


BOOK = PortfolioContext(cash=10_000.0, positions=[])
PASSING_INTENT = ExecutionIntent(size_pct=0.05, short_amount=0.0)
OVERSIZE_INTENT = ExecutionIntent(size_pct=0.5, short_amount=0.0)


def make_graph(tmp_path, monkeypatch, model=None, intent=None):
    """A guarded graph whose every on-disk path is under ``tmp_path``."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config.update(
        results_dir=str(tmp_path / "results"),
        data_cache_dir=str(tmp_path / "cache"),
        memory_log_path=str(tmp_path / "memory.md"),
    )
    monkeypatch.setattr(
        trading_graph, "create_tier_client", lambda config, tier, **k: _Client(model or ScriptedModel())
    )
    return GuardedTradingAgentsGraph(config=config, execution_intent=intent)


def sidecar_path(results_dir, trade_date=TRADE_DATE) -> pathlib.Path:
    return (
        pathlib.Path(results_dir) / TICKER / "TradingAgentsStrategy_logs"
        / f"guardrail_trace_{trade_date}.json"
    )


def memory_ratings(graph) -> list[str]:
    return [entry["rating"] for entry in graph.memory_log.load_entries()]


# ---------------------------------------------------------------------------
# E1 -- a pass, through the programmatic entry point
# ---------------------------------------------------------------------------

def test_e1_a_full_run_passes_the_gate_and_the_evidence_is_complete(
    tmp_path, monkeypatch, offline
):
    graph = make_graph(tmp_path, monkeypatch, intent=PASSING_INTENT)

    state, signal = graph.propagate(TICKER, TRADE_DATE, portfolio=BOOK)

    # The agents' verdict, untouched by a passing gate.
    assert signal == "Overweight"
    assert state["final_rating"] == "Overweight"

    # Every report really was produced: this is a whole run, not a stub.
    for key in (
        "market_report", "sentiment_report", "news_report", "fundamentals_report",
        "investment_plan", "trader_investment_plan", "final_trade_decision",
    ):
        assert isinstance(state[key], str) and state[key].strip(), key
    assert offline >= TOOL_METHODS

    # The gate ran and passed.
    guardrail = state["guardrail"]
    assert guardrail["passed"] is True
    assert guardrail["action"] is None
    assert guardrail["audit"] is None
    assert guardrail["original_rating"] == "Overweight"
    assert guardrail["load_report"]["missing_fields"] == []

    # The chain is complete: evidence exists, every critical link resolves, and
    # the audit found nothing.
    trace = guardrail["trace"]
    assert trace["traceable"] is True
    assert trace["snapshot_count"] > 0
    assert trace["checked_links"] == trace["resolved_links"] > 0
    assert trace["findings"] == []
    assert trace["unbacked_reports"] == []
    assert trace["decision_id"] == f"decision:{TICKER}:{TRADE_DATE}:Overweight"
    assert trace["trace_error"] is None
    assert trace["capture_errors"] == []

    # The sidecar sits beside the state log and parses.
    path = sidecar_path(tmp_path / "results")
    assert path.is_file()
    body = json.loads(path.read_text(encoding="utf-8"))
    assert set(body) == {"guardrail", "trace"}
    assert body["trace"]["decision_id"] == trace["decision_id"]
    assert guardrail["sidecar"] == str(path)

    # The memory log remembers the decision the gate approved.
    assert memory_ratings(graph) == ["Overweight"]


# ---------------------------------------------------------------------------
# E2 -- a rejection, through the programmatic entry point
# ---------------------------------------------------------------------------

def _capture_pre_gate(monkeypatch) -> list:
    """Record each ``(rating, decision text)`` the run's OWN recursion passes in.

    ``TradingAgentsGraph.record_decision`` is reached twice per run, and the
    order is not something a test should guess. Patch the method the run
    actually calls -- the guarded subclass's -- and call the captured original
    so it still resolves ``super()`` to the unpatched base: only the run's own
    call is observed, not the guard's internal chain.
    """
    calls: list = []
    real = GuardedTradingAgentsGraph.record_decision

    def recording(self, company_name, trade_date, final_state):
        calls.append((final_state.get("final_rating"), final_state.get("final_trade_decision")))
        return real(self, company_name, trade_date, final_state)

    monkeypatch.setattr(GuardedTradingAgentsGraph, "record_decision", recording)
    return calls


def _agents_output(calls: list) -> tuple[object, str]:
    """The one call the run's OWN recursion made: the state it handed to the gate.

    ``propagate`` reaches the boundary once, so anything less or more than one
    observation means the test is measuring something other than the run.
    """
    assert len(calls) == 1, calls
    rating, text = calls[0]
    return rating, text


# ---------------------------------------------------------------------------
# E2 -- a rejection, through the programmatic entry point
# ---------------------------------------------------------------------------

def test_e2_an_oversize_run_is_held_through_the_real_graph(tmp_path, monkeypatch, offline):
    graph = make_graph(tmp_path, monkeypatch, intent=OVERSIZE_INTENT)
    calls = _capture_pre_gate(monkeypatch)

    state, signal = graph.propagate(TICKER, TRADE_DATE, portfolio=BOOK)

    # What the caller acts on is Hold.
    assert signal == FALLBACK_RATING == "Hold"
    assert state["final_rating"] == "Hold"

    guardrail = state["guardrail"]
    assert guardrail["passed"] is False
    assert guardrail["audit"]["trigger"] == "POSITION_LIMIT"
    assert guardrail["audit"]["action"] == "REVIEW/HOLD"
    assert guardrail["audit"]["observed_value"] == "0.5"
    assert guardrail["original_rating"] == "Overweight"

    # The decision text the agents wrote is preserved verbatim under the banner:
    # the rejection replaces the executable rating, never the analysis.
    agents_rating, original = _agents_output(calls)
    assert agents_rating == "Overweight"
    assert "**Rating**: Overweight" in original            # the PM's own structured output
    decision_text = state["final_trade_decision"]
    assert original in decision_text                         # verbatim...
    assert decision_text != original                         # ...and not alone
    assert decision_text.startswith("**Rating**: Hold")      # the executable rating first
    assert decision_text.index(original) > decision_text.index("Guardrail")

    # Evidence about a rejection is still complete evidence.
    assert guardrail["trace"]["traceable"] is True
    assert guardrail["trace"]["snapshot_count"] > 0
    assert guardrail["trace"]["findings"] == []
    assert guardrail["trace"]["decision_id"] == f"decision:{TICKER}:{TRADE_DATE}:Hold"
    assert sidecar_path(tmp_path / "results").is_file()

    # The memory log remembers the gate's verdict, not the agents' proposal, so
    # the next run reflects on the decision that was actually taken.
    assert memory_ratings(graph) == ["Hold"]


# ---------------------------------------------------------------------------
# E3 -- no order supplied at all
# ---------------------------------------------------------------------------

def test_e3_no_intent_fails_closed_to_a_malformed_rejection(tmp_path, monkeypatch, offline):
    assert EXECUTION_INTENT.get() is None          # nothing supplied by an entry point either
    graph = make_graph(tmp_path, monkeypatch, intent=None)
    calls = _capture_pre_gate(monkeypatch)

    state, signal = graph.propagate(TICKER, TRADE_DATE, portfolio=BOOK)

    assert signal == "Hold"
    assert state["final_rating"] == "Hold"
    guardrail = state["guardrail"]
    assert guardrail["passed"] is False
    assert guardrail["audit"]["trigger"] == "MALFORMED_DECISION"
    assert guardrail["audit"]["action"] == "REVIEW/HOLD"
    assert set(guardrail["load_report"]["missing_fields"]) == {"size_pct", "short_amount"}
    _rating, original = _agents_output(calls)
    assert original in state["final_trade_decision"]                    # the analysis survives
    assert state["final_trade_decision"] != original
    assert guardrail["trace"]["traceable"] is True
    assert memory_ratings(graph) == ["Hold"]


def test_e3_the_context_var_supplies_the_intent_to_a_graph_built_without_one(
    tmp_path, monkeypatch, offline
):
    """The CLI path: ``entry`` sets the ContextVar, the graph is built plainly."""
    graph = make_graph(tmp_path, monkeypatch, intent=None)
    token = EXECUTION_INTENT.set(PASSING_INTENT)
    try:
        _, signal = graph.propagate(TICKER, TRADE_DATE, portfolio=BOOK)
    finally:
        EXECUTION_INTENT.reset(token)

    assert signal == "Overweight"


# ---------------------------------------------------------------------------
# E4 -- the CLI's streaming path
# ---------------------------------------------------------------------------

def _stream_like_the_cli(graph, trade_date, book):
    """Mirror ``cli/run.py``: create_run_state, stream, merge, record.

    Returns the merged state, which is the SAME object mutation must happen to.
    """
    init = graph.create_run_state(TICKER, trade_date, "stock", book)
    args = graph.propagator.get_graph_args()
    final_state: dict = {}
    for _messages, chunk in graph.stream_run(graph.checkpoint_input(init), **args):
        if isinstance(chunk, dict):
            final_state.update(chunk)
    graph.record_decision(TICKER, trade_date, final_state)
    return final_state


def test_e4_the_cli_streaming_path_is_gated_and_the_capture_is_closed(
    tmp_path, monkeypatch, offline
):
    graph = make_graph(tmp_path, monkeypatch, intent=OVERSIZE_INTENT)

    final_state = _stream_like_the_cli(graph, TRADE_DATE, BOOK)

    # The CLI's own object was mutated in place -- it holds no other reference.
    assert final_state["final_rating"] == "Hold"
    guardrail = final_state["guardrail"]
    assert guardrail["passed"] is False
    assert guardrail["audit"]["trigger"] == "POSITION_LIMIT"
    assert guardrail["original_rating"] == "Overweight"

    # A streamed run leaves no half-open capture behind.
    assert graph._capture is None
    assert graph._capture_finished is True
    assert graph._capture_calls          # the vendor calls were captured

    trace = guardrail["trace"]
    assert trace["traceable"] is True
    assert trace["snapshot_count"] > 0
    assert trace["findings"] == []
    assert sidecar_path(tmp_path / "results").is_file()
    assert memory_ratings(graph) == ["Hold"]


def test_e4_the_streaming_path_passes_when_the_order_is_within_limits(
    tmp_path, monkeypatch, offline
):
    graph = make_graph(tmp_path, monkeypatch, intent=PASSING_INTENT)

    final_state = _stream_like_the_cli(graph, TRADE_DATE, BOOK)

    assert final_state["final_rating"] == "Overweight"
    assert final_state["guardrail"]["passed"] is True
    assert graph._capture is None and graph._capture_finished is True
    assert final_state["guardrail"]["trace"]["traceable"] is True
    assert memory_ratings(graph) == ["Overweight"]


# ---------------------------------------------------------------------------
# E5 -- determinism of the evidence chain on a real run
# ---------------------------------------------------------------------------

def _chain(tmp_path, monkeypatch, offline) -> dict:
    """Run one scripted run in its own temp tree and return its trace payload."""
    graph = make_graph(tmp_path, monkeypatch, intent=PASSING_INTENT)
    state, _signal = graph.propagate(TICKER, TRADE_DATE, portfolio=BOOK)
    return state["guardrail"]["trace"]


def test_e5_the_same_run_twice_produces_the_same_evidence_chain(
    tmp_path, monkeypatch, offline
):
    """Ids are content-derived, so replaying a run must replay its evidence.

    The timestamps differ between the two runs -- that is the clock doing its
    job -- so the comparison is over the table's identity columns only, never
    the whole sidecar.
    """
    first = _chain(tmp_path / "first", monkeypatch, offline)
    second = _chain(tmp_path / "second", monkeypatch, offline)

    assert first["traceable"] is True and second["traceable"] is True
    assert first["snapshot_count"] == second["snapshot_count"] > 0
    assert first["checked_links"] == second["checked_links"] > 0
    assert first["decision_id"] == second["decision_id"]

    def identity_columns(trace):
        return [(row["assertion_id"], row["referenced_data_snapshot_id"]) for row in trace["table"]]

    assert identity_columns(first) == identity_columns(second)

    # The snapshots themselves -- not just their count -- are the same set.
    snapshot_ids_first = {row["referenced_data_snapshot_id"] for row in first["table"]}
    snapshot_ids_second = {row["referenced_data_snapshot_id"] for row in second["table"]}
    assert snapshot_ids_first == snapshot_ids_second
    assert len(snapshot_ids_first) == first["snapshot_count"]


def test_e5_the_snapshot_ids_are_the_content_digest_form(tmp_path, monkeypatch, offline):
    """An id names the date, the method and a digest -- nothing about the clock."""
    trace = _chain(tmp_path, monkeypatch, offline)
    for snapshot_id in {row["referenced_data_snapshot_id"] for row in trace["table"]}:
        assert snapshot_id.startswith(f"snap-{TRADE_DATE}-")


def test_e5_rejections_are_deterministic_too(tmp_path, monkeypatch, offline):
    """The audit record of a rejection is content-derived as well."""
    records = []
    for name in ("first", "second"):
        graph = make_graph(tmp_path / name, monkeypatch, intent=OVERSIZE_INTENT)
        state, _signal = graph.propagate(TICKER, TRADE_DATE, portfolio=BOOK)
        records.append(state["guardrail"]["audit"]["record_id"])
    assert records[0] == records[1]
