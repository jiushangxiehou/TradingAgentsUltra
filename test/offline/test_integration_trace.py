"""OFFLINE trace-adapter tests (ADR-006, REQ-TRACEABILITY, INV-TRACE-COMPLETENESS).

Requires no API, no network, no clock. ``DataCapture`` is exercised against
FAKE targets, so nothing here needs the vendored baseline: the sole baseline
import in the module under test is the lazy one inside ``default_targets()``,
and this file never calls it from the pure tests.

Trace boundary under test (ADR-006, policy G1)
----------------------------------------------
A run-level evidence set. Every critical assertion links to the run's whole
deduplicated snapshot set in sorted id order. The tests below therefore assert
the *size* and *contents* of each link set -- never a per-analyst attribution,
which the design deliberately does not claim.
"""

from __future__ import annotations

import ast
import json
import pathlib
import types

import pytest

from src.integration import trace_adapter
from src.integration.trace_adapter import (
    KIND_DIRECT,
    KIND_ROUTE,
    NO_DATA_SUFFIX,
    REPORT_KEYS,
    RESULT_ERROR,
    RESULT_NO_DATA,
    RESULT_OK,
    UNKNOWN_SOURCE,
    CapturedCall,
    DataCapture,
    PatchTarget,
    begin_capture,
    build_trace,
)

pytestmark = pytest.mark.offline

MODULE_PATH = pathlib.Path(trace_adapter.__file__)

# A fixed injected instant: the recorder only accepts tz-aware UTC ISO-8601.
INSTANT = "2026-11-24T00:00:00+00:00"
TRADE_DATE = "2026-11-24"
TICKER = "NVDA"

PAYLOAD_KEYS = {
    "traceable",
    "checked_links",
    "resolved_links",
    "findings",
    "decision_id",
    "snapshot_count",
    "table",
    "unbacked_reports",
    "capture_errors",
    "trace_error",
}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeRouter:
    """A stand-in for ``tradingagents.dataflows.router``.

    ``route_to_vendor`` is a plain attribute, so the capture's ``setattr`` patch
    works exactly as it does on the real module.
    """

    def __init__(self, source: str = "yfinance", explode: bool = False) -> None:
        self.source = source
        self.explode = explode
        self.calls: list[tuple[str, tuple, dict]] = []
        self.route_to_vendor = self._route

    def _route(self, method, *args, **kwargs):
        self.calls.append((method, args, kwargs))
        return f"{method}:{'|'.join(str(a) for a in args)}"

    def get_category_for_method(self, method):
        return "market"

    def get_vendor(self, category, method=None):
        if self.explode:
            raise KeyError("no vendor configured")
        return self.source


def fake_module(**attrs) -> types.SimpleNamespace:
    """A stand-in for any baseline module: plain attributes, patchable."""
    return types.SimpleNamespace(**attrs)


def route_target(router, attr="route_to_vendor") -> PatchTarget:
    return PatchTarget(owner=router, attr=attr, kind=KIND_ROUTE, router_module=router)


def direct_target(module, attr="fetch_reddit_posts", method="reddit", source="reddit"):
    return PatchTarget(owner=module, attr=attr, kind=KIND_DIRECT, method=method, source=source)


def make_calls(*specs) -> tuple[CapturedCall, ...]:
    """Captured calls with deterministic digests: ``(method, source)`` pairs."""

    def digest(tag: str) -> str:
        return (tag * 12)[:12]

    calls = []
    for index, (method, source) in enumerate(specs):
        calls.append(
            CapturedCall(
                method=method,
                data_source=source,
                args_digest=digest(f"a{index}"),
                result_digest=digest(f"r{index}"),
                result_kind=RESULT_OK,
            )
        )
    return tuple(calls)


def full_state(**overrides) -> dict:
    state = {
        "company_of_interest": TICKER,
        "trade_date": TRADE_DATE,
        "market_report": "Market report body.",
        "sentiment_report": "Sentiment report body.",
        "news_report": "News report body.",
        "fundamentals_report": "Fundamentals report body.",
        "final_trade_decision": "**Rating**: Hold",
        "final_rating": "Hold",
    }
    state.update(overrides)
    return state


def trace(*, calls, state=None, started_at=INSTANT, capture_errors=()) -> dict:
    return build_trace(
        calls=calls,
        started_at=started_at,
        final_state=full_state() if state is None else state,
        ticker=TICKER,
        trade_date=TRADE_DATE,
        rating="Hold",
        capture_errors=capture_errors,
    )


# ---------------------------------------------------------------------------
# T0 -- offline marker
# ---------------------------------------------------------------------------

def test_file_is_marked_offline():
    """Pinned R1: every test in this file is offline-marked."""
    assert trace_adapter.build_trace
    assert pytestmark == pytest.mark.offline


# ---------------------------------------------------------------------------
# T1 -- patch / restore identity, one call through, result unchanged
# ---------------------------------------------------------------------------

def test_capture_patches_then_restores_the_same_object():
    router = FakeRouter()
    original = router.route_to_vendor
    capture = begin_capture(INSTANT, [route_target(router)])
    try:
        assert router.route_to_vendor is not original
        assert callable(router.route_to_vendor)
    finally:
        capture.finish()
    assert router.route_to_vendor is original


def test_wrapper_calls_the_original_exactly_once_and_returns_its_value():
    router = FakeRouter()
    capture = begin_capture(INSTANT, [route_target(router)])
    try:
        result = router.route_to_vendor("get_stock_data", "NVDA", "2026-01-01")
    finally:
        calls = capture.finish()
    assert len(router.calls) == 1
    assert result == "get_stock_data:NVDA|2026-01-01"
    assert len(calls) == 1


def test_context_manager_restores_on_normal_exit():
    router = FakeRouter()
    original = router.route_to_vendor
    with DataCapture(INSTANT, (route_target(router),)) as capture:
        assert router.route_to_vendor is not original
        router.route_to_vendor("get_news", "NVDA")
    assert router.route_to_vendor is original
    assert len(capture.finish()) == 1


def test_begin_capture_used_in_a_with_block_restores_the_original():
    """Regression: ``with begin_capture(...)`` must not double-install.

    ``begin_capture`` installs immediately; ``__enter__`` then entered the same
    object and installed a SECOND wrapper. ``finish()`` unwound one layer and
    left a wrapper patched on the module forever. Entering again must be a
    no-op, so one restore is complete.
    """
    router = FakeRouter()
    original = router.route_to_vendor
    with begin_capture(INSTANT, [route_target(router)]) as capture:
        assert router.route_to_vendor is not original
        router.route_to_vendor("get_news", "NVDA")
    assert router.route_to_vendor is original

    calls = capture.finish()
    assert capture.finish() is calls  # idempotent no-op afterwards
    assert router.route_to_vendor is original


def test_entering_an_already_entered_capture_does_not_wrap_again():
    router = FakeRouter()
    original = router.route_to_vendor
    capture = begin_capture(INSTANT, [route_target(router)])
    installed = router.route_to_vendor
    capture.__enter__()
    capture.__enter__()
    assert router.route_to_vendor is installed  # unchanged: no extra layer
    capture.finish()
    assert router.route_to_vendor is original


def test_context_manager_restores_when_the_body_raises():
    """A run that dies still un-patches: the next run must see real functions."""
    router = FakeRouter()
    original = router.route_to_vendor
    with pytest.raises(RuntimeError), DataCapture(INSTANT, (route_target(router),)):
        raise RuntimeError("analyst blew up")
    assert router.route_to_vendor is original


def test_entry_exits_is_the_module_it_claims_to_be():
    assert isinstance(trace_adapter.begin_capture, types.FunctionType)


# ---------------------------------------------------------------------------
# T2 -- route source resolution, with an ``unknown`` fallback
# ---------------------------------------------------------------------------

def test_route_source_is_resolved_via_the_router_module():
    router = FakeRouter(source="alpha_vantage")
    capture = begin_capture(INSTANT, [route_target(router)])
    try:
        router.route_to_vendor("get_stock_data", "NVDA")
    finally:
        calls = capture.finish()
    assert calls[0].data_source == "alpha_vantage"
    assert calls[0].method == "get_stock_data"


def test_route_source_falls_back_to_unknown_when_get_vendor_raises():
    router = FakeRouter(explode=True)
    capture = begin_capture(INSTANT, [route_target(router)])
    try:
        result = router.route_to_vendor("get_indicators", "NVDA")
    finally:
        calls = capture.finish()
    # The call itself is unaffected: resolution faults never change a result.
    assert result == "get_indicators:NVDA"
    assert calls[0].data_source == UNKNOWN_SOURCE


def test_route_method_is_read_from_the_keyword_when_no_positional_arg():
    router = FakeRouter()
    capture = begin_capture(INSTANT, [route_target(router)])
    try:
        router.route_to_vendor(method="get_news", ticker="NVDA")
    finally:
        calls = capture.finish()
    assert calls[0].method == "get_news"


def test_route_target_without_a_router_module_records_its_own_source():
    """A route target that names no router cannot resolve: it keeps ``source``."""
    module = fake_module(route_to_vendor=lambda method, *a: "x")
    target = PatchTarget(owner=module, attr="route_to_vendor", kind=KIND_ROUTE, source="configured")
    capture = begin_capture(INSTANT, [target])
    try:
        module.route_to_vendor("get_news")
    finally:
        calls = capture.finish()
    assert calls[0].data_source == "configured"


# ---------------------------------------------------------------------------
# T3 -- direct targets record their fixed method and source
# ---------------------------------------------------------------------------

def test_direct_target_records_its_fixed_method_and_source():
    module = fake_module(fetch_stocktwits_messages=lambda ticker: "messages")
    target = direct_target(module, "fetch_stocktwits_messages", "stocktwits", "stocktwits")
    capture = begin_capture(INSTANT, [target])
    try:
        assert module.fetch_stocktwits_messages("NVDA") == "messages"
    finally:
        calls = capture.finish()
    assert calls[0].method == "stocktwits"
    assert calls[0].data_source == "stocktwits"
    assert calls[0].result_kind == RESULT_OK


def test_direct_target_ignores_the_router_entirely():
    router = FakeRouter(explode=True)
    module = fake_module(fetch_reddit_posts=lambda ticker: "posts")
    capture = begin_capture(INSTANT, [direct_target(module), route_target(router)])
    try:
        module.fetch_reddit_posts("NVDA")
    finally:
        calls = capture.finish()
    assert len(calls) == 1
    assert calls[0].data_source == "reddit"


# ---------------------------------------------------------------------------
# T4 -- no-data sentinels
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sentinel",
    [
        "NO_DATA_AVAILABLE: No usable market data for 'ZZZZ' from any configured vendor.",
        "DATA_UNAVAILABLE: no configured vendor could serve get_news right now",
        "<Reddit unavailable: fetch failed (r/wallstreetbets); this is not an absence>",
        "<stocktwits unavailable: TimeoutError>",
    ],
    ids=["no-data-available", "data-unavailable", "reddit-placeholder", "stocktwits-placeholder"],
)
def test_no_data_result_is_marked_and_keeps_its_source(sentinel):
    module = fake_module(fetch_reddit_posts=lambda ticker: sentinel)
    capture = begin_capture(INSTANT, [direct_target(module)])
    try:
        assert module.fetch_reddit_posts("NVDA") == sentinel
    finally:
        calls = capture.finish()
    assert calls[0].result_kind == RESULT_NO_DATA
    assert calls[0].data_source == f"reddit{NO_DATA_SUFFIX}"


def test_route_no_data_keeps_the_resolved_vendor_and_marks_it():
    router = FakeRouter(source="yfinance")
    router.route_to_vendor = lambda method, *a: "NO_DATA_AVAILABLE: nothing for ZZZZ"
    capture = begin_capture(INSTANT, [route_target(router)])
    try:
        router.route_to_vendor("get_stock_data", "ZZZZ")
    finally:
        calls = capture.finish()
    assert calls[0].result_kind == RESULT_NO_DATA
    assert calls[0].data_source == f"yfinance{NO_DATA_SUFFIX}"


def test_an_ordinary_result_is_not_mistaken_for_no_data():
    module = fake_module(fetch_reddit_posts=lambda ticker: "3 posts about NVDA")
    capture = begin_capture(INSTANT, [direct_target(module)])
    try:
        module.fetch_reddit_posts("NVDA")
    finally:
        calls = capture.finish()
    assert calls[0].result_kind == RESULT_OK
    assert calls[0].data_source == "reddit"


@pytest.mark.parametrize(
    "report",
    [
        "The data feed was unavailable for part of the session; shares still rose 2%.",
        "News unavailable to retail investors dominated the tape, but volume was strong.",
        "Long report.\n- Source: yfinance\n- Note: vendor temporarily unavailable\n.",
    ],
    ids=["mentions-the-word", "mid-sentence", "word-in-a-long-report"],
)
def test_a_report_merely_mentioning_unavailable_is_not_no_data(report):
    """Correction 3: match the placeholder SHAPE, not the bare word.

    A substring test would label a real report ``(no-data)`` -- a false evidence
    label, and the worst kind, because it looks like diligence.
    """
    module = fake_module(fetch_reddit_posts=lambda ticker: report)
    capture = begin_capture(INSTANT, [direct_target(module)])
    try:
        module.fetch_reddit_posts("NVDA")
    finally:
        calls = capture.finish()
    assert calls[0].result_kind == RESULT_OK
    assert calls[0].data_source == "reddit"


def test_a_placeholder_is_recognised_after_leading_whitespace():
    module = fake_module(fetch_reddit_posts=lambda ticker: "   <Reddit unavailable: fetch failed>")
    capture = begin_capture(INSTANT, [direct_target(module)])
    try:
        module.fetch_reddit_posts("NVDA")
    finally:
        calls = capture.finish()
    assert calls[0].result_kind == RESULT_NO_DATA


# ---------------------------------------------------------------------------
# T5 -- an exception is recorded AND re-raised
# ---------------------------------------------------------------------------

def test_original_exception_is_recorded_then_reraised_unchanged():
    def boom(ticker):
        raise TimeoutError("vendor timed out")

    module = fake_module(fetch_stocktwits_messages=boom)
    capture = begin_capture(INSTANT, [direct_target(module, "fetch_stocktwits_messages",
                                                     "stocktwits", "stocktwits")])
    calls: tuple[CapturedCall, ...] = ()
    try:
        with pytest.raises(TimeoutError) as caught:
            module.fetch_stocktwits_messages("NVDA")
    finally:
        calls = capture.finish()
    assert caught.value.args == ("vendor timed out",)
    assert len(calls) == 1
    assert calls[0].result_kind == RESULT_ERROR
    assert calls[0].method == "stocktwits"


def test_the_error_digest_names_the_exception_type_not_its_message():
    """A message can carry a clock or a URL; the type is the stable identity."""

    def run(message: str) -> CapturedCall:
        def boom(ticker):
            raise ValueError(message)

        module = fake_module(fetch_reddit_posts=boom)
        capture = begin_capture(INSTANT, [direct_target(module)])
        result: list[CapturedCall] = []
        try:
            with pytest.raises(ValueError):
                module.fetch_reddit_posts("NVDA")
            result.extend(capture.finish())
        finally:
            capture.finish()  # idempotent: restores even if an assertion above fails
        return result[0]

    assert run("first message") == run("a completely different message")


def test_missing_target_is_reported_and_the_others_still_work():
    router = FakeRouter()
    module = fake_module(fetch_reddit_posts=lambda ticker: "posts")
    capture = begin_capture(INSTANT, [route_target(router, "not_a_real_attr"),
                                      direct_target(module)])
    try:
        module.fetch_reddit_posts("NVDA")
    finally:
        calls = capture.finish()
    assert len(calls) == 1
    assert calls[0].method == "reddit"
    assert any("not_a_real_attr" in error for error in capture.capture_errors)
    assert not hasattr(router, "not_a_real_attr")


def test_a_failing_observe_changes_no_result_and_is_journalled(monkeypatch):
    """Correction 2: a dropped observation must be recorded, not silent."""
    router = FakeRouter()
    capture = begin_capture(INSTANT, [route_target(router)])

    def broken_record(*args, **kwargs):
        raise RuntimeError("bookkeeping exploded")

    monkeypatch.setattr(capture, "_record", broken_record)
    try:
        result = router.route_to_vendor("get_stock_data", "NVDA")
    finally:
        calls = capture.finish()

    # The call still returned exactly what the original returned...
    assert result == "get_stock_data:NVDA"
    # ...and the lost observation is journalled rather than swallowed.
    assert calls == ()
    assert any("observe failed: RuntimeError" in error for error in capture.capture_errors)


def test_finish_is_idempotent_and_restores_only_once():
    router = FakeRouter()
    original = router.route_to_vendor
    capture = begin_capture(INSTANT, [route_target(router)])
    router.route_to_vendor("get_news", "NVDA")
    first = capture.finish()
    second = capture.finish()
    assert first == second
    assert len(first) == 1
    assert router.route_to_vendor is original


def test_calls_after_finish_are_not_captured():
    """Restoration is real: the original now runs unobserved."""
    router = FakeRouter()
    capture = begin_capture(INSTANT, [route_target(router)])
    capture.finish()
    router.route_to_vendor("get_news", "NVDA")
    assert capture.calls() == ()


# ---------------------------------------------------------------------------
# T7 -- four reports, three snapshots: the pinned link set
# ---------------------------------------------------------------------------

THREE_CALLS = make_calls(
    ("get_stock_data", "yfinance"),
    ("get_news", "alpha_vantage"),
    ("reddit", "reddit"),
)


def test_four_reports_and_three_snapshots_check_five_by_three_links():
    """REQ-TRACEABILITY: each of 4 reports + 1 decision links to all 3 snapshots."""
    payload = trace(calls=THREE_CALLS)
    assert payload["traceable"] is True
    assert payload["snapshot_count"] == 3
    assert payload["checked_links"] == (4 + 1) * 3 == 15
    assert payload["resolved_links"] == payload["checked_links"]
    assert payload["findings"] == []
    assert payload["trace_error"] is None
    assert len(payload["table"]) == 15


def test_table_row_order_is_pinned_reports_first_then_decision():
    payload = trace(calls=THREE_CALLS)
    assertion_order = []
    for row in payload["table"]:
        if not assertion_order or assertion_order[-1] != row["assertion_id"]:
            assertion_order.append(row["assertion_id"])
    names = [aid.split(":")[1] for aid in assertion_order[:-1]]
    assert names == ["market", "sentiment", "news", "fundamentals"]
    assert assertion_order[-1] == f"decision:{TICKER}:{TRADE_DATE}:Hold"


def test_every_report_links_to_every_snapshot_in_sorted_order():
    """Policy G1: the link set is the run's whole evidence set, sorted."""
    payload = trace(calls=THREE_CALLS)
    snapshot_ids = [
        row["referenced_data_snapshot_id"] for row in payload["table"]
    ]
    unique_sorted = sorted(set(snapshot_ids))
    assert len(unique_sorted) == 3
    for index in range(0, len(snapshot_ids), 3):
        assert snapshot_ids[index:index + 3] == unique_sorted
        assert [row["critical"] for row in payload["table"][index:index + 3]] == ["True"] * 3


def test_decision_is_recorded_with_the_pinned_id():
    payload = trace(calls=THREE_CALLS)
    assert payload["decision_id"] == f"decision:{TICKER}:{TRADE_DATE}:Hold"


def test_payload_is_json_serialisable_and_has_exactly_the_pinned_keys():
    payload = trace(calls=THREE_CALLS)
    assert set(payload) == PAYLOAD_KEYS
    json.dumps(payload)


def test_table_rows_carry_the_injected_instant():
    payload = trace(calls=THREE_CALLS)
    assert {row["fetch_timestamp"] for row in payload["table"]} == {INSTANT}


# ---------------------------------------------------------------------------
# T8 -- no calls: NO_EVIDENCE, never a fabricated snapshot
# ---------------------------------------------------------------------------

def test_no_calls_with_four_reports_is_not_traceable_and_lists_all_unbacked():
    payload = trace(calls=())
    assert payload["traceable"] is False
    assert payload["snapshot_count"] == 0
    assert payload["checked_links"] == 0
    assert payload["resolved_links"] == 0
    assert payload["unbacked_reports"] == list(REPORT_KEYS)
    assert payload["table"] == []
    reasons = {finding["reason"] for finding in payload["findings"]}
    assert "NO_EVIDENCE" in reasons
    assert all(finding["referenced_data_snapshot_id"] == "" for finding in payload["findings"]
               if finding["reason"] == "NO_EVIDENCE")


def test_no_calls_never_invents_a_snapshot():
    """Pinned: an empty set stays empty; no placeholder evidence is written."""
    payload = trace(calls=(), state={"market_report": "only market"})
    assert payload["snapshot_count"] == 0
    assert payload["table"] == []
    assert payload["unbacked_reports"] == ["market_report"]


def test_an_empty_report_is_neither_asserted_nor_unbacked():
    """An empty report is absent, not unbacked: it asserts nothing at all."""
    payload = trace(calls=THREE_CALLS, state=full_state(news_report="   ", market_report=""))
    assert payload["unbacked_reports"] == []
    # 2 reports left + the decision, over 3 snapshots.
    assert payload["checked_links"] == (2 + 1) * 3
    names = {row["assertion_id"].split(":")[1] for row in payload["table"]
             if row["assertion_id"].startswith("report:")}
    assert names == {"sentiment", "fundamentals"}


# ---------------------------------------------------------------------------
# T9 -- calls but no reports: the decision still links
# ---------------------------------------------------------------------------

def test_calls_with_no_reports_still_links_the_decision():
    """No reports, but real evidence: the decision is still backed and verifiable."""
    payload = trace(calls=THREE_CALLS, state={})
    assert payload["traceable"] is True
    assert payload["checked_links"] == 3
    assert {row["assertion_id"] for row in payload["table"]} == {payload["decision_id"]}
    assert payload["unbacked_reports"] == []


def test_non_string_report_is_ignored_rather_than_crashing():
    payload = trace(calls=THREE_CALLS, state={"market_report": 42, "news_report": None})
    assert payload["checked_links"] == 3
    assert payload["unbacked_reports"] == []


# ---------------------------------------------------------------------------
# T10 -- duplicate calls collapse to one snapshot
# ---------------------------------------------------------------------------

def test_identical_calls_dedupe_to_one_snapshot():
    one = make_calls(("get_stock_data", "yfinance"))[0]
    payload = trace(calls=(one, one, one))
    assert payload["snapshot_count"] == 1
    assert payload["checked_links"] == (4 + 1) * 1


def test_a_collision_between_different_results_is_an_error_not_an_overwrite(monkeypatch):
    """Two different results under one id must be reported, never overwritten.

    A real SHA-256 prefix clash cannot be produced on demand, so the detector
    is exercised by collapsing the id of two calls that DO differ in content.
    The collision branch itself -- not the hash -- is what is under test.
    """
    first = CapturedCall("get_news", "yfinance", "a" * 12, "r" * 12, RESULT_OK)
    second = CapturedCall("get_news", "finnhub", "a" * 12, "r" * 12, RESULT_OK)
    monkeypatch.setattr(trace_adapter, "_snapshot_id", lambda *a, **k: "snap-collided")
    payload = trace(calls=(first, second))
    assert payload["traceable"] is False
    assert "collision" in payload["trace_error"]
    assert payload["snapshot_count"] == 0


def test_two_different_sources_are_two_snapshots_when_ids_differ():
    """The control for the collision test: differing content is kept apart."""
    first = CapturedCall("get_news", "yfinance", "a" * 12, "r" * 12, RESULT_OK)
    second = CapturedCall("get_news", "finnhub", "a" * 12, "r" * 12, RESULT_OK)
    payload = trace(calls=(first, second))
    assert payload["trace_error"] is None
    assert payload["snapshot_count"] == 2
    assert {row["data_source"] for row in payload["table"]} == {"yfinance", "finnhub"}


# ---------------------------------------------------------------------------
# T11 -- capture order does not change the payload
# ---------------------------------------------------------------------------

def test_reversed_capture_order_is_byte_identical():
    forward = trace(calls=THREE_CALLS)
    backward = trace(calls=tuple(reversed(THREE_CALLS)))
    assert json.dumps(forward, sort_keys=True) == json.dumps(backward, sort_keys=True)
    assert forward["table"] == backward["table"]


def test_a_non_trace_error_from_the_recorder_is_reported_not_raised(monkeypatch):
    """Correction 4: the contract is "never raises", not "never raises TraceError"."""
    from src.trace_recorder import TraceRecorder

    def explode(self, **kwargs):
        raise RuntimeError("recorder misbehaved")

    monkeypatch.setattr(TraceRecorder, "record_snapshot", explode)
    payload = trace(calls=THREE_CALLS)
    assert payload["traceable"] is False
    assert "RuntimeError" in payload["trace_error"]
    assert payload["snapshot_count"] == 0
    assert payload["checked_links"] == 0
    assert payload["table"] == []
    assert payload["unbacked_reports"] == list(REPORT_KEYS)  # all four named
    assert set(payload) == PAYLOAD_KEYS
    json.dumps(payload)


# ---------------------------------------------------------------------------
# T12 -- an invalid instant is a reported trace error, not an exception
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "started_at",
    ["not-a-timestamp", "2026-11-24T00:00:00", "2026-11-24T00:00:00+08:00", ""],
    ids=["garbage", "naive", "non-utc", "empty"],
)
def test_invalid_started_at_is_reported_and_never_raised(started_at):
    payload = trace(calls=THREE_CALLS, started_at=started_at)
    assert payload["traceable"] is False
    assert payload["trace_error"]
    assert "TraceError" in payload["trace_error"]
    assert set(payload) == PAYLOAD_KEYS


def test_the_trace_verdict_never_changes_the_rating_input():
    """The trace is evidence; the guardrail is the gate."""
    payload = trace(calls=THREE_CALLS, started_at="garbage")
    assert payload["decision_id"].endswith(":Hold")
    assert payload["traceable"] is False


# ---------------------------------------------------------------------------
# T13 -- a dangling snapshot surfaces as a finding
# ---------------------------------------------------------------------------

def test_dropped_snapshot_is_detected_as_dangling(monkeypatch):
    """INV-TRACE-COMPLETENESS: a link to unrecorded evidence must fail the audit."""
    from src.trace_recorder import TraceRecorder

    real = TraceRecorder.record_snapshot
    seen: list[str] = []

    def flaky(self, *, snapshot_id, data_source, fetch_timestamp):
        seen.append(snapshot_id)
        if len(seen) == 2:  # silently lose the second snapshot
            return None
        return real(self, snapshot_id=snapshot_id, data_source=data_source,
                    fetch_timestamp=fetch_timestamp)

    monkeypatch.setattr(TraceRecorder, "record_snapshot", flaky)
    payload = trace(calls=THREE_CALLS)
    assert payload["traceable"] is False
    assert payload["trace_error"] is None
    reasons = {finding["reason"] for finding in payload["findings"]}
    assert "DANGLING_SNAPSHOT" in reasons
    assert payload["resolved_links"] < payload["checked_links"]


# ---------------------------------------------------------------------------
# T15 -- a non-dict state behaves as empty
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("state", [None, [], "text", 7, ()], ids=[
    "none", "list", "string", "int", "tuple",
])
def test_non_dict_final_state_behaves_as_empty_and_never_raises(state):
    payload = build_trace(
        calls=THREE_CALLS, started_at=INSTANT, final_state=state,
        ticker=TICKER, trade_date=TRADE_DATE, rating="Hold",
    )
    assert payload["unbacked_reports"] == []
    assert payload["checked_links"] == 3  # the decision only
    assert payload["traceable"] is True
    assert set(payload) == PAYLOAD_KEYS


def test_capture_errors_are_carried_into_the_payload_in_order():
    payload = trace(calls=THREE_CALLS, capture_errors=("missing target: a", "missing target: b"))
    assert payload["capture_errors"] == ["missing target: a", "missing target: b"]


# ---------------------------------------------------------------------------
# T14 -- purity (AST): allowed imports only; no clock, no random, no network
# ---------------------------------------------------------------------------

ALLOWED_TOP_LEVEL_IMPORTS = {
    "hashlib", "json", "threading", "functools", "dataclasses", "typing", "__future__", "src",
}

FORBIDDEN_IMPORTS = {
    "os", "sys", "time", "datetime", "random", "uuid", "secrets", "socket",
    "requests", "httpx", "urllib", "http", "ssl", "yfinance", "subprocess",
}

FORBIDDEN_CALLS = {
    "datetime.now", "datetime.today", "datetime.utcnow",
    "time.time", "time.monotonic", "uuid.uuid4", "uuid.uuid1",
    "uuid4", "uuid1", "random.random",
    "open", "urlopen", "requests.get", "socket.socket",
}


def _module_tree() -> ast.Module:
    return ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def _top_level_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:  # module scope only
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _all_imports(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _called_attributes(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            parts, base = [func.attr], func.value
            while isinstance(base, ast.Attribute):
                parts.append(base.attr)
                base = base.value
            if isinstance(base, ast.Name):
                parts.append(base.id)
            found.add(".".join(reversed(parts)))
    return found


def test_module_scope_imports_are_on_the_allowed_list():
    imported = _top_level_imports(_module_tree())
    assert imported & FORBIDDEN_IMPORTS == set(), imported & FORBIDDEN_IMPORTS
    assert imported - ALLOWED_TOP_LEVEL_IMPORTS == set(), imported - ALLOWED_TOP_LEVEL_IMPORTS


def test_tradingagents_is_imported_only_inside_default_targets():
    """The baseline import must be lazy: the capture must test without it."""
    tree = _module_tree()
    assert "tradingagents" in _all_imports(tree)

    owners: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names: set[str] = set()
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import):
                    names |= {alias.name.split(".")[0] for alias in inner.names}
                elif isinstance(inner, ast.ImportFrom) and inner.level == 0 and inner.module:
                    names.add(inner.module.split(".")[0])
            if "tradingagents" in names:
                owners.append(node.name)
    assert owners == ["default_targets"]


def test_module_has_no_clock_random_or_network_calls():
    assert _called_attributes(_module_tree()) & FORBIDDEN_CALLS == set()


def test_the_capture_module_is_importable_without_the_framework(monkeypatch):
    """The lazy import is real: the module must load with the baseline blocked.

    A session-wide ``sys.modules`` check would only measure test order, since
    other offline tests legitimately import the baseline.
    """
    import importlib
    import importlib.abc
    import sys

    class Refuse(importlib.abc.MetaPathFinder):
        """Refuse every ``tradingagents.*`` import for the duration."""

        def find_spec(self, fullname, path=None, target=None):
            if fullname == "tradingagents" or fullname.startswith("tradingagents."):
                raise ImportError(f"the baseline must not be imported: {fullname}")

    monkeypatch.delitem(sys.modules, "tradingagents", raising=False)
    for name in [n for n in sys.modules if n.split(".")[0] == "tradingagents"]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [Refuse(), *sys.meta_path])
    monkeypatch.delitem(sys.modules, "src.integration.trace_adapter", raising=False)
    try:
        module = importlib.import_module("src.integration.trace_adapter")
        assert module.begin_capture is not None
        assert module.build_trace is not None
    finally:
        monkeypatch.undo()
        sys.modules.pop("src.integration.trace_adapter", None)
        importlib.import_module("src.integration.trace_adapter")


def test_default_targets_names_the_five_pinned_targets():
    """The five targets, as pinned by ADR-006 -- skipped when the baseline is absent."""
    pytest.importorskip("tradingagents")
    targets = trace_adapter.default_targets()
    described = [(target.attr, target.kind, target.method, target.source) for target in targets]
    assert described == [
        ("route_to_vendor", KIND_ROUTE, "", ""),
        ("route_to_vendor", KIND_ROUTE, "", ""),
        ("build_verified_market_snapshot", KIND_DIRECT, "get_verified_market_snapshot",
         "verified_market_snapshot"),
        ("fetch_stocktwits_messages", KIND_DIRECT, "stocktwits", "stocktwits"),
        ("fetch_reddit_posts", KIND_DIRECT, "reddit", "reddit"),
    ]
    # The two route targets are distinct module attributes, not one patched twice.
    assert targets[0].owner is not targets[1].owner
    assert targets[0].attr == targets[1].attr == "route_to_vendor"
