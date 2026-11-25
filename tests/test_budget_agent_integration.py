"""Offline tests at the graph's model edge and SDK HTTP transport."""

import json
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import HumanMessage

from cli.stats_handler import StatsCallbackHandler
from tradingagents.agents import tools
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.context_budget import ContextBudgetBlocked
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.deepseek_context_adapter import (
    CITYU_BASE,
    CITYU_MODEL,
    DeepSeekProviderAdapter,
)
from tradingagents.llm_clients.openai_client import DeepSeekChatOpenAI

from .test_graph_end_to_end import ARGS, STRUCTURED, TEXT, TRADE_DATE, offline as offline

MODEL = CITYU_MODEL


def _response(message):
    return httpx.Response(200, json={
        "id": "mock-response", "object": "chat.completion", "model": MODEL,
        "created": 1, "choices": [{"index": 0, "finish_reason": "stop", "message": message}],
        "usage": {"prompt_tokens": 31, "completion_tokens": 7, "total_tokens": 38},
    })


def _graph(
    monkeypatch, tmp_path, model, adapter, *,
    selected=("news",), stub_memory=True, **overrides,
):
    monkeypatch.setattr(
        "tradingagents.graph.trading_graph.create_tier_client",
        lambda *_args, **_kwargs: SimpleNamespace(get_llm=lambda: model),
    )
    if stub_memory:
        monkeypatch.setattr(TradingAgentsGraph, "_memory_step", lambda self, state: {"past_context": ""})
    cfg = DEFAULT_CONFIG | {
        "llm_provider": "deepseek",
        "quick_think_llm": MODEL, "deep_think_llm": MODEL, "backend_url": CITYU_BASE,
        "context_input_hard_cap_tokens": 99_000,
        "context_input_compaction_threshold_tokens": 98_000,
        "results_dir": str(tmp_path / "results"), "data_cache_dir": str(tmp_path / "data"),
        "memory_log_path": str(tmp_path / "memory.md"), "checkpoint_enabled": False,
    } | overrides
    return TradingAgentsGraph(
        selected_analysts=selected, config=cfg,
        context_adapters={"quick": adapter, "deep": adapter},
    )


@pytest.mark.parametrize("tool_round_limit", [1, 2])
def test_news_real_subgraph_counts_tool_turn_and_report_at_sdk_transport(
    monkeypatch, tmp_path, tool_round_limit
):
    wire, counted, tool_results = [], [], []

    def route(method, *args):
        tool_results.append((method, args))
        return "Synthetic reportable evidence"

    monkeypatch.setattr(tools, "route_to_vendor", route)

    def transport(request):
        assert request.url.path == "/v1/chat/completions"
        assert request.content == counted[-1].body
        wire.append(json.loads(request.content))
        if len(wire) == 1:
            return _response({
                "role": "assistant", "content": None, "reasoning_content": "Check the evidence",
                "tool_calls": [{"id": "call-1", "type": "function", "function": {
                    "name": "get_news",
                    "arguments": '{"start_date":"2025-12-28","end_date":"2026-01-02"}',
                }}],
            })
        return _response({"role": "assistant", "content": "Verified synthetic report"})

    def fake_counter(req):
        counted.append(req)
        return len(req.body)

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder", http_client=client,
        )
        adapter = DeepSeekProviderAdapter(
            MODEL, fake_counter, counter_revision="mock-wire-v1", base_url=CITYU_BASE
        )
        graph = _graph(monkeypatch, tmp_path, model, adapter, max_tool_rounds=tool_round_limit)
        result = graph.workflow.compile(interrupt_before=["Bull Researcher"]).invoke({
            "company_of_interest": "ACME", "trade_date": "2026-01-02",
            "messages": [HumanMessage(content="Report on ACME")],
        })

    assert result["news_report"] == "Verified synthetic report"
    assert len(wire) == len(counted) == 2
    assert len(tool_results) == 1
    assert tool_results[0][0] == "get_news"
    assert "tools" in wire[0]
    assert "Synthetic reportable evidence" in json.dumps(wire[1])
    if tool_round_limit == 1:
        assert "tools" not in wire[1]
        assert all(m["role"] != "tool" for m in wire[1]["messages"])
    else:
        assert wire[1]["messages"][-1]["tool_call_id"] == "call-1"
        assert wire[1]["messages"][-2]["reasoning_content"] == "Check the evidence"


@pytest.mark.parametrize("mode", ["no_counter", "overflow", "final_count_failure"])
def test_news_subgraph_blocked_requests_have_zero_http(monkeypatch, tmp_path, mode):
    calls, counts = [], []

    def transport(request):
        calls.append(request)
        pytest.fail("Blocked request reached HTTP")

    def counter(request):
        counts.append(request)
        return None if mode == "final_count_failure" and len(counts) == 2 else 10

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder", http_client=client,
        )
        adapter = DeepSeekProviderAdapter(
            MODEL, None if mode == "no_counter" else counter,
            counter_revision="mock-wire-v1", base_url=CITYU_BASE,
        )
        graph = _graph(
            monkeypatch, tmp_path, model, adapter,
            context_input_hard_cap_tokens=5, context_input_compaction_threshold_tokens=4,
        )
        with pytest.raises(ContextBudgetBlocked):
            graph.workflow.compile(interrupt_before=["Bull Researcher"]).invoke({
                "company_of_interest": "ACME", "trade_date": "2026-01-02",
                "messages": [HumanMessage(content="Report on ACME")],
            })

    assert calls == []
    assert len(counts) == (0 if mode == "no_counter" else 2)


@pytest.mark.usefixtures("offline")
def test_live_graph_all_agent_edges_and_reflection_use_counted_sdk_requests(
    monkeypatch, tmp_path, caplog
):
    from threading import Lock

    counted = {}
    wires = []
    lock = Lock()
    stats = StatsCallbackHandler()
    schemas = {schema.__name__: value for schema, value in STRUCTURED.items()}

    def count(req):
        with lock:
            counted[req.body] = counted.get(req.body, 0) + 1
        return len(req.body)

    def transport(request):
        with lock:
            assert counted.get(request.content, 0) > 0
            counted[request.content] -= 1
            payload = json.loads(request.content)
            wires.append(payload)
        tools = [item["function"] for item in payload.get("tools", [])]
        if tools and tools[0]["name"] in schemas:
            name = tools[0]["name"]
            calls = [{"id": "schema", "type": "function", "function": {
                "name": name, "arguments": schemas[name].model_dump_json(),
            }}]
        elif tools and payload["messages"][-1]["role"] != "tool":
            calls = [
                {"id": f"call-{i}", "type": "function", "function": {
                    "name": item["name"], "arguments": json.dumps({
                        k: v for k, v in ARGS.items() if k in item["parameters"]["properties"]
                    }),
                }}
                for i, item in enumerate(tools)
            ]
        else:
            return _response({"role": "assistant", "content": TEXT})
        return _response({"role": "assistant", "content": None, "tool_calls": calls})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder",
            http_client=client, callbacks=[stats],
        )
        adapter = DeepSeekProviderAdapter(MODEL, count, counter_revision="mock-v1", base_url=CITYU_BASE)
        graph = _graph(
            monkeypatch, tmp_path, model, adapter,
            selected=("market", "social", "news", "fundamentals"),
            max_debate_rounds=2, max_risk_discuss_rounds=2,
        )
        with caplog.at_level("INFO", logger="tradingagents.graph.budgeted_model"):
            state, rating = graph.propagate("NVDA", TRADE_DATE)
            assert graph.reflector.reflect_on_final_decision("Hold", .01, .02) == TEXT

    assert rating == state["final_rating"] == "Overweight"
    decisions = [r.args for r in caplog.records if r.msg == "agent_input_budget %s"]
    assert {item["agent_name"] for item in decisions} == {
        "Market Analyst", "Sentiment Analyst", "News Analyst", "Fundamentals Analyst",
        "Bull Researcher", "Bear Researcher", "Research Manager", "Trader",
        "Aggressive Analyst", "Neutral Analyst", "Conservative Analyst", "Portfolio Manager",
        "Reflection",
    }
    assert len(wires) == len(decisions)
    assert all(item["allowed_send"] and item["counter_exact"] for item in decisions)
    assert all(v == 0 for v in counted.values())
    assert stats.get_stats()["llm_calls"] == len(wires)
    assert stats.get_stats()["tokens_in"] == len(wires) * 31
    assert stats.get_stats()["tokens_out"] == len(wires) * 7
    for payload in wires:
        if payload["messages"][-1]["role"] == "tool":
            names = {tool["function"]["name"] for tool in payload["tools"]}
            utterance = next(m for m in payload["messages"] if m.get("tool_calls"))
            assert {call["function"]["name"] for call in utterance["tool_calls"]} == names
            assert {m["tool_call_id"] for m in payload["messages"] if m["role"] == "tool"} == {
                call["id"] for call in utterance["tool_calls"]
            }


def test_budgeted_sdk_transport_has_no_automatic_retry(monkeypatch, tmp_path):
    import openai

    calls = []

    def transport(request):
        calls.append(request.content)
        return httpx.Response(500, json={"error": {"message": "synthetic upstream failure"}})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder",
            http_client=client, max_retries=3,
        )
        adapter = DeepSeekProviderAdapter(
            MODEL, lambda req: len(req.body), counter_revision="mock-v1", base_url=CITYU_BASE
        )
        graph = _graph(monkeypatch, tmp_path, model, adapter)
        with pytest.raises(openai.InternalServerError):
            graph.workflow.compile(interrupt_before=["Bull Researcher"]).invoke({
                "company_of_interest": "ACME", "trade_date": "2026-01-02",
                "messages": [HumanMessage(content="Analyze ACME")],
            })
    assert len(calls) == 1


def test_unsupported_jev_screen_is_never_sent(monkeypatch):
    from tradingagents.agents import post_screen

    monkeypatch.setenv("TYPESAFE_API_KEY", "synthetic-placeholder")
    monkeypatch.setattr(post_screen.requests, "post", lambda *a, **k: pytest.fail("Jev sent HTTP"))
    assert post_screen.jev_screen("NVDA", budget_config={
        "context_input_hard_cap_tokens": 100,
        "context_input_compaction_threshold_tokens": 90,
    }) is None


def test_disabled_news_graph_preserves_legacy_sdk_bytes(monkeypatch, tmp_path):
    from tradingagents.agents.analysts.news_analyst import create_news_analyst

    wire = []

    def transport(request):
        wire.append(request.content)
        return _response({"role": "assistant", "content": "Original report"})

    state = {
        "company_of_interest": "ACME", "trade_date": "2026-01-02",
        "messages": [HumanMessage(content="Analyze ACME")],
    }
    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder", http_client=client,
        )
        original = create_news_analyst(model)(state)
        graph = _graph(
            monkeypatch, tmp_path, model, None,
            context_input_hard_cap_tokens=None, context_input_compaction_threshold_tokens=None,
        )
        output = graph.workflow.compile(interrupt_before=["Bull Researcher"]).invoke(state)

    assert output["news_report"] == original["news_report"]
    assert len(wire) == 2 and wire[0] == wire[1]


def test_budget_checkpoint_resume_counts_pending_news_and_rejects_changed_counter(
    monkeypatch, tmp_path
):
    wire = []

    def transport(request):
        wire.append(request.content)
        return _response({"role": "assistant", "content": "Resumed report"})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder", http_client=client,
        )
        adapter = DeepSeekProviderAdapter(MODEL, lambda req: len(req.body),
                                          counter_revision="v1-mock", base_url=CITYU_BASE)
        graph = _graph(monkeypatch, tmp_path, model, adapter, checkpoint_enabled=True)
        state = {
            "company_of_interest": "ACME", "trade_date": "2026-01-02",
            "messages": [HumanMessage(content="Analyze ACME")],
        }
        with graph.checkpoint_scope("ACME", "2026-01-02") as initial:
            options = {"configurable": {"thread_id": initial}}
            graph.graph.invoke(state, options, interrupt_before=["News Analyst"])
        assert wire == []
        with graph.checkpoint_scope("ACME", "2026-01-02") as resumed:
            assert resumed == initial
            assert graph.checkpoint_input(state) is None
            result = graph.graph.invoke(
                None, options, interrupt_before=["Bull Researcher"]
            )
        assert result["news_report"] == "Resumed report"
        assert len(wire) == 1
        adapter.counter_revision = "v2-mock"
        with graph.checkpoint_scope("ACME", "2026-01-02") as changed:
            assert changed != initial
            assert graph.checkpoint_input(state) is state
    assert len(wire) == 1


def test_paired_news_faithfulness_on_sdk_wire(monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage, ToolMessage

    constraints = (
        "Ticker: ACME", "Asset Type: stock", "As-of: 2026-01-02",
        "Portfolio: none", "Rating rule: retain all uncertainty verbatim",
    )
    facts = [
        {
            "fact_id": "F1", "ticker": "ACME", "subject": "ACME",
            "event_date": "2025-12-28", "available_at": "2025-12-29",
            "published_at": "2025-12-29", "source": "Synthetic source A",
            "amount": "1.2M USD", "causality": "correlated_only", "relevance": "low",
        },
        {
            "fact_id": "F2", "ticker": "ACME", "subject": "ACME",
            "event_date": "2025-12-30", "available_at": "2025-12-31",
            "published_at": "2025-12-31", "source": "Synthetic source B",
            "amount": "1.3M EUR", "causality": "speculative", "relevance": "required",
        },
    ]
    expected = {f["fact_id"]: f for f in facts}
    state = {
        "company_of_interest": "ACME", "trade_date": "2026-01-02",
        "messages": [HumanMessage(content="\n".join(constraints))],
    }

    def exchange(fact, call_id, trailing=""):
        state["messages"].extend([
            AIMessage(content="", tool_calls=[{"name": "get_news", "id": call_id, "args": {}}]),
            ToolMessage(
                tool_call_id=call_id,
                content="\n".join(f"{k}: {v}" for k, v in fact.items())
                + "\n" + "Unrelated layout filler. " * 130 + trailing,
                additional_kwargs={"provenance": {**fact, "summary_fact": fact}},
            ),
        ])

    exchange(facts[0], "one")
    exchange(facts[0], "dup", "   ")
    exchange(facts[1], "two")
    wire, counts = [], []

    def counter(request):
        counts.append(len(request.body))
        return counts[-1]

    def transport(request):
        wire.append(json.loads(request.content))
        return _response({"role": "assistant", "content": "Paired report"})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder", http_client=client,
        )
        adapter = DeepSeekProviderAdapter(
            MODEL, counter, counter_revision="mock-bytes-v1", base_url=CITYU_BASE
        )
        for cap, threshold in [(None, None), (99_000, 1)]:
            graph = _graph(
                monkeypatch, tmp_path, model, adapter,
                context_input_hard_cap_tokens=cap, context_input_compaction_threshold_tokens=threshold,
            )
            graph.workflow.compile(interrupt_before=["Bull Researcher"]).invoke(state)

    def records(payload):
        return [
            dict(line.split(": ", 1) for line in msg["content"].splitlines() if ": " in line)
            for msg in payload["messages"] if msg["role"] == "tool"
        ]

    first, second = (records(payload) for payload in wire)
    baseline = {record["fact_id"]: record for record in first}
    compacted = {record["fact_id"]: record for record in second}
    errors = sum(
        {key: record.get(key) for key in expected[record["fact_id"]]} != expected[record["fact_id"]]
        for record in second
    )
    preserved = sum(compacted.get(key) == record for key, record in baseline.items())
    preserved_constraints = sum(
        all(any(constraint in message["content"] for message in payload["messages"] if message["content"])
            for payload in wire) for constraint in constraints
    )
    contamination = sum(record["ticker"] != "ACME" for record in second)
    future = sum(record["available_at"] > state["trade_date"] for record in second)
    assert baseline == expected == compacted
    assert len(first) == 3 and len(second) == 2
    assert wire[1]["messages"][3]["content"].startswith("Extracted source fact:")
    assert errors == contamination == future == 0
    assert preserved == len(baseline) and preserved_constraints == len(constraints)
    assert len(counts) == 2 and counts[1] < counts[0]
    print(json.dumps({
        "baseline_facts": len(baseline), "compacted_facts": len(compacted),
        "preserved_facts": preserved, "fact_retention_rate": preserved / len(baseline) if baseline else None,
        "constraints": len(constraints), "preserved_constraints": preserved_constraints,
        "constraint_retention_rate": preserved_constraints / len(constraints) if constraints else None,
        "fact_errors": errors, "cross_ticker_contamination": contamination, "future_leaks": future,
        "mock_count_before": counts[0], "mock_count_after": counts[1],
        "mock_reduction_rate": 1 - counts[1] / counts[0] if counts[0] else None,
    }, sort_keys=True))


def test_missing_production_adapter_blocks_without_initializing_openai(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("A model SDK was initialized for a tier without a verified adapter")

    monkeypatch.setattr("tradingagents.graph.trading_graph.create_tier_client", forbidden)
    monkeypatch.setattr(TradingAgentsGraph, "_memory_step", lambda self, state: {"past_context": ""})
    graph = TradingAgentsGraph(selected_analysts=("news",), config=DEFAULT_CONFIG | {
        "llm_provider": "openai",
        "context_input_hard_cap_tokens": 1000,
        "context_input_compaction_threshold_tokens": 900,
        "results_dir": str(tmp_path / "results"), "data_cache_dir": str(tmp_path / "data"),
        "memory_log_path": str(tmp_path / "memory.md"),
    })
    with pytest.raises(ContextBudgetBlocked, match="count_unverifiable"):
        graph.workflow.compile(interrupt_before=["Bull Researcher"]).invoke({
            "company_of_interest": "ACME", "trade_date": "2026-01-02",
            "messages": [HumanMessage(content="Analyze ACME")],
        })


def test_intraday_cutoff_uses_utc_instant_before_sdk_send(monkeypatch, tmp_path):
    from langchain_core.messages import AIMessage, ToolMessage

    from tradingagents.graph.budgeted_model import BudgetedModel

    sent = []

    def transport(request):
        sent.append(request.content)
        return _response({"role": "assistant", "content": "Filtered"})

    with httpx.Client(transport=httpx.MockTransport(transport)) as client:
        model = DeepSeekChatOpenAI(
            model=MODEL, base_url=CITYU_BASE, api_key="test-placeholder", http_client=client,
        )
        adapter = DeepSeekProviderAdapter(MODEL, lambda req: len(req.body),
                                          counter_revision="mock-v1", base_url=CITYU_BASE)
        g = _graph(monkeypatch, tmp_path, model, adapter)
        boundary = BudgetedModel(model, adapter, g.config, "News Analyst", MODEL)
        messages = [HumanMessage(content="Analyze ACME")]
        for call_id, available in [("before", "2026-01-02T10:00:00+02:00"),
                                   ("after", "2026-01-02T10:00:00Z")]:
            messages.extend([
                AIMessage(content="", tool_calls=[{"name": "get_news", "id": call_id, "args": {}}]),
                ToolMessage(
                    content=f"news-{call_id}", tool_call_id=call_id,
                    additional_kwargs={"provenance": {"available_at": available}},
                ),
            ])
        boundary.invoke_budget(messages, cutoff="2026-01-02T09:00:00Z")
    assert len(sent) == 1
    assert b"news-before" in sent[0] and b"news-after" not in sent[0]
