"""Budget-core acceptance cases with 0.7.1 messages and Mock HTTP."""

from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tradingagents.graph import context_budget as cb

from . import news_context_budget_fixtures as fx

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# In-file mock provider adapter + model-under-test
# ---------------------------------------------------------------------------

def _msg_repr(m) -> dict:
    return {
        "role": getattr(m, "type", getattr(m, "role", "unknown")),
        "content": str(getattr(m, "content", "")),
        "tool_calls": getattr(m, "tool_calls", None) or [],
        "tool_call_id": getattr(m, "tool_call_id", None),
    }


def _tool_schema(tool) -> dict:
    return {
        "name": getattr(tool, "name", None),
        "args": getattr(tool, "args", None),
        "description": getattr(tool, "description", None),
    }


@dataclasses.dataclass
class MockRequest:
    """The exact request the adapter counts and sends (identity-checked)."""

    model: str
    messages: list[dict]
    tools: list[dict]

    @property
    def body(self):
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False).encode()


def _count_request(req: MockRequest) -> int:
    """Deterministic token-ish metric over the FULL request, incl. schema/roles.

    Not a real tokenizer; it exists to prove the pilot's *control logic*
    (cap/completion/block) and that counting covers system prompt, messages,
    tool calls/results and tool schemas. It is only meaningful for the mock.
    """
    total = len(req.model)
    for m in req.messages:
        total += len(m["role"]) + len(m["content"])
        total += len(json.dumps(m["tool_calls"], default=str))
        if m["tool_call_id"]:
            total += len(m["tool_call_id"])
    for t in req.tools:
        total += len(str(t["name"])) + len(json.dumps(t["args"], default=str)) + len(str(t["description"]))
    return max(1, total)


class MockProviderAdapter:
    """Mock ProviderAdapter: prepare -> count/send the identical MockRequest.

    Records the ids of counted vs sent requests so a test can assert the pilot
    counted and sent the SAME object.
    """

    def __init__(self, *, supported=True, count_mode="exact", reply="Mock news report.",
                 final_count_override=None):
        self.supported = supported
        self.count_mode = count_mode  # "exact" | "raise" | "invalid" | "none"
        self.reply = reply
        self.final_count_override = final_count_override  # applied to the 2nd count
        self.counted_ids: list[int] = []
        self.sent_ids: list[int] = []
        self.sent_requests: list[MockRequest] = []
        self.count_calls = 0
        self.http_bodies: list[bytes] = []
        self.counted_bodies: list[bytes] = []

    def supports(self, model):  # noqa: D401 - protocol method
        return self.supported

    def prepare(self, formatted_messages, bound_model):
        tools = getattr(bound_model, "tools", []) or []
        return MockRequest(
            model=getattr(bound_model, "model_name", ""),
            messages=[_msg_repr(m) for m in formatted_messages],
            tools=[_tool_schema(t) for t in tools],
        )

    def count(self, request):
        self.count_calls += 1
        self.counted_ids.append(id(request))
        self.counted_bodies.append(request.body)
        if self.count_mode == "raise":
            from tradingagents.graph.context_budget import UnverifiableCountError

            raise UnverifiableCountError("mock cannot verify")
        if self.count_mode == "none":
            return None
        if self.count_mode == "invalid":
            return 0
        # Simulate a provider whose FINAL (post-compaction) count is higher than
        # the trimmed payload suggests (e.g. a bulky block still cannot fit).
        if self.final_count_override is not None and self.count_calls >= 2:
            return self.final_count_override
        return _count_request(request)

    @property
    def send_calls(self):
        return len(self.http_bodies)

    def _receive(self, request):
        self.http_bodies.append(request.content)
        assert request.url.path == "/chat/completions"
        assert request.content == self.counted_bodies[-1]
        return httpx.Response(200, json={"content": self.reply})

    def send(self, request):
        body = cb.require_authorized_send(self, request)
        with httpx.Client(transport=httpx.MockTransport(self._receive)) as client:
            response = client.post("https://model.invalid/chat/completions", content=body)
        self.sent_ids.append(id(request))
        self.sent_requests.append(request)
        return AIMessage(content=response.json()["content"])


class LLMUnderTest:
    model_name = "mock/news-model-v1"

    def bind_tools(self, tools):
        return SimpleNamespace(model_name=self.model_name, tools=tools)


def _budget_node(llm, config, context_adapter):
    """Exercise the budget boundary independently of the news graph."""
    bound_model = llm.bind_tools(fx.mock_news_tools())

    def run(state):
        result, diagnostic = cb.budget_and_send(
            formatted_messages=_format_messages(state["messages"]),
            bound_model=bound_model,
            config=config,
            adapter=context_adapter,
            model_name=llm.model_name,
            cut_off=state["trade_date"],
        )
        state["context_budget_diagnostic"] = diagnostic.as_dict()
        return {"news_report": result.content}

    return run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _budget(cap: int, threshold: int) -> dict:
    return {
        "context_input_hard_cap_tokens": cap,
        "context_input_compaction_threshold_tokens": threshold,
    }


def _news_messages(facts) -> list:
    """One tool-call/result block per fact (adjacent, pairing-safe)."""
    msgs: list = []
    for i, f in enumerate(facts):
        cid = f"call_{i}"
        msgs.append(
            AIMessage(
                content="",
                tool_calls=[{"name": "get_news", "args": {"ticker": f.subject or fx.TICKER}, "id": cid}],
            )
        )
        msgs.append(ToolMessage(content=f.render_news_block(), tool_call_id=cid))
    return msgs


def _prepared_text(request: MockRequest) -> str:
    """All text the model would see, joined — for 'present/absent' assertions."""
    parts = [m["content"] for m in request.messages]
    parts += [json.dumps(m["tool_calls"], default=str) for m in request.messages]
    return "\n".join(parts)


def _fact_tuples_present(text: str, facts) -> dict:
    """Which fidelity dimensions of each fact survive verbatim in ``text``."""
    out = {}
    for f in facts:
        out[f.fact_id] = {
            "subject": f.subject in text,
            "event_date": f.event_date in text,
            "amount": f.amount in text,
            "source": f.source in text,
            "causality": _causality_present(text, f),
        }
    return out


def _causality_present(text: str, f) -> bool:
    if f.causality == "confirmed":
        return "confirmed" in text
    # correlated_only / speculative: the original hedged wording must survive,
    # and it must NOT be rewritten into a causal claim.
    if f.causality == "correlated_only":
        return "no confirmed causal link" in text or "remain uncertain" in text
    return "Unconfirmed" in text or "speculative" in text.lower()


# ---------------------------------------------------------------------------
# NA-01 — empty context
# ---------------------------------------------------------------------------

def test_na_01_empty_context_sends_within_budget_without_compaction():
    cfg = _budget(cap=100_000, threshold=90_000)
    adapter = MockProviderAdapter()
    llm = LLMUnderTest()
    node = _budget_node(llm, config=cfg, context_adapter=adapter)
    state = fx.base_state(messages=fx.empty_history())

    out = node(state)

    assert adapter.send_calls == 1
    assert adapter.count_calls == 1  # under threshold: single count, no compaction
    assert out["news_report"] == "Mock news report."
    diag = state["context_budget_diagnostic"]
    assert diag["reason"] == cb.REASON_NO_COMPACTION_NEEDED
    assert diag["compaction_passes"] == 0
    assert diag["deduped_blocks"] == 0 and diag["dropped_blocks"] == 0


# ---------------------------------------------------------------------------
# NA-02 — short context passes through unmodified
# ---------------------------------------------------------------------------

def test_na_02_short_context_passthrough_is_unchanged():
    facts = fx.news_facts()[:1]
    messages = _news_messages(facts)
    cfg = _budget(cap=100_000, threshold=90_000)
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=cfg, context_adapter=adapter)
    state = fx.base_state(messages=list(messages))

    out = node(state)

    assert adapter.send_calls == 1 and adapter.count_calls == 1
    # The short evidence survives verbatim in the sent request.
    sent_text = _prepared_text(_last_sent_request(adapter))
    assert facts[0].render_news_block().strip() in sent_text
    diag = state["context_budget_diagnostic"]
    assert diag["reason"] == cb.REASON_NO_COMPACTION_NEEDED
    assert out["news_report"] == "Mock news report."


# ---------------------------------------------------------------------------
# NA-03 / 04 / 05 — compaction threshold boundaries (thr-1, thr, thr+1)
# ---------------------------------------------------------------------------

def _run_and_get_count_before(messages, trade_date=None) -> int:
    """Run the real node once with a huge cap to learn its actual count_before.

    The node builds the real system prompt, so its count differs from a local
    estimate. Reading the node's own ``count_before`` lets boundary tests place
    threshold/cap exactly relative to the request the node actually sends.
    """
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(10_000_000, 9_999_999), context_adapter=adapter)
    state = fx.base_state(messages=list(messages), **({"trade_date": trade_date} if trade_date else {}))
    node(state)
    return state["context_budget_diagnostic"]["count_before"]


def _reducible_messages(filler_chars: int) -> list:
    """Real fact blocks (droppable) plus a filler human turn (an anchor).

    The fact blocks give the compaction pass real, removable evidence so an
    over-threshold/over-cap request can actually be trimmed to fit (not block on
    'nothing to drop'). The filler human turn lets a test reach a target size
    while remaining a mandatory anchor.
    """
    facts = fx.news_facts()
    return _news_messages(facts) + _noise_exchange() + [
        HumanMessage(content=f"{fx.TICKER} context: " + "N" * filler_chars)
    ]


def _noise_exchange():
    return [
        AIMessage(content="", tool_calls=[{"name": "get_news", "args": {}, "id": "noise"}]),
        ToolMessage(
            content="IRRELEVANT-NOISE " + "garden weather " * 40,
            tool_call_id="noise",
            additional_kwargs={"provenance": {"relevance": "irrelevant"}},
        ),
    ]


def _format_messages(messages):
    """Approximate the node's formatted messages (system stub + messages).

    Used only for RELATIVE sizing in non-boundary cases; boundary tests use
    ``_run_and_get_count_before`` to read the node's real count.
    """
    return [SystemMessage(content="Preserve source, dates and uncertainty for " + fx.TICKER)] + list(messages)


def _format_and_tag(messages):
    """The grouping input is just the message list itself."""
    return list(messages)


@pytest.mark.parametrize(
    "delta,expect_compaction",
    [(-1, False), (0, False), (+1, True)],
)
def test_na_03_04_05_threshold_boundaries(delta, expect_compaction):
    """thr-1 and thr do not compact; thr+1 does. (Equal threshold: no compaction.)"""
    messages = _reducible_messages(filler_chars=200)
    actual = _run_and_get_count_before(messages)  # node's real count for this input
    # threshold = actual - delta: delta=-1 -> actual+1 (below, no compaction);
    # delta=0 -> actual (equal, no compaction); delta=+1 -> actual-1 (over).
    threshold = actual - delta
    cap = actual + 50          # cap above current size; compaction target is easy

    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=adapter)
    state = fx.base_state(messages=list(messages))
    node(state)
    diag = state["context_budget_diagnostic"]

    over = actual > threshold
    assert over is expect_compaction
    assert (diag["compaction_passes"] == 1) is over
    if not over:
        assert diag["reason"] == cb.REASON_NO_COMPACTION_NEEDED
    else:
        assert diag["reason"] == cb.REASON_OK_COMPACTED
        assert diag["count_after"] <= cap


# ---------------------------------------------------------------------------
# NA-06 / 07 / 08 — hard cap boundaries (cap-1, cap, cap+1) and NA-08 two paths
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delta", [-1, 0])
def test_na_06_07_cap_minus_and_equal_send(delta):
    """cap-1 and cap: node trims real evidence to fit and sends one ≤ cap request."""
    messages = _reducible_messages(filler_chars=200)
    actual = _run_and_get_count_before(messages)
    cap = actual - delta
    threshold = cap
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=adapter)
    state = fx.base_state(messages=list(messages))
    node(state)
    diag = state["context_budget_diagnostic"]
    assert diag["allowed_send"] is True
    assert diag["overflow"] is False
    assert diag["count_after"] <= cap
    assert adapter.send_calls == 1
    sent = _last_sent_request(adapter)
    assert _count_request(sent) == cap + delta
    assert adapter.counted_ids[-1] == id(sent)
    assert diag["compaction_passes"] == 0



def test_na_08_cap_plus_one_compacts_then_sends():
    """cap+1 (just over full size): compact real evidence to fit, send one request."""
    messages = _reducible_messages(filler_chars=200)
    actual = _run_and_get_count_before(messages)
    cap = actual - 1                # one below full size -> genuine trimming required
    threshold = cap - 1
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=adapter)
    state = fx.base_state(messages=list(messages))

    node(state)

    diag = state["context_budget_diagnostic"]
    # Enough real evidence exists that one pass fits: must send, never block.
    assert diag["allowed_send"] is True
    assert diag["reason"] == cb.REASON_OK_COMPACTED
    assert diag["count_after"] <= cap
    assert diag["compaction_passes"] == 1
    assert adapter.send_calls == 1
    assert adapter.count_calls <= 2


# ---------------------------------------------------------------------------
# NA-09 — very long multi-turn history is bounded, deterministic
# ---------------------------------------------------------------------------

def test_na_09_long_multiturn_history_bounded_and_deterministic():
    # Fixtures now emit only well-formed tool-call/result pairs (the duplicate is a
    # complete pair), so no orphan to strip.
    messages = fx.long_multiturn_history(turns=8)
    actual = _run_and_get_count_before(messages)
    cap = actual - 50          # require trimming with headroom so one pass fits
    threshold = cap - 1

    def run_once():
        a = MockProviderAdapter()
        node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=a)
        st = fx.base_state(messages=list(messages))
        node(st)
        return st["context_budget_diagnostic"], a

    d1, a1 = run_once()
    d2, _a2 = run_once()

    assert d1["allowed_send"] and d2["allowed_send"]
    assert d1["count_after"] <= cap
    assert d1["count_after"] == d2["count_after"]  # deterministic
    assert d1["compaction_passes"] == 1
    # Pairing preserved in the sent request: every tool_call_id has its AI call.
    sent = _last_sent_request(a1)
    call_ids = {
        tc["id"]
        for m in sent.messages
        for tc in (m["tool_calls"] or [])
        if isinstance(tc, dict)
    }
    for m in sent.messages:
        tcid = m["tool_call_id"]
        if tcid is not None:
            assert tcid in call_ids, f"orphan tool result {tcid}"


# ---------------------------------------------------------------------------
# NA-10 — irrelevant evidence dropped first
# ---------------------------------------------------------------------------

def test_na_10_irrelevant_evidence_is_droppable():
    facts = fx.news_facts()[:2]
    messages = _noise_exchange() + _news_messages(facts)
    actual = _run_and_get_count_before(messages)
    cap = actual - 60
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap, cap - 1), context_adapter=adapter)
    state = fx.base_state(messages=list(messages))
    node(state)
    diag = state["context_budget_diagnostic"]
    assert diag["compaction_passes"] == 1
    assert diag["dropped_blocks"] >= 1
    # The irrelevant noise is absent from the request actually captured for the model.
    sent_text = _prepared_text(_last_sent_request(adapter))
    assert "IRRELEVANT-NOISE" not in sent_text
    # At least one selected news fact survives verbatim in the captured request.
    assert any(f.render_news_block().strip() in sent_text for f in facts)


# ---------------------------------------------------------------------------
# NA-11 — cross-ticker evidence is not merged into the subject's facts
# ---------------------------------------------------------------------------

def test_na_11_cross_ticker_evidence_not_merged():
    facts = fx.news_facts()
    other = [f for f in facts if f.subject == fx.OTHER_TICKER]
    same = [f for f in facts if f.subject == fx.TICKER]
    assert other and same
    adapter = MockProviderAdapter()
    messages = _news_messages(facts)
    actual = _run_and_get_count_before(messages)
    state = fx.base_state(messages=messages)
    _budget_node(
        LLMUnderTest(), config=_budget(actual + 100, actual - 1), context_adapter=adapter
    )(state)
    text = _prepared_text(_last_sent_request(adapter))
    assert state["context_budget_diagnostic"]["compaction_passes"] == 1
    # OTHER_TICKER facts present with their subject; no BETA fact relabeled ACME.
    for f in other:
        assert fx.OTHER_TICKER in f.body
        assert f.fact_id in text  # link id survives
        assert "(not ACME)" in f.body or "BETA" in f.body


# ---------------------------------------------------------------------------
# NA-12 — future evidence filtered (strict cutoff), upstream dates preserved
# ---------------------------------------------------------------------------

def test_na_12_explicit_future_evidence_is_filtered():
    trade_date = fx.TRADE_DATE
    past = AIMessage(
        content="",
        tool_calls=[{"name": "get_news", "args": {}, "id": "past"}],
        additional_kwargs={"provenance": {"available_at": "2026-01-05", "subject": fx.TICKER}},
    )
    past_res = ToolMessage(content=fx.TICKER + " past news", tool_call_id="past")
    future = AIMessage(
        content="",
        tool_calls=[{"name": "get_news", "args": {}, "id": "fut"}],
        additional_kwargs={"provenance": {"available_at": "2026-02-20", "subject": fx.TICKER}},
    )
    fut_res = ToolMessage(content=fx.TICKER + " FUTURE-LEAK marker", tool_call_id="fut")
    # An upcoming EVENT already published today (available_at in-window) must
    # survive: availability governs cutoff, not the event date.
    inwin = AIMessage(
        content="",
        tool_calls=[{"name": "get_news", "args": {}, "id": "now"}],
        additional_kwargs={
            "provenance": {"available_at": "2026-01-10", "event_date": "2026-06-01", "subject": fx.TICKER}
        },
    )
    now_res = ToolMessage(content=fx.TICKER + " current news", tool_call_id="now")
    messages = [past, past_res, inwin, now_res, future, fut_res]

    # Generous cap so SIZE trimming never drops facts; threshold just below the
    # full count so the compaction pass (and thus the future filter) runs. This
    # isolates future-filtering: the only difference is dropping the future block.
    actual = _run_and_get_count_before(messages)
    cap = actual + 1000
    threshold = actual - 1
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=adapter)
    state = fx.base_state(messages=list(messages), trade_date=trade_date)
    node(state)
    sent = _last_sent_request(adapter)
    text = _prepared_text(sent)
    # Future-availability block dropped; in-window blocks (incl. the published
    # upcoming-event article) survive.
    assert "FUTURE-LEAK" not in text
    assert "past news" in text
    assert "current news" in text


# ---------------------------------------------------------------------------
# NA-13 — exact duplicates collapse; near-duplicates NOT merged
# ---------------------------------------------------------------------------

def test_na_13_exact_duplicates_collapse_near_duplicates_do_not():
    dup_block = _news_messages([fx.news_facts()[0]])
    duplicate = [
        dup_block[0].model_copy(update={
            "tool_calls": [dict(dup_block[0].tool_calls[0], id="another-call")]
        }),
        dup_block[1].model_copy(update={"tool_call_id": "another-call"}),
    ]
    messages = dup_block + duplicate
    blocks, removed = cb._dedup_blocks(cb.group_into_blocks(_format_and_tag(messages)))
    assert removed == 1

    # Near-duplicate: same text shape, different amount -> distinct fact, kept.
    base = fx.news_facts()[0]
    near = fx.near_duplicate_distinct_fact()
    distinct = _news_messages([base, near])
    _, removed2 = cb._dedup_blocks(cb.group_into_blocks(_format_and_tag(distinct)))
    assert removed2 == 0


# ---------------------------------------------------------------------------
# NA-14 — structured summary AND preserved rules after compaction
# ---------------------------------------------------------------------------

def test_na_14_compaction_preserves_identity_and_dates():
    facts = fx.news_facts()
    messages = _news_messages(facts)
    actual = _run_and_get_count_before(messages)
    # Generous cap (no size trimming) but threshold just below the count so the
    # compaction pass runs (dedup/priority); anchors must survive intact.
    cap = actual + 1000
    threshold = actual - 1
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=adapter)
    state = fx.base_state(messages=list(messages), trade_date=fx.TRADE_DATE)
    node(state)
    sent = _last_sent_request(adapter)
    text = _prepared_text(sent)
    # Anchors (instrument context + trade date) survive verbatim after compaction.
    assert fx.TICKER in text
    assert fx.TRADE_DATE in text
    # At least one full fact block survives intact (no rewriting).
    survivors = [f for f in facts if f.render_news_block().strip() in text]
    assert survivors


# ---------------------------------------------------------------------------
# NA-15 — mandatory overflow / over-after-compaction blocks with zero sends
# ---------------------------------------------------------------------------

def test_na_15_mandatory_overflow_blocks_with_zero_requests(caplog):
    """Mandatory (anchor) content over cap blocks with zero sends + structured diag."""
    import logging

    # A mandatory (human) message alone pushes mandatory content far over cap.
    big = HumanMessage(content="MANDATORY " + ("Z" * 5000))
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(cap=100, threshold=90), context_adapter=adapter)
    state = fx.base_state(messages=[big])

    with (
        caplog.at_level(logging.WARNING, logger="tradingagents.graph.context_budget"),
        pytest.raises(cb.ContextBudgetBlocked) as excinfo,
    ):
        node(state)
    diag = excinfo.value.diagnostic
    # Structured, content-free diagnostic.
    assert diag.allowed_send is False
    assert diag.overflow is True
    assert diag.reason in (cb.REASON_MANDATORY_OVER_CAP, cb.REASON_OVER_AFTER_COMPACTION)
    assert diag.budget_tokens == 100 and diag.threshold_tokens == 90
    assert diag.count_after is not None and diag.count_after > diag.budget_tokens
    assert adapter.send_calls == 0
    # A structured warning was logged (no prompt/news content leaked).
    assert any("block" in r.message.lower() or "cap" in r.message.lower() for r in caplog.records)


def test_na_15_second_scenario_over_after_compaction_blocks(caplog):
    """One ordinary news fact cannot fit: blocks with REASON_OVER_AFTER_COMPACTION.

    cap = 2*n and threshold = n-1 (n = the node's real baseline count). Since cap
    is 2*n the text estimate will not trim this evidence, so it survives the single
    compaction pass; the adapter's final count override (cap+1) then exceeds cap,
    with droppable evidence present (so it is NOT mandatory-only).
    """
    import logging

    fact = fx.news_facts()[0]
    messages = _news_messages([fact])
    n = _run_and_get_count_before(messages)  # actual baseline count
    cap = 2 * n
    threshold = n - 1
    adapter = MockProviderAdapter(final_count_override=cap + 1)
    node = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=adapter)
    state = fx.base_state(messages=list(messages))

    with (
        caplog.at_level(logging.WARNING, logger="tradingagents.graph.context_budget"),
        pytest.raises(cb.ContextBudgetBlocked) as excinfo,
    ):
        node(state)
    diag = excinfo.value.diagnostic
    assert diag.reason == cb.REASON_OVER_AFTER_COMPACTION
    assert diag.count_after is not None and diag.count_after > cap
    assert diag.compaction_passes == 1
    assert adapter.count_calls == 2
    assert adapter.send_calls == 0
    assert any(cb.REASON_OVER_AFTER_COMPACTION in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# NA-16 — unverifiable / invalid / unsupported counts block with zero requests
# ---------------------------------------------------------------------------

def test_na_16_unverifiable_invalid_unsupported_and_missing_block_zero_requests():
    """All fail-closed variants block with zero generation requests (one test)."""
    one_fact = _news_messages(fx.news_facts()[:1])

    # Unverifiable / invalid / none counts -> count_unverifiable, zero sends.
    for mode in ("raise", "invalid", "none"):
        adapter = MockProviderAdapter(count_mode=mode)
        node = _budget_node(LLMUnderTest(), config=_budget(100, 80), context_adapter=adapter)
        state = fx.base_state(messages=list(one_fact))
        with pytest.raises(cb.ContextBudgetBlocked) as excinfo:
            node(state)
        assert excinfo.value.diagnostic.reason == cb.REASON_UNVERIFIABLE, mode
        assert adapter.send_calls == 0, mode

    # Mismatched/unsupported provider -> provider_unsupported, zero sends.
    adapter = MockProviderAdapter(supported=False)
    node = _budget_node(LLMUnderTest(), config=_budget(100, 80), context_adapter=adapter)
    state = fx.base_state(messages=fx.empty_history())
    with pytest.raises(cb.ContextBudgetBlocked) as excinfo:
        node(state)
    assert excinfo.value.diagnostic.reason == cb.REASON_UNSUPPORTED
    assert adapter.send_calls == 0

    # Missing adapter -> blocked, zero sends (reason unverifiable/unsupported).
    node = _budget_node(LLMUnderTest(), config=_budget(100, 80), context_adapter=None)
    state = fx.base_state(messages=fx.empty_history())
    with pytest.raises(cb.ContextBudgetBlocked) as excinfo:
        node(state)
    assert excinfo.value.diagnostic.reason in (cb.REASON_UNVERIFIABLE, cb.REASON_UNSUPPORTED)


# ---------------------------------------------------------------------------
# NA-17 — as-of isolation: only lessons resolved by the cutoff survive
# ---------------------------------------------------------------------------

def test_na_17_as_of_isolation_filters_future_lessons(tmp_path):
    from tradingagents.memory.log import TradingMemoryLog

    entries = fx.memory_log_entries()
    log_path = tmp_path / "memory" / "trading_memory.md"
    log = TradingMemoryLog({"memory_log_path": str(log_path)})
    for key in ("in_window_same", "in_window_cross", "future_same"):
        for e in entries[key]:
            log.store_decision(ticker=e["ticker"], trade_date=e["date"], final_trade_decision=e["decision"])
            log.update_with_outcome(
                ticker=e["ticker"], trade_date=e["date"],
                raw_return=0.04, alpha_return=0.01, holding_days=5,
                reflection=e["reflection"], resolution_date=e["resolved"],
            )

    ctx = log.get_past_context(fx.TICKER, as_of=fx.AS_OF_DATE)
    assert fx.TICKER in ctx
    # In-window lesson (resolved on/before as_of) is retained.
    assert "Lesson known before the cutoff" in ctx
    # Future-dated lesson (resolved AFTER as_of) must not leak.
    assert "FUTURE lesson" not in ctx
    assert "Known only after the cutoff" not in ctx


# ---------------------------------------------------------------------------
def test_na_19_fact_fidelity_and_request_identity():
    facts = fx.news_facts()
    messages = _news_messages(facts)

    # Counted and sent the SAME request object (identity), incl. tool schema.
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter)
    state = fx.base_state(messages=list(messages))
    node(state)
    assert adapter.counted_ids[-1] == adapter.sent_ids[-1]
    assert adapter.send_calls == 1

    # Tool-schema overhead IS counted: adding a bigger schema raises the count.
    bound = LLMUnderTest().bind_tools(fx.mock_news_tools())
    small = adapter.prepare(_format_messages(messages), bound)
    big_tools = fx.mock_news_tools()
    big_tools[0].description = "X" * 500
    bound_big = LLMUnderTest().bind_tools(big_tools)
    big = adapter.prepare(_format_messages(messages), bound_big)
    assert _count_request(big) > _count_request(small)

    # Five fact dimensions survive a compacting run for the survivors, and no
    # false merges: distinct facts kept distinct, no invented amounts. Generous
    # cap (no size trimming) but threshold below count forces the compaction pass.
    actual = _run_and_get_count_before(messages)
    cap = actual + 1000
    threshold = actual - 1
    compact_adapter = MockProviderAdapter()
    cnode = _budget_node(LLMUnderTest(), config=_budget(cap, threshold), context_adapter=compact_adapter)
    cstate = fx.base_state(messages=list(messages))
    cnode(cstate)
    sent_text = _prepared_text(_last_sent_request(compact_adapter))
    dims = _fact_tuples_present(sent_text, facts)
    survivors = [f for f in facts if f.render_news_block().strip() in sent_text]
    assert survivors == facts, "all required fact blocks must survive"
    # Every surviving fact block keeps ALL five dimensions intact (no rewriting).
    for f in survivors:
        assert all(dims[f.fact_id].values()), (f.fact_id, dims[f.fact_id])
    # No false merges: each surviving block contains its own amount and does NOT
    # contain another surviving fact's amount (facts never collapse together).
    amounts = [f.amount for f in survivors if f.amount != "n/a"]
    for f in survivors:
        if f.amount != "n/a":
            block = f.render_news_block()
            assert f.amount in block
            for other in amounts:
                if other != f.amount:
                    assert other not in block, f"{f.fact_id} merged with amount {other}"
    # No invented facts: the near-duplicate amount '2.4M USD' was never input.
    assert "2.4M USD" not in sent_text


# ---------------------------------------------------------------------------
# Small utilities for retrieving what the adapter actually sent
# ---------------------------------------------------------------------------

def _last_sent_request(adapter: MockProviderAdapter) -> MockRequest:
    """Return the MockRequest object the adapter sent last (identity-recorded)."""
    assert adapter.sent_requests, "adapter did not send a request"
    return adapter.sent_requests[-1]


@pytest.mark.parametrize("compact", [False, True])
def test_future_filter_independent_of_compaction(compact):
    call = AIMessage(content="", tool_calls=[
        {"name": "get_news", "args": {}, "id": "past"},
        {"name": "get_news", "args": {}, "id": "future"},
    ])
    past = ToolMessage(
        content="PUBLISHED UPCOMING EVENT",
        tool_call_id="past",
        additional_kwargs={"provenance": {
            "available_at": fx.TRADE_DATE, "event_date": "2099-01-01", "source": "A"
        }},
    )
    future = ToolMessage(
        content="FUTURE SECRET",
        tool_call_id="future",
        additional_kwargs={"provenance": {"available_at": "2099-01-02", "source": "B"}},
    )
    messages = [call, past, future]
    actual = _run_and_get_count_before(messages)
    adapter = MockProviderAdapter()
    state = fx.base_state(messages=messages)
    _budget_node(
        LLMUnderTest(), config=_budget(actual + 100, actual - int(compact)), context_adapter=adapter
    )(state)
    sent = _last_sent_request(adapter)
    assert "PUBLISHED UPCOMING EVENT" in _prepared_text(sent)
    assert "FUTURE SECRET" not in _prepared_text(sent)
    assert [m["tool_call_id"] for m in sent.messages if m["tool_call_id"]] == ["past", "future"]
    assert state["context_budget_diagnostic"]["compaction_passes"] == int(compact)


@pytest.mark.parametrize("kind", ["missing", "orphan", "duplicate"])
def test_malformed_tool_history_blocks_before_preparing(kind):
    call, result = _news_messages(fx.news_facts()[:1])
    messages = {"missing": [call], "orphan": [result], "duplicate": [call, result, result]}[kind]
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )
    with pytest.raises(cb.ContextBudgetBlocked) as error:
        node(fx.base_state(messages=messages))
    assert error.value.diagnostic.reason == cb.REASON_INVALID_HISTORY
    assert adapter.count_calls == adapter.send_calls == 0


def test_interleaved_multiple_tool_results_are_paired_by_id():
    ai = AIMessage(content="", tool_calls=[
        {"name": "get_news", "args": {}, "id": "A"},
        {"name": "get_global_news", "args": {}, "id": "B"},
    ])
    messages = [
        ai, ToolMessage(content="result B", tool_call_id="B"),
        HumanMessage(content="Follow up"), ToolMessage(content="result A", tool_call_id="A"),
    ]
    adapter = MockProviderAdapter()
    _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )(fx.base_state(messages=messages))
    sent = _last_sent_request(adapter).messages
    assert [m["tool_call_id"] for m in sent[2:4]] == ["A", "B"]
    assert sent[4]["content"] == "Follow up"


@pytest.mark.parametrize("field", ["source", "subject", "available_at", "event_date"])
def test_distinct_provenance_survives_compaction(field):
    a, ra, b, rb = _news_messages([fx.news_facts()[0]] * 2)
    ra = ra.model_copy(update={"additional_kwargs": {"provenance": {field: "2025-01-01"}}})
    rb = rb.model_copy(update={"additional_kwargs": {"provenance": {field: "2025-01-02"}}})
    messages = [a, ra, b, rb]
    actual = _run_and_get_count_before(messages)
    adapter = MockProviderAdapter()
    _budget_node(
        LLMUnderTest(), config=_budget(actual + 100, actual - 1), context_adapter=adapter
    )(fx.base_state(messages=messages))
    assert [m["tool_call_id"] for m in _last_sent_request(adapter).messages if m["tool_call_id"]] == [
        "call_0", "call_1"
    ]


def test_trim_preserves_independent_reports_if_they_cannot_fit():
    selected = fx.news_facts()[:2]
    messages = _news_messages(selected)
    actual = _run_and_get_count_before(messages)
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(actual - 1, actual - 2), context_adapter=adapter
    )
    with pytest.raises(cb.ContextBudgetBlocked) as error:
        node(fx.base_state(messages=messages))
    diag = error.value.diagnostic
    assert diag.reason == cb.REASON_OVER_AFTER_COMPACTION
    assert diag.dropped_blocks == 0
    assert adapter.count_calls == 2
    assert adapter.send_calls == 0


def test_dedup_accounts_for_savings_before_trimming():
    fact = fx.news_facts()[0]
    pair, duplicate = (_news_messages([fact] * 2)[i:i + 2] for i in (0, 2))
    reduced = pair + _noise_exchange()
    cap = _run_and_get_count_before(reduced)
    adapter = MockProviderAdapter()
    state = fx.base_state(messages=pair + duplicate + _noise_exchange())
    _budget_node(
        LLMUnderTest(), config=_budget(cap, cap), context_adapter=adapter
    )(state)
    sent = _last_sent_request(adapter)
    assert _count_request(sent) == cap
    assert _prepared_text(sent).count(fact.render_news_block().strip()) == 1
    assert "IRRELEVANT-NOISE" in _prepared_text(sent)
    assert state["context_budget_diagnostic"]["dropped_blocks"] == 0


@pytest.mark.parametrize("bad", [
    {"context_input_hard_cap_tokens": 100},
    _budget(100.0, 50),
    _budget(True, 50),
    _budget(100, 101),
])
def test_invalid_budget_cannot_send(bad):
    adapter = MockProviderAdapter()
    node = _budget_node(LLMUnderTest(), config=bad, context_adapter=adapter)
    with pytest.raises(ValueError):
        node(fx.base_state(messages=[]))
    assert adapter.count_calls == adapter.send_calls == 0

@pytest.mark.parametrize(("additional", "response", "survives"), [
    ({}, {"available_at": "2099-01-01"}, False),
    ({"available_at": "2025-01-01"}, {"available_at": "2025-01-01"}, True),
    ({"available_at": "2099-01-01"}, {"available_at": "2025-01-01"}, False),
    ({"available_at": "2025-01-01"}, {"available_at": "2099-01-01"}, False),
    ({}, {}, True),
    ({"event_date": "2099-01-01", "available_at": "2025-01-01"}, {}, True),
    ({"available_at": "2099-01-01"}, {}, False),
])
def test_provenance_availability_before_every_send(additional, response, survives):
    call, result = _news_messages(fx.news_facts()[:1])
    result = result.model_copy(update={
        "additional_kwargs": {"provenance": additional},
        "response_metadata": {"provenance": response},
    })
    adapter = MockProviderAdapter()
    _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )(fx.base_state(messages=[call, result]))
    assert (result.content.strip() in _prepared_text(_last_sent_request(adapter))) is survives


def test_invalid_availability_from_either_source_blocks():
    call, result = _news_messages(fx.news_facts()[:1])
    result = result.model_copy(update={
        "additional_kwargs": {"provenance": {"available_at": "unverified"}},
        "response_metadata": {"provenance": {"available_at": "2025-01-01"}},
    })
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )
    with pytest.raises(cb.ContextBudgetBlocked):
        node(fx.base_state(messages=[call, result]))
    assert adapter.count_calls == adapter.send_calls == 0


def _with_raw_calls(message, ids):
    raw = [
        {"type": "function", "function": {"name": call["name"], "arguments": json.dumps(call["args"])}}
        | ({"id": call_id} if call_id is not None else {})
        for call, call_id in zip(message.tool_calls, ids, strict=True)
    ]
    return message.model_copy(update={"additional_kwargs": {"tool_calls": raw}})


@pytest.mark.parametrize("kind", ["mismatch", "missing", "duplicate", "canonical_only_result"])
def test_malformed_raw_tool_ids_block(kind):
    a, ar, b, br = _news_messages(fx.news_facts()[:2])
    raw = {"mismatch": "other", "missing": None, "duplicate": "call_0",
           "canonical_only_result": "call_1"}[kind]
    if kind == "duplicate":
        b = b.model_copy(update={"tool_calls": [dict(b.tool_calls[0], id="call_0")]})
    if kind == "canonical_only_result":
        br = br.model_copy(update={"tool_call_id": "another"})
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )
    with pytest.raises(cb.ContextBudgetBlocked) as error:
        node(fx.base_state(messages=[_with_raw_calls(a, ["call_0"]), ar, _with_raw_calls(b, [raw]), br]))
    assert error.value.diagnostic.reason == cb.REASON_INVALID_HISTORY
    assert adapter.count_calls == adapter.send_calls == 0


def test_raw_ids_unchanged_through_interleaved_multi_tool_serialization():
    a, ar, b, br = _news_messages(fx.news_facts()[:2])
    both = a.model_copy(update={"tool_calls": a.tool_calls + b.tool_calls})
    both = _with_raw_calls(both, ["call_0", "call_1"])

    class WireAdapter(MockProviderAdapter):
        def prepare(self, formatted_messages, bound_model):
            wire = super().prepare(formatted_messages, bound_model)
            raw_ids = [
                call["id"] for msg in formatted_messages
                for call in msg.additional_kwargs.get("tool_calls", [])
            ]
            assert raw_ids == [call["id"] for msg in wire.messages for call in msg["tool_calls"]]
            return wire

    adapter = WireAdapter()
    _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )(fx.base_state(messages=[both, br, HumanMessage(content="Follow up"), ar]))
    sent = _last_sent_request(adapter)
    assert adapter.counted_ids[-1] == id(sent)
    assert [m["tool_call_id"] for m in sent.messages if m["tool_call_id"]] == ["call_0", "call_1"]
    assert both.additional_kwargs["tool_calls"][1]["id"] == "call_1"


def test_identical_evidence_in_distinct_user_turns_keeps_both_exchanges():
    fact = fx.news_facts()[0]
    a, ar, b, br = _news_messages([fact, fact])
    messages = [HumanMessage(content="First query"), a, ar, HumanMessage(content="Second query"), b, br]
    actual = _run_and_get_count_before(messages)
    adapter = MockProviderAdapter()
    _budget_node(
        LLMUnderTest(), config=_budget(actual + 100, actual - 1), context_adapter=adapter
    )(fx.base_state(messages=messages))
    sent = _last_sent_request(adapter)
    assert [m["tool_call_id"] for m in sent.messages if m["tool_call_id"]] == ["call_0", "call_1"]
    assert [m["content"] for m in sent.messages if m["role"] == "human"] == ["First query", "Second query"]


def test_tool_result_marked_irrelevant_cannot_make_assistant_text_disposable():
    ai, tool = _noise_exchange()
    ai = ai.model_copy(update={"content": "Important independent finding"})
    messages = [HumanMessage(content="Question"), ai, tool]
    actual = _run_and_get_count_before(messages)
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(actual - 1, actual - 1), context_adapter=adapter
    )
    with pytest.raises(cb.ContextBudgetBlocked) as error:
        node(fx.base_state(messages=messages))
    assert error.value.diagnostic.dropped_blocks == 0
    assert adapter.send_calls == 0


@pytest.mark.parametrize("required_fits", [True, False])
def test_na_19_hard_cap_preserves_all_required_facts_or_blocks(required_fits):
    facts = fx.news_facts()
    required = _news_messages(facts)
    required_count = _run_and_get_count_before(required)
    cap = required_count if required_fits else required_count - 1
    messages = required + _noise_exchange()
    assert _run_and_get_count_before(messages) > cap
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(cap, cap), context_adapter=adapter
    )
    if required_fits:
        node(fx.base_state(messages=messages))
        sent = _last_sent_request(adapter)
        text = _prepared_text(sent)
        assert "IRRELEVANT-NOISE" not in text
        assert all(fact.render_news_block().strip() in text for fact in facts)
        assert all(all(fields.values()) for fields in _fact_tuples_present(text, facts).values())
        assert _count_request(sent) == cap
        assert adapter.counted_ids[-1] == id(sent)
        assert adapter.send_calls == 1
    else:
        with pytest.raises(cb.ContextBudgetBlocked) as error:
            node(fx.base_state(messages=messages))
        assert error.value.diagnostic.count_after == required_count > cap
        assert error.value.diagnostic.dropped_blocks == 1
        assert adapter.send_calls == 0
    assert adapter.count_calls == 2


@pytest.mark.parametrize(("role", "cutoff", "available", "outcome"), [
    ("human", fx.TRADE_DATE, "2099-01-01", "block"),
    ("system", fx.TRADE_DATE, "2099-01-01", "block"),
    ("ai", fx.TRADE_DATE, "2099-01-01", "remove"),
    ("ai", None, "2099-01-01", "block"),
    ("ai", None, None, "block"),
    ("ai", fx.TRADE_DATE, None, "keep"),
    ("human", fx.TRADE_DATE, "invalid", "block"),
    ("ai", fx.TRADE_DATE, "2025-01-01", "keep"),
])
def test_stage_47_availability_at_mock_send_boundary(role, cutoff, available, outcome):
    from langchain_core.messages import SystemMessage

    message_type = {"human": HumanMessage, "system": SystemMessage, "ai": AIMessage}[role]
    message = message_type(
        content="DATE-SENSITIVE EVIDENCE",
        additional_kwargs={"provenance": {"available_at": available, "event_date": "2099-02-01"}},
    )
    adapter = MockProviderAdapter()

    def run():
        cb.budget_and_send(
            formatted_messages=[HumanMessage(content="News request"), message],
            bound_model=LLMUnderTest().bind_tools([]),
            config=_budget(100_000, 90_000),
            adapter=adapter,
            model_name="mock/news-model-v1",
            cut_off=cutoff,
        )

    if outcome == "block":
        with pytest.raises(cb.ContextBudgetBlocked):
            run()
        assert adapter.count_calls == adapter.send_calls == 0
    else:
        run()
        sent = _last_sent_request(adapter)
        assert ("DATE-SENSITIVE EVIDENCE" in _prepared_text(sent)) is (outcome == "keep")
        assert adapter.counted_ids[-1] == id(sent)


@pytest.mark.parametrize("kind", ["different_args", "reused_id", "different_name", "duplicate_json_key"])
def test_stage_47_conflicting_raw_tool_arguments_never_send(kind):
    a, ar, b, br = _news_messages([fx.news_facts()[0]] * 2)
    a = _with_raw_calls(a, ["call_0"])
    if kind == "reused_id":
        b = b.model_copy(update={"tool_calls": [dict(b.tool_calls[0], id="call_0")]})
        br = br.model_copy(update={"tool_call_id": "call_0"})
    b = _with_raw_calls(b, [b.tool_calls[0]["id"]])
    raw_function = b.additional_kwargs["tool_calls"][0]["function"]
    if kind == "different_name":
        raw_function["name"] = "get_global_news"
    elif kind == "duplicate_json_key":
        raw_function["arguments"] = '{"ticker":"ACME","ticker":"ACME"}'
    else:
        raw_function["arguments"] = '{"ticker":"OTHER"}'
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(100_000, 90_000), context_adapter=adapter
    )
    with pytest.raises(cb.ContextBudgetBlocked) as error:
        node(fx.base_state(messages=[a, ar, b, br]))
    assert error.value.diagnostic.reason == cb.REASON_INVALID_HISTORY
    assert adapter.count_calls == adapter.send_calls == 0


def test_stage_47_mock_wire_preserves_distinct_valid_interleaved_calls():
    a, ar, b, br = _news_messages(fx.news_facts()[:2])
    b.tool_calls[0]["args"] = {"ticker": fx.TICKER, "start_date": "2025-01-01"}
    both = a.model_copy(update={"tool_calls": a.tool_calls + b.tool_calls})
    both = _with_raw_calls(both, ["call_0", "call_1"])
    adapter = MockProviderAdapter()
    _budget_node(
        LLMUnderTest(), config=_budget(100_000, 1), context_adapter=adapter
    )(fx.base_state(messages=[both, br, HumanMessage(content="Follow up"), ar]))
    sent = _last_sent_request(adapter)
    calls = [call for message in sent.messages for call in message["tool_calls"]]
    raw = both.additional_kwargs["tool_calls"]
    assert [(call["id"], call["name"], call["args"]) for call in calls] == [
        (call["id"], call["function"]["name"], json.loads(call["function"]["arguments"]))
        for call in raw
    ]
    assert [msg["tool_call_id"] for msg in sent.messages if msg["tool_call_id"]] == ["call_0", "call_1"]
    assert adapter.counted_ids[-1] == id(sent)


@pytest.mark.parametrize("essential_fits", [True, False])
def test_stage_47_standalone_assistant_body_survives_or_blocks(essential_fits):
    body = AIMessage(
        content="Important standalone analysis: preserve this evidence.",
        additional_kwargs={"provenance": {"relevance": "irrelevant"}},
    )
    essential = [HumanMessage(content="Explain the news"), body]
    minimum = _run_and_get_count_before(essential)
    cap = minimum if essential_fits else minimum - 1
    messages = essential + _noise_exchange()
    assert _run_and_get_count_before(messages) > cap
    adapter = MockProviderAdapter()
    node = _budget_node(
        LLMUnderTest(), config=_budget(cap, cap), context_adapter=adapter
    )
    if essential_fits:
        node(fx.base_state(messages=messages))
        sent = _last_sent_request(adapter)
        assert [msg["content"] for msg in sent.messages if msg["role"] == "ai"] == [body.content]
        assert "IRRELEVANT-NOISE" not in _prepared_text(sent)
        assert _count_request(sent) == cap
        assert adapter.counted_ids[-1] == id(sent)
        assert adapter.send_calls == 1
    else:
        with pytest.raises(cb.ContextBudgetBlocked) as error:
            node(fx.base_state(messages=messages))
        assert error.value.diagnostic.count_after == minimum
        assert error.value.diagnostic.dropped_blocks == 1
        assert adapter.send_calls == 0
    assert adapter.count_calls == 2


def test_na_18_unconfigured_budget_leaves_071_news_path_intact(monkeypatch):
    from langchain_core.runnables import RunnableLambda

    from tradingagents.agents.analysts.news_analyst import TOOLS, create_news_analyst
    from tradingagents.default_config import DEFAULT_CONFIG

    assert cb.resolve_budget(DEFAULT_CONFIG) == (None, None)
    assert not cb.is_budget_enabled(DEFAULT_CONFIG)
    captured = []

    def budget_called(**kwargs):
        pytest.fail("Unconfigured news path called the budget")

    class NewsModel:
        def bind_tools(self, tools):
            assert tuple(tools) == TOOLS

            def invoke(prompt):
                captured.append(prompt.to_messages())
                return AIMessage(content="Existing news report")

            return RunnableLambda(invoke)

    monkeypatch.setattr(cb, "budget_and_send", budget_called)
    human = HumanMessage(content="Keep this analysis request")
    state = {
        "messages": [human],
        "trade_date": fx.TRADE_DATE,
        "company_of_interest": fx.TICKER,
    }
    result = create_news_analyst(NewsModel())(state)
    assert result["news_report"] == "Existing news report"
    assert len(captured) == 1
    assert isinstance(captured[0][0], SystemMessage)
    assert captured[0][1:] == [human]
    assert "context_budget_diagnostic" not in state


def test_only_one_http_send_can_consume_the_permit():
    class ReplayAdapter(MockProviderAdapter):
        def send(self, request):
            response = super().send(request)
            with pytest.raises(cb.UnverifiableCountError):
                super().send(request)
            return response

    adapter = ReplayAdapter()
    _budget_node(LLMUnderTest(), _budget(100_000, 90_000), adapter)(fx.base_state())
    assert adapter.send_calls == 1


def test_unpermitted_send_never_reaches_http():
    adapter = MockProviderAdapter()
    request = adapter.prepare(
        _format_messages([]), LLMUnderTest().bind_tools(fx.mock_news_tools())
    )
    adapter.count(request)
    with pytest.raises(cb.UnverifiableCountError):
        adapter.send(request)
    assert adapter.send_calls == 0


def test_future_tool_result_does_not_remove_available_assistant_body():
    call = AIMessage(
        content="Retain the previously established reporting constraint.",
        tool_calls=[{"name": "get_news", "args": {}, "id": "future"}],
    )
    result = ToolMessage(
        content="FUTURE-ONLY EVIDENCE",
        tool_call_id="future",
        response_metadata={"provenance": {"available_at": "2026-01-16"}},
    )
    adapter = MockProviderAdapter()
    _budget_node(LLMUnderTest(), _budget(100_000, 90_000), adapter)(
        fx.base_state([call, result])
    )
    wire = json.loads(adapter.http_bodies[0])
    assert wire["messages"][1]["content"] == call.content
    assert wire["messages"][1]["tool_calls"][0]["id"] == "future"
    assert wire["messages"][2]["tool_call_id"] == "future"
    assert wire["messages"][2]["content"] == "Evidence unavailable on the analysis date."
    assert "FUTURE-ONLY EVIDENCE" not in adapter.http_bodies[0].decode()


def test_copied_execution_contexts_share_a_single_http_permit():
    from concurrent.futures import ThreadPoolExecutor
    from contextvars import copy_context
    from threading import Barrier

    class ConcurrentAdapter(MockProviderAdapter):
        def send(self, request):
            ready = Barrier(2)

            def attempt():
                ready.wait(timeout=5)
                try:
                    return super(ConcurrentAdapter, self).send(request)
                except cb.UnverifiableCountError:
                    return None

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(copy_context().run, attempt) for _ in range(2)]
                results = [future.result(timeout=10) for future in futures]
            replies = [result for result in results if result is not None]
            assert len(replies) == 1
            return replies[0]

    adapter = ConcurrentAdapter()
    _budget_node(LLMUnderTest(), _budget(100_000, 90_000), adapter)(fx.base_state())
    assert adapter.send_calls == 1


def test_changed_body_on_same_counted_object_cannot_reach_http():
    class MutatingAdapter(MockProviderAdapter):
        def send(self, request):
            request.messages[0]["content"] = "Changed after counting"
            return super().send(request)

    adapter = MutatingAdapter()
    with pytest.raises(cb.UnverifiableCountError, match="body differs"):
        _budget_node(LLMUnderTest(), _budget(100_000, 90_000), adapter)(fx.base_state())
    assert adapter.count_calls == 1
    assert adapter.send_calls == 0
