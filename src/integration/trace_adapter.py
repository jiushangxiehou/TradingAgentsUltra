"""Trace adapter: capture a run's data accesses and attest them (ADR-006).

ADR-003 / ADR-006 / REQ-TRACEABILITY / INV-TRACE-COMPLETENESS

Two steps, kept apart so each is testable on its own:

``DataCapture``   patches the data-access functions of a live run and records
                  every call it observes. It never inspects the recorder and
                  never decides what the evidence means; it records.
``build_trace``   turns the observed calls plus the finished state into a
                  ``TraceRecorder`` chain and an audit verdict. Pure: it reads
                  no clock, opens no file, touches no global.

Trace boundary -- G1, a run-level evidence set (ADR-006)
--------------------------------------------------------
This is deliberately COARSE. Every critical assertion for a run links to the
run's whole deduplicated evidence set, in sorted snapshot-id order. There is no
per-analyst and no per-method attribution claim, because the analysts run in
parallel: a call observed while three analysts are mid-flight cannot be pinned
to one of them reliably, and a false attribution is worse than a coarse one --
it would let a reader verify a citation against the wrong source and conclude
the chain is sound. Closing this needs the analysts to declare their own
evidence, which is ADR-003's deferred interface change and a reopen condition
of ADR-006.

What the assertions mean: ``report:{name}:{digest}`` says "this report exists
and the run's evidence must resolve"; ``decision:...`` says the same for the
decision. Neither claims that every sentence in a report rests on the snapshots
linked to it -- nothing in the framework can testify to that.

Unbacked reports
----------------
A report is *unbacked* when the run observed no snapshot at all. It is then
named in ``unbacked_reports`` and given no assertion, because an assertion with
nothing to link to could only be recorded as dangling, and a dangling link is a
failure the audit reports -- not evidence. The trade is deliberate: an unbacked
run returns ``NO_EVIDENCE`` (``traceable=False``), which is the honest verdict,
rather than a fabricated link that would make the run *look* audited.

Snapshot identity
-----------------
``snap-{trade_date}-{method}-{digest12}`` where ``digest12`` hashes the call's
arguments, its result and its source. Two identical calls therefore collapse to
one snapshot (evidence identity, not call identity), and a genuine collision --
two different results under one id -- is a ``TraceError`` that ``build_trace``
reports rather than overwrites.

Timestamps
----------
``fetch_timestamp`` is one injected UTC instant per run, taken by the caller in
the integration layer. The as-of date lives in the id. The injected instant is
what makes a run's table byte-identical on replay, and what keeps the recorder
free of a clock.

Import boundary
---------------
This module imports only the standard library and ``src.trace_recorder``. The
baseline is imported lazily inside ``default_targets()`` alone, so the capture
machinery is testable against fake targets without the framework installed.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from typing import Final, Self

from src.trace_recorder import TraceRecorder

# Route targets: the wrapper reads the method from the call's first argument.
KIND_ROUTE: Final[str] = "route"
# Direct targets: a function outside the router, with a fixed method and source.
KIND_DIRECT: Final[str] = "direct"

RESULT_OK: Final[str] = "ok"
RESULT_NO_DATA: Final[str] = "no-data"
RESULT_ERROR: Final[str] = "error"

UNKNOWN_SOURCE: Final[str] = "unknown"
NO_DATA_SUFFIX: Final[str] = " (no-data)"

# The router's sentinels (tradingagents/dataflows/router.py) and the fetchers'
# placeholder, which say "the vendor told us nothing" rather than "we did not
# look". Recorded as evidence of absence, so the source is kept and marked.
#
# These are matched as SHAPES, anchored at the start of the result (after
# optional whitespace) and case-insensitively. Two reasons, both learned from
# the real code:
#
#   * the fetchers embed the marker in a sentence -- reddit.py returns
#     ``<Reddit unavailable: fetch failed (...)>``, stocktwits.py returns
#     ``<stocktwits unavailable: TimeoutError>`` -- so trailing text must be
#     allowed;
#   * a bare ``"unavailable" in result`` substring test would relabel any long
#     report that merely *mentions* the word as absent data, which is a false
#     evidence label. The placeholder always begins the result.
_NO_DATA_PLACEHOLDERS: Final[tuple[str, ...]] = (
    "no_data_available:",
    "data_unavailable:",
    "<stocktwits unavailable",
    "<reddit unavailable",
    "<unavailable",
)

# The reports a run can carry, in the order their assertions are inserted.
REPORT_KEYS: Final[tuple[str, ...]] = (
    "market_report",
    "sentiment_report",
    "news_report",
    "fundamentals_report",
)

_DIGEST_CHARS: Final[int] = 12


@dataclass(frozen=True)
class PatchTarget:
    """One observed data-access function and how to read a call to it."""

    owner: object
    attr: str
    kind: str
    method: str = ""
    source: str = ""
    router_module: object | None = None


@dataclass(frozen=True)
class CapturedCall:
    """One observed data access, reduced to what a snapshot needs."""

    method: str
    data_source: str
    args_digest: str
    result_digest: str
    result_kind: str


# ---------------------------------------------------------------------------
# The baseline's data-access surface (five targets, lazily imported)
# ---------------------------------------------------------------------------

def default_targets() -> tuple[PatchTarget, ...]:
    """The five places a run reads outside evidence, in the pinned order.

    Two route targets (the router itself and the name the tools bound to it),
    and three direct paths that bypass the router entirely. Imported here, and
    here only: this is the module's single import of the baseline.
    """
    from tradingagents.agents import tools
    from tradingagents.agents.analysts import sentiment_analyst
    from tradingagents.dataflows import router

    return (
        PatchTarget(owner=router, attr="route_to_vendor", kind=KIND_ROUTE, router_module=router),
        PatchTarget(owner=tools, attr="route_to_vendor", kind=KIND_ROUTE, router_module=router),
        PatchTarget(
            owner=tools,
            attr="build_verified_market_snapshot",
            kind=KIND_DIRECT,
            method="get_verified_market_snapshot",
            source="verified_market_snapshot",
        ),
        PatchTarget(
            owner=sentiment_analyst,
            attr="fetch_stocktwits_messages",
            kind=KIND_DIRECT,
            method="stocktwits",
            source="stocktwits",
        ),
        PatchTarget(
            owner=sentiment_analyst,
            attr="fetch_reddit_posts",
            kind=KIND_DIRECT,
            method="reddit",
            source="reddit",
        ),
    )


# ---------------------------------------------------------------------------
# Canonical digests
# ---------------------------------------------------------------------------

def _digest_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:_DIGEST_CHARS]


def _canonical(value: object) -> object:
    """A key-sorted, JSON-safe projection of an argument or a result.

    Strings pass through verbatim (a report or a price table is its own
    identity). Containers are projected recursively, recursively sorted by a
    canonical key, so an equal result always hashes equally. Anything else --
    including floats -- is described by type and ``repr``. ``repr`` is sound
    here because tool arguments and vendor results are primitives, strings and
    containers of them; a live object with a volatile ``repr`` shows up as a
    differing snapshot, which is the direction that is safe to be wrong in.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return {"__float__": value.hex()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        rendered = [_canonical(item) for item in value]
        return sorted(rendered, key=_canonical_key)
    return {"__type__": type(value).__name__, "__repr__": repr(value)}


def _canonical_key(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest_payload(*parts: object) -> str:
    """One content digest over an ordered sequence of canonical parts."""
    payload = json.dumps(
        [_canonical(part) for part in parts],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return _digest_text(payload)


def _classify_result(result: object) -> str:
    """``no-data`` for a vendor sentinel or a fetcher placeholder, else ``ok``."""
    if not isinstance(result, str):
        return RESULT_OK
    head = result.lstrip().lower()
    if head.startswith(_NO_DATA_PLACEHOLDERS):
        return RESULT_NO_DATA
    return RESULT_OK


def _snapshot_id(trade_date: str, method: str, args_digest: str, result_digest: str,
                 data_source: str) -> str:
    digest = _digest_payload(args_digest, result_digest, data_source)
    return f"snap-{trade_date}-{method}-{digest}"


# ---------------------------------------------------------------------------
# Capture: patch, observe, restore
# ---------------------------------------------------------------------------

_MISSING = object()


class DataCapture:
    """Patch a set of data-access functions and record the calls they serve.

    Thread-safe: analysts run in parallel, so raw calls are appended under a
    lock and nothing but that append touches shared state from a worker thread.
    The recorder is not touched at all -- attestation happens later, on the run
    thread, in ``build_trace``.

    The wrapper always calls the original exactly once and returns its result
    (or re-raises its exception) unchanged. Its own bookkeeping is wrapped in a
    try/except so a capture fault can never change what the programme does.
    """

    def __init__(self, started_at: str, targets: tuple[PatchTarget, ...]) -> None:
        self.started_at = started_at
        self._targets = targets
        self._lock = threading.Lock()
        self._calls: list[CapturedCall] = []
        self._errors: list[str] = []
        self._restorers: list[tuple[object, str, object]] = []
        self._entered = False
        self._finished = False
        self._calls_result: tuple[CapturedCall, ...] = ()

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> Self:
        # Idempotent on purpose. ``begin_capture`` installs immediately (so a
        # caller that cannot use ``with`` still gets bookkeeping), and
        # ``with begin_capture(...)`` then enters the SAME object. Installing
        # again would wrap the wrapper, and the single ``finish()`` would leave
        # one layer behind, still patching the module.
        if self._entered:
            return self
        self._install()
        self._entered = True
        return self

    def __exit__(self, *exc: object) -> None:
        self.finish()

    def _install(self) -> None:
        for target in self._targets:
            current = getattr(target.owner, target.attr, _MISSING)
            if current is _MISSING:
                # A renamed or dropped upstream symbol: report it, keep going.
                self._note_error(f"missing target: {target.attr}")
                continue
            try:
                wrapper = (
                    self._route_wrapper(target, current)
                    if target.kind == KIND_ROUTE
                    else self._direct_wrapper(target, current)
                )
                setattr(target.owner, target.attr, wrapper)
            except Exception as exc:  # noqa: BLE001 - a fault must not stop the run
                self._note_error(f"cannot patch {target.attr}: {type(exc).__name__}")
                continue
            self._restorers.append((target.owner, target.attr, current))

    def finish(self) -> tuple[CapturedCall, ...]:
        """Restore every patched attribute and return the observed calls.

        Idempotent: a second call restores nothing again and returns the same
        tuple, so a caller may ``finish()`` inside a ``finally`` and *also* let
        ``__exit__`` run.
        """
        with self._lock:
            if self._finished:
                return self._calls_result
            self._finished = True
            self._calls_result = tuple(self._calls)

        while self._restorers:
            owner, attr, original = self._restorers.pop()
            try:
                setattr(owner, attr, original)
            except Exception as exc:  # noqa: BLE001 - nothing may break the run
                self._note_error(f"cannot restore {attr}: {type(exc).__name__}")
        return self._calls_result

    # -- introspection -----------------------------------------------------

    def calls(self) -> tuple[CapturedCall, ...]:
        with self._lock:
            return tuple(self._calls)

    @property
    def capture_errors(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._errors)

    # -- wrappers ----------------------------------------------------------

    def _observe(self, target: PatchTarget, method: object, args: tuple, kwargs: dict,
                 result: object, result_kind: str) -> None:
        """Record one call, reporting -- never raising -- a bookkeeping fault.

        A trace that breaks the run it observes is worse than a missing trace:
        the decision is the point, the evidence is about it. A fault here is
        therefore recorded in ``capture_errors`` and not raised. That journal
        entry is the only proof the gap exists, so it must be written: the
        recorder cannot report a call it was never told about.
        """
        try:
            self._record(target, method, args, kwargs, result, result_kind)
        except Exception as exc:  # noqa: BLE001 - see the docstring: never break a call
            self._note_error(f"observe failed: {type(exc).__name__}: {target.attr}")

    def _note_error(self, message: str) -> None:
        with self._lock:
            self._errors.append(message)

    def _route_wrapper(self, target: PatchTarget, original: object):
        def route(*args, **kwargs):
            method = args[0] if args else kwargs.get("method", "")
            try:
                result = original(*args, **kwargs)
            except BaseException as exc:  # record, then re-raise
                self._observe(target, method, args, kwargs, exc, RESULT_ERROR)
                raise
            self._observe(target, method, args, kwargs, result, _classify_result(result))
            return result

        return route

    def _direct_wrapper(self, target: PatchTarget, original: object):
        def direct(*args, **kwargs):
            try:
                result = original(*args, **kwargs)
            except BaseException as exc:  # record, then re-raise
                self._observe(target, target.method, args, kwargs, exc, RESULT_ERROR)
                raise
            self._observe(target, target.method, args, kwargs, result, _classify_result(result))
            return result

        return direct

    # -- recording ---------------------------------------------------------

    def _resolve_source(self, target: PatchTarget, method: object) -> str:
        """The vendor the router would have used, resolved INSIDE the call."""
        if target.kind != KIND_ROUTE or target.router_module is None:
            return target.source
        module = target.router_module
        try:
            category = module.get_category_for_method(method)
            return module.get_vendor(category, method)
        except Exception:  # noqa: BLE001 - an unresolvable vendor is still a call
            return UNKNOWN_SOURCE

    def _record(self, target: PatchTarget, method: object, args: tuple, kwargs: dict,
                result: object, result_kind: str) -> None:
        source = self._resolve_source(target, method)
        if result_kind == RESULT_NO_DATA:
            source = f"{source}{NO_DATA_SUFFIX}"
        if result_kind == RESULT_ERROR:
            result_digest = _digest_payload({"error": type(result).__name__})
        else:
            result_digest = _digest_payload(result)
        call = CapturedCall(
            method=str(method),
            data_source=source,
            args_digest=_digest_payload(args, kwargs),
            result_digest=result_digest,
            result_kind=result_kind,
        )
        with self._lock:
            self._calls.append(call)


def begin_capture(
    started_at: str, targets: tuple[PatchTarget, ...] | list[PatchTarget] | None = None
) -> DataCapture:
    """A capture over ``targets`` (default: the baseline's five), ALREADY entered.

    The patched functions are installed before this returns -- not on ``with`` --
    so a caller that cannot use a ``with`` block still gets bookkeeping. That is
    why ``__enter__`` is idempotent: ``with begin_capture(...)`` enters this
    same, already-installed object rather than installing a second wrapper.
    ``finish()`` (or ``__exit__``) restores everything, once.
    """
    chosen = default_targets() if targets is None else tuple(targets)
    capture = DataCapture(started_at, chosen)
    capture._install()
    capture._entered = True
    return capture


# ---------------------------------------------------------------------------
# Attestation: calls + state -> recorder chain + verdict
# ---------------------------------------------------------------------------

def _snapshot_ids(
    calls: tuple[CapturedCall, ...], trade_date: str
) -> tuple[list[tuple[str, str]], str | None]:
    """Distinct ``(snapshot_id, data_source)`` pairs, sorted by id.

    Returns ``(pairs, error)``. A collision -- two different results or sources
    under one id -- is an error rather than a silent overwrite.
    """
    by_id: dict[str, CapturedCall] = {}
    for call in calls:
        snapshot_id = _snapshot_id(
            trade_date, call.method, call.args_digest, call.result_digest, call.data_source
        )
        seen = by_id.get(snapshot_id)
        if seen is not None:
            if (seen.result_digest, seen.data_source) != (call.result_digest, call.data_source):
                return [], f"snapshot id collision: {snapshot_id} names two different results"
            continue
        by_id[snapshot_id] = call
    return sorted((sid, by_id[sid].data_source) for sid in by_id), None


def _report_assertions(state: dict) -> tuple[list[tuple[str, str]], list[str]]:
    """``(assertion_id, report_name)`` for every non-empty report, in fixed order.

    The second element is every non-empty report, because whether it is
    *backed* is decided later: a report is unbacked when the run recorded no
    snapshot at all. A report backed by the run's evidence set gets an
    assertion; an unbacked one is listed and never given an id, so nothing in
    the table can cite evidence that does not exist.
    """
    found: list[tuple[str, str]] = []
    present: list[str] = []
    for key in REPORT_KEYS:
        report = state.get(key)
        if isinstance(report, str) and report.strip():
            name = key.removesuffix("_report")
            found.append((f"report:{name}:{_digest_text(report)}", name))
            present.append(key)
    return found, present


def build_trace(
    *,
    calls: tuple[CapturedCall, ...] | list[CapturedCall],
    started_at: str,
    final_state: dict,
    ticker: str,
    trade_date: str,
    rating: str,
    capture_errors: tuple[str, ...] | list[str] = (),
) -> dict[str, object]:
    """Record the run's evidence chain and return its audit verdict.

    Never raises: a ``TraceError`` (a bad timestamp, a collision, a duplicate
    link) -- or any other exception from the recorder -- comes back as
    ``traceable=False`` with ``trace_error`` set, so the caller records it
    instead of losing the run. Nothing is persisted on that path, so
    ``snapshot_count`` is 0 and every non-empty report is listed unbacked.

    Insertion order is fixed -- the reports in :data:`REPORT_KEYS` order, then
    the decision -- so ``render_table()`` is byte-identical for equal calls
    whatever order capture observed them in.
    """
    state: dict = final_state if isinstance(final_state, dict) else {}
    captured = tuple(calls)
    payload: dict[str, object] = {
        "traceable": False,
        "checked_links": 0,
        "resolved_links": 0,
        "findings": [],
        "decision_id": f"decision:{ticker}:{trade_date}:{rating}",
        "snapshot_count": 0,
        "table": [],
        "unbacked_reports": [],
        "capture_errors": list(capture_errors),
        "trace_error": None,
    }

    pairs, collision = _snapshot_ids(captured, trade_date)
    assertions, present_reports = _report_assertions(state)
    if collision is not None:
        payload["trace_error"] = collision
        payload["unbacked_reports"] = present_reports
        return payload
    ids = tuple(snapshot_id for snapshot_id, _ in pairs)
    payload["snapshot_count"] = len(ids)
    if not ids:
        # Fail closed and explicitly: with no evidence in the run, no report can
        # be backed. Each is named in ``unbacked_reports`` and given NO
        # assertion, so the table cannot cite a snapshot that was never seen.
        payload["unbacked_reports"] = present_reports
        assertions = []

    recorder = TraceRecorder()
    try:
        for snapshot_id, data_source in pairs:
            recorder.record_snapshot(
                snapshot_id=snapshot_id,
                data_source=data_source,
                fetch_timestamp=started_at,
            )
        for assertion_id, _name in assertions:
            for snapshot_id in ids:
                recorder.record_assertion(
                    assertion_id=assertion_id,
                    referenced_data_snapshot_id=snapshot_id,
                    critical=True,
                )
        decision_id = str(payload["decision_id"])
        for snapshot_id in ids:
            recorder.record_assertion(
                assertion_id=decision_id,
                referenced_data_snapshot_id=snapshot_id,
                critical=True,
            )
        recorder.record_final_decision(decision_id=decision_id, referenced_snapshot_ids=ids)
    except Exception as exc:  # noqa: BLE001 - the contract is "never raises"
        # Any fault -- a TraceError, or a recorder that misbehaves -- leaves the
        # chain unusable. Nothing is persisted on a partial write, so the count
        # says what a reader should trust: zero.
        payload.update(
            {
                "traceable": False,
                "checked_links": 0,
                "resolved_links": 0,
                "findings": [],
                "snapshot_count": 0,
                "table": [],
                "unbacked_reports": present_reports,
                "trace_error": f"{type(exc).__name__}: {exc}",
            }
        )
        return payload

    report = recorder.audit()
    payload.update(
        {
            "traceable": report.traceable,
            "checked_links": report.checked_links,
            "resolved_links": report.resolved_links,
            "findings": [finding.to_dict() for finding in report.findings],
            "table": recorder.render_table(),
        }
    )
    return payload
