"""OFFLINE deterministic trace-recorder tests (REQ-TRACEABILITY, ADR-003).

Requires no API, no network, no clock.

Invariant under test
--------------------
INV-TRACE-COMPLETENESS : every critical assertion is linked to a recorded
                         evidence snapshot (invariants.md:10)

Acceptance conditions T1-T9 are the requirements-session conditions
(transcripts/60760270-CUIHaoyu-01-requirements-classification.md:1350-1358);
the T-NEW conditions are the build-session pinned decisions
(transcripts/60760270-CUIHaoyu-02-architecture-evaluation.md:1075-1085).

AUDIT BOUNDARY (pinned by the reviewer, build session)
------------------------------------------------------
``audit()`` audits **recorded assertions only**. It measures whether each
assertion that was *given* to ``record_assertion`` is resolvable. It can never
detect a critical assertion that was never passed to the recorder at all --
nothing in the recorder's memory can testify to a call that did not happen.
T3/T9 therefore compute ``N`` from the fixture's *expected* critical flags and
compare it with ``audit().resolved_links``; they never derive ``N`` from the
recorder's own contents. Closing the never-called gap needs an interface change
(the producing agents must declare their critical assertions up-front) and is
deferred to the next ADR, not this build.
"""

from __future__ import annotations

import ast
import dataclasses
import pathlib

import pytest

from src import trace_recorder
from src.trace_recorder import (
    AuditFinding,
    AuditReport,
    DataSnapshot,
    TraceError,
    TraceLink,
    TraceRecorder,
)

pytestmark = pytest.mark.offline

MODULE_PATH = pathlib.Path(trace_recorder.__file__)

# ---------------------------------------------------------------------------
# Synthetic, deterministic fixtures. Timestamps are ALWAYS supplied by the
# test, never read from the clock, so T7/T8 cannot flake (pinned determinism).
# ---------------------------------------------------------------------------

FIXTURE_SNAPSHOTS = (
    ("snap-market-1", "yfinance", "2026-11-24T13:30:00+00:00"),
    ("snap-news-1", "sec-edgar", "2026-11-24T13:31:05.250000+00:00"),
    ("snap-fred-1", "fred", "2026-11-24T13:32:00Z"),
)

# (assertion_id, referenced_data_snapshot_id, expected critical flag)
FIXTURE_ASSERTIONS = (
    ("assert-revenue-growth", "snap-market-1", True),
    ("assert-guidance-cut", "snap-news-1", True),
    ("assert-rates-path", "snap-fred-1", True),
    ("assert-tone-shift", "snap-news-1", False),
)

FINAL_DECISION_ID = "decision-2026-11-24-aapl"
FINAL_DECISION_REFS = ("snap-market-1", "snap-news-1", "snap-fred-1")


# ---------------------------------------------------------------------------
# Read-only inspection helpers
#
# The recorder exposes `render_table()`; these two helpers project it back to
# the record objects. They deliberately add NO accessor to the frozen
# interface -- inspection goes through the one public view the ADR specifies.
# ---------------------------------------------------------------------------

def _links(recorder: TraceRecorder) -> tuple[TraceLink, ...]:
    """One TraceLink per recorded link, in insertion order."""
    return tuple(
        TraceLink(
            link_id=row["link_id"],
            assertion_id=row["assertion_id"],
            referenced_data_snapshot_id=row["referenced_data_snapshot_id"],
            critical=row["critical"] == "True",
        )
        for row in recorder.render_table()
    )


def _snapshots(recorder: TraceRecorder) -> tuple[DataSnapshot, ...]:
    """Distinct (snapshot_id, data_source, fetch_timestamp) triples witnessed."""
    seen: dict[str, DataSnapshot] = {}
    for row in recorder.render_table():
        seen.setdefault(
            row["referenced_data_snapshot_id"],
            DataSnapshot(
                snapshot_id=row["referenced_data_snapshot_id"],
                data_source=row["data_source"],
                fetch_timestamp=row["fetch_timestamp"],
            ),
        )
    return tuple(seen.values())


def expected_critical_count(assertions=FIXTURE_ASSERTIONS) -> int:
    """N -- counted from the fixture's flags, NOT from recorder state."""
    return sum(1 for _, _, critical in assertions if critical)


def build_recorder(
    snapshots=FIXTURE_SNAPSHOTS,
    assertions=FIXTURE_ASSERTIONS,
    final_refs=FINAL_DECISION_REFS,
    record_final: bool = True,
) -> TraceRecorder:
    """A fully-populated recorder; every field is caller-supplied."""
    recorder = TraceRecorder()
    for snapshot_id, data_source, fetch_timestamp in snapshots:
        recorder.record_snapshot(
            snapshot_id=snapshot_id,
            data_source=data_source,
            fetch_timestamp=fetch_timestamp,
        )
    for assertion_id, snapshot_id, critical in assertions:
        recorder.record_assertion(
            assertion_id=assertion_id,
            referenced_data_snapshot_id=snapshot_id,
            critical=critical,
        )
    if record_final:
        recorder.record_final_decision(
            decision_id=FINAL_DECISION_ID,
            referenced_snapshot_ids=final_refs,
        )
    return recorder


def completeness_gap(recorder: TraceRecorder, assertions=FIXTURE_ASSERTIONS) -> int:
    """The single measured-completeness expression shared by T3 and T9.

    gap == 0 <=> every critical assertion in the fixture resolves to a
    recorded snapshot. Because both the positive gate (T3) and the negative
    gate (T9) call THIS function, T9 proves that T3 is not a tautology.
    """
    report = recorder.audit()
    return expected_critical_count(assertions) - report.resolved_links


def _ast_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _ast_called_attributes(path: pathlib.Path) -> set[str]:
    """Dotted attribute names used in any call, e.g. {'datetime.now'}."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            parts = [func.attr]
            base = func.value
            while isinstance(base, ast.Attribute):
                parts.append(base.attr)
                base = base.value
            if isinstance(base, ast.Name):
                parts.append(base.id)
            found.add(".".join(reversed(parts)))
    return found


# ---------------------------------------------------------------------------
# T0 -- offline marker (pinned R1: the offline gate must not be vacuous)
# ---------------------------------------------------------------------------

def test_file_is_marked_offline():
    """REQ-TRACEABILITY / pinned R1: every test in this file is offline-marked."""
    assert trace_recorder.TraceRecorder  # module importable
    # `pytestmark` is applied at module level above; a regression to a
    # per-test-only or absent marker would deselect this suite in CI.
    assert pytestmark == pytest.mark.offline


# ---------------------------------------------------------------------------
# T1 -- field completeness of every recorded critical link
# ---------------------------------------------------------------------------

def test_critical_link_fields_present_and_typed():
    """T1: zero missing fields across the fixture set."""
    recorder = build_recorder(record_final=False)
    links = _links(recorder)

    assert links, "the fixture must produce links (guards a vacuous T1)"
    assert len(links) == len(FIXTURE_ASSERTIONS)

    missing = 0
    for link in links:
        for field in (
            "link_id",
            "assertion_id",
            "referenced_data_snapshot_id",
            "critical",
        ):
            value = getattr(link, field)
            if field == "critical":
                if not isinstance(value, bool):
                    missing += 1
            elif not (isinstance(value, str) and value.strip()):
                missing += 1
    assert missing == 0

    # The snapshot half of the chain supplies data_source + fetch_timestamp.
    for snapshot in _snapshots(recorder):
        assert isinstance(snapshot, DataSnapshot)
        assert isinstance(snapshot.data_source, str) and snapshot.data_source.strip()
        assert isinstance(snapshot.fetch_timestamp, str) and snapshot.fetch_timestamp.strip()


def test_critical_flag_is_explicit_and_preserved():
    """T1 / pinned A4: critical is the producing agent's explicit flag."""
    recorder = build_recorder(record_final=False)
    by_assertion = {link.assertion_id: link for link in _links(recorder)}
    for assertion_id, _, critical in FIXTURE_ASSERTIONS:
        assert by_assertion[assertion_id].critical is critical


# ---------------------------------------------------------------------------
# T2 -- a dangling snapshot reference is a failure, never silently dropped
# ---------------------------------------------------------------------------

def test_dangling_snapshot_reference_fails_audit():
    """T2: a dangling referenced_data_snapshot_id is a failure, not a warning."""
    recorder = TraceRecorder()
    recorder.record_snapshot(
        snapshot_id="snap-market-1",
        data_source="yfinance",
        fetch_timestamp="2026-11-24T13:30:00+00:00",
    )
    link = recorder.record_assertion(
        assertion_id="assert-guidance-cut",
        referenced_data_snapshot_id="snap-does-not-exist",
        critical=True,
    )
    recorder.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )

    report = recorder.audit()

    assert report.traceable is False
    assert link in _links(recorder), "the dangling link must be stored, not dropped"
    reasons = {finding.reason for finding in report.findings}
    assert "DANGLING_SNAPSHOT" in reasons
    dangling = [f for f in report.findings if f.reason == "DANGLING_SNAPSHOT"]
    assert all(isinstance(f, AuditFinding) for f in dangling)
    assert dangling[0].assertion_id == "assert-guidance-cut"
    assert dangling[0].referenced_data_snapshot_id == "snap-does-not-exist"
    assert report.resolved_links == 1
    assert report.checked_links == 2


# ---------------------------------------------------------------------------
# T3 -- measured completeness: N from the fixture, M from the recorder
# ---------------------------------------------------------------------------

def test_measured_completeness_m_equals_n():
    """T3 / INV-TRACE-COMPLETENESS: M == N, both non-zero."""
    recorder = build_recorder()
    report = recorder.audit()

    n = expected_critical_count()  # from the fixture's flags only
    m = report.resolved_links

    assert n > 0, "N must be non-zero or the completeness gate is vacuous"
    assert m == n
    assert completeness_gap(recorder) == 0
    assert report.traceable is True


def test_completeness_gap_detects_a_missing_critical_link():
    """T3 boundary: the gap expression is sensitive to one dropped critical link."""
    recorder = TraceRecorder()
    recorder.record_snapshot(
        snapshot_id="snap-market-1",
        data_source="yfinance",
        fetch_timestamp="2026-11-24T13:30:00+00:00",
    )
    recorder.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )

    assertions = (
        ("assert-revenue-growth", "snap-market-1", True),
        ("assert-guidance-cut", "snap-market-1", True),
    )
    assert expected_critical_count(assertions) == 2
    assert completeness_gap(recorder, assertions) == 1


# ---------------------------------------------------------------------------
# T4 -- the auditor walks the final decision and resolves every link
# ---------------------------------------------------------------------------

def test_final_decision_is_traceable():
    """T4: every visited link resolves; findings empty iff traceable."""
    report = build_recorder().audit()

    assert isinstance(report, AuditReport)
    assert report.traceable is True
    assert report.findings == ()
    assert report.to_dict()["traceable"] is True


def test_final_decision_with_zero_references_fails_floor():
    """T4 floor: the final decision must reference at least one snapshot."""
    recorder = build_recorder(final_refs=())
    report = recorder.audit()

    assert report.traceable is False
    reasons = {finding.reason for finding in report.findings}
    assert reasons & {"NO_EVIDENCE", "UNKNOWN_FINAL_REFERENCE"}


def test_missing_final_decision_fails():
    """T4: a run with no recorded final decision is not traceable."""
    report = build_recorder(record_final=False).audit()

    assert report.traceable is False
    assert "NO_FINAL_DECISION" in {finding.reason for finding in report.findings}


def test_final_decision_citing_unknown_snapshot_fails():
    """T4: a final reference that never resolved to a snapshot is a gap."""
    recorder = build_recorder(final_refs=("snap-market-1", "snap-never-recorded"))
    report = recorder.audit()

    assert report.traceable is False
    assert "UNKNOWN_FINAL_REFERENCE" in {f.reason for f in report.findings}


# ---------------------------------------------------------------------------
# T5 -- renderable trace table, one row per link, no empty cells
# ---------------------------------------------------------------------------

def test_render_table_one_row_per_link_no_empty_cells():
    """T5: one row per link, every required column present and non-empty."""
    recorder = build_recorder()
    rows = recorder.render_table()

    assert isinstance(rows, list)
    assert len(rows) == len(_links(recorder))

    required = (
        "assertion_id",
        "referenced_data_snapshot_id",
        "data_source",
        "fetch_timestamp",
    )
    for row in rows:
        assert isinstance(row, dict)
        assert set(required) <= set(row)
        empty = [
            column
            for column in required
            if not (isinstance(row[column], str) and row[column].strip())
        ]
        assert empty == [], f"empty cells {empty} in row {row}"

    # The table must join through to the snapshot, so the source is visible.
    assert {row["data_source"] for row in rows} == {"yfinance", "sec-edgar", "fred"}


def test_render_table_row_order_is_insertion_order():
    """T5 / T8: row order is deterministic (insertion order)."""
    recorder = build_recorder()
    rows = recorder.render_table()
    assert [row["assertion_id"] for row in rows] == [
        assertion_id for assertion_id, _, _ in FIXTURE_ASSERTIONS
    ]


# ---------------------------------------------------------------------------
# T6 -- storage-bounding clause: non-critical links are optional
# ---------------------------------------------------------------------------

def test_omitting_noncritical_assertions_keeps_completeness():
    """T6: dropping a non-critical link must not fail T3 or T4."""
    critical_only = tuple(a for a in FIXTURE_ASSERTIONS if a[2])
    recorder = build_recorder(assertions=critical_only)
    report = recorder.audit()

    assert expected_critical_count(critical_only) == len(critical_only)
    assert completeness_gap(recorder, critical_only) == 0
    assert report.traceable is True
    assert len(_links(recorder)) == len(critical_only)


# ---------------------------------------------------------------------------
# T7 -- fetch_timestamp is UTC ISO-8601, tz-aware, parseable
# ---------------------------------------------------------------------------

def test_every_snapshot_timestamp_is_utc_aware_and_parseable():
    """T7: fromisoformat round-trips, tz-aware, zero UTC offset."""
    from datetime import datetime

    recorder = build_recorder(record_final=False)
    for snapshot in _snapshots(recorder):
        parsed = datetime.fromisoformat(snapshot.fetch_timestamp)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() is not None
        assert parsed.utcoffset().total_seconds() == 0


@pytest.mark.parametrize(
    "bad_timestamp",
    [
        "2026-11-24T13:30:00",          # naive: no tz
        "2026-11-24 13:30:00",          # naive: no tz
        "2026-11-24T13:30:00+05:00",    # tz-aware but not UTC
        "not-a-timestamp",
        "",
    ],
)
def test_non_utc_or_unparseable_timestamp_is_rejected(bad_timestamp):
    """T7: the recorder rejects a timestamp it cannot audit."""
    recorder = TraceRecorder()
    with pytest.raises(TraceError):
        recorder.record_snapshot(
            snapshot_id="snap-bad",
            data_source="yfinance",
            fetch_timestamp=bad_timestamp,
        )
    # The invalid snapshot must not have been stored: a decision citing it is
    # still an unresolved reference at audit time.
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-bad",),
    )
    report = recorder.audit()
    assert report.traceable is False
    assert "UNKNOWN_FINAL_REFERENCE" in {f.reason for f in report.findings}


# ---------------------------------------------------------------------------
# T8 -- determinism across two independent recorder instances
# ---------------------------------------------------------------------------

def test_two_instances_produce_identical_records():
    """T8: fixed fixture => byte-identical snapshots, links, report, table."""
    first = build_recorder()
    second = build_recorder()

    assert _snapshots(first) == _snapshots(second)
    assert _links(first) == _links(second)
    assert [s.to_dict() for s in _snapshots(first)] == [s.to_dict() for s in _snapshots(second)]
    assert [link.to_dict() for link in _links(first)] == [link.to_dict() for link in _links(second)]
    assert first.audit().to_dict() == second.audit().to_dict()
    assert first.render_table() == second.render_table()


def test_link_id_is_content_derived():
    """T8 / pinned R5: link_id is a stable function of (assertion, snapshot)."""
    first = build_recorder(record_final=False)
    second = build_recorder(record_final=False)

    first_ids = {link.assertion_id: link.link_id for link in _links(first)}
    second_ids = {link.assertion_id: link.link_id for link in _links(second)}
    assert first_ids == second_ids

    # A one-field change must move the id (not a constant, not a counter).
    distinct = set(first_ids.values())
    assert len(distinct) == len(first_ids)

    for link_id in distinct:
        assert not link_id.isdigit()
        assert len(link_id) >= 8


# ---------------------------------------------------------------------------
# T9 -- NEGATIVE test: a recorder that drops one critical link must fail T3
# ---------------------------------------------------------------------------

class DroppingRecorder(TraceRecorder):
    """Real recorder, but the k-th critical assertion is never stored.

    The other assertions still travel the real ``super().record_assertion``
    path, so T9 measures the completeness gate rather than a hand-written fake.
    """

    def __init__(self, drop_assertion_id: str) -> None:
        super().__init__()
        self._drop_assertion_id = drop_assertion_id

    def record_assertion(self, *, assertion_id, referenced_data_snapshot_id, critical):
        if critical and assertion_id == self._drop_assertion_id:
            return TraceLink(
                link_id=f"dropped-{assertion_id}",
                assertion_id=assertion_id,
                referenced_data_snapshot_id=referenced_data_snapshot_id,
                critical=False,  # silently demoted = the defect under test
            )
        return super().record_assertion(
            assertion_id=assertion_id,
            referenced_data_snapshot_id=referenced_data_snapshot_id,
            critical=critical,
        )


def test_recorder_dropping_one_critical_link_fails_completeness():
    """T9: proves T3 is a real gate (`.agent/rules.md` covenant 3)."""
    recorder = DroppingRecorder(drop_assertion_id="assert-guidance-cut")
    for snapshot_id, data_source, fetch_timestamp in FIXTURE_SNAPSHOTS:
        recorder.record_snapshot(
            snapshot_id=snapshot_id,
            data_source=data_source,
            fetch_timestamp=fetch_timestamp,
        )
    for assertion_id, snapshot_id, critical in FIXTURE_ASSERTIONS:
        recorder.record_assertion(
            assertion_id=assertion_id,
            referenced_data_snapshot_id=snapshot_id,
            critical=critical,
        )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=FINAL_DECISION_REFS,
    )

    # N still comes from the fixture's expected flags, so the demotion is visible.
    assert completeness_gap(recorder) == 1
    assert recorder.audit().resolved_links == expected_critical_count() - 1


# ---------------------------------------------------------------------------
# T-NEW -- build-session pinned decisions
# ---------------------------------------------------------------------------

def test_critical_is_keyword_only_with_no_default():
    """Pinned A4: omitting the explicit flag is a TypeError, not a guess."""
    recorder = TraceRecorder()
    recorder.record_snapshot(
        snapshot_id="snap-market-1",
        data_source="yfinance",
        fetch_timestamp="2026-11-24T13:30:00+00:00",
    )
    with pytest.raises(TypeError):
        recorder.record_assertion(  # type: ignore[call-arg]
            assertion_id="assert-revenue-growth",
            referenced_data_snapshot_id="snap-market-1",
        )
    with pytest.raises(TypeError):
        recorder.record_assertion(  # type: ignore[call-arg]
            "assert-revenue-growth",
            "snap-market-1",
            True,
        )
    assert _links(recorder) == ()


def test_duplicate_link_is_rejected_not_overwritten():
    """Pinned R5: re-asserting (assertion, snapshot) is a collision -> reject."""
    recorder = build_recorder(record_final=False)
    before = _links(recorder)

    with pytest.raises(TraceError):
        recorder.record_assertion(
            assertion_id="assert-revenue-growth",
            referenced_data_snapshot_id="snap-market-1",
            critical=True,
        )

    assert _links(recorder) == before


def test_duplicate_snapshot_is_rejected_not_overwritten():
    """Pinned R5 parity: a repeated snapshot_id must not overwrite evidence."""
    recorder = build_recorder(record_final=False)
    before = _snapshots(recorder)

    with pytest.raises(TraceError):
        recorder.record_snapshot(
            snapshot_id="snap-market-1",
            data_source="another-vendor",
            fetch_timestamp="2026-11-24T14:00:00+00:00",
        )

    assert _snapshots(recorder) == before


def test_one_snapshot_per_assertion_documented_workaround():
    """Pinned: multi-evidence uses distinct assertion ids, one snapshot each."""
    recorder = TraceRecorder()
    for snapshot_id, data_source, fetch_timestamp in FIXTURE_SNAPSHOTS[:2]:
        recorder.record_snapshot(
            snapshot_id=snapshot_id,
            data_source=data_source,
            fetch_timestamp=fetch_timestamp,
        )
    recorder.record_assertion(
        assertion_id="assert-revenue-growth#1",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    recorder.record_assertion(
        assertion_id="assert-revenue-growth#2",
        referenced_data_snapshot_id="snap-news-1",
        critical=True,
    )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1", "snap-news-1"),
    )

    report = recorder.audit()
    assert report.traceable is True
    assert report.resolved_links == 2


def test_audit_boundary_is_documented_in_module_docstring():
    """Pinned: the never-called gap must be stated where implementers read it."""
    doc = trace_recorder.__doc__ or ""
    lowered = doc.lower()
    assert "recorded assertions only" in lowered
    assert "never passed" in lowered or "never called" in lowered
    assert "distinct assertion ids" in lowered


# ---------------------------------------------------------------------------
# T-NEW -- import hygiene + clock ban (pinned R7)
# ---------------------------------------------------------------------------

ALLOWED_IMPORTS = {"dataclasses", "enum", "typing", "hashlib", "datetime", "__future__"}

FORBIDDEN_IMPORTS = {
    "time",
    "uuid",
    "os",
    "sys",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "http",
    "openai",
    "anthropic",
    "langchain",
    "langchain_core",
    "langgraph",
    "random",
    "secrets",
}

FORBIDDEN_CALLS = {
    "datetime.now",
    "datetime.today",
    "datetime.utcnow",
    "datetime.datetime.now",
    "datetime.datetime.today",
    "datetime.datetime.utcnow",
    "time.time",
    "time.monotonic",
    "uuid.uuid4",
    "uuid.uuid1",
    "uuid4",
    "uuid1",
}


def test_import_hygiene_ast():
    """Pinned R7: trace_recorder imports nothing outside the allowlist."""
    assert MODULE_PATH.exists()
    imported = _ast_imports(MODULE_PATH)

    forbidden = imported & FORBIDDEN_IMPORTS
    assert forbidden == set(), f"forbidden imports reached the recorder: {forbidden}"
    outside = imported - ALLOWED_IMPORTS
    assert outside == set(), f"imports outside the allowlist: {outside}"

    # Guard against an empty module: the recorder must actually be defined.
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    class_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert "TraceRecorder" in class_names


def test_no_clock_or_uuid_calls():
    """Pinned R7: no datetime.now / time.time / uuid4 anywhere in the recorder."""
    calls = _ast_called_attributes(MODULE_PATH)
    hits = calls & FORBIDDEN_CALLS
    assert hits == set(), f"clock/uuid calls reached the recorder: {hits}"


# ---------------------------------------------------------------------------
# T-ADV -- adversarial compliance block (verification-compliance session)
#
# Additive: pins conditions T1-T9 do not exercise -- the table's dangling row,
# a recorder with no critical links, duplicate/extra final decisions, the frozen
# return type, and malformed snapshot references.
# ---------------------------------------------------------------------------

def _one_snapshot_recorder() -> TraceRecorder:
    recorder = TraceRecorder()
    recorder.record_snapshot(
        snapshot_id="snap-market-1",
        data_source="yfinance",
        fetch_timestamp="2026-11-24T13:30:00+00:00",
    )
    return recorder


def test_render_table_dangling_link_keeps_every_cell_non_empty():
    """T-ADV / T5: a dangling link still renders one row, in order, no blanks.

    T5 only covers a fully resolved recorder. The pinned rule is "no empty
    cells" for EVERY row, so the placeholder path in ``render_table`` must be
    exercised: the row must stay in insertion order, keep its own columns, and
    substitute an explicit non-blank placeholder for the two snapshot columns.
    """
    recorder = _one_snapshot_recorder()
    resolved = recorder.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    dangling = recorder.record_assertion(
        assertion_id="assert-guidance-cut",
        referenced_data_snapshot_id="snap-never-recorded",
        critical=True,
    )

    rows = recorder.render_table()

    assert [row["assertion_id"] for row in rows] == [
        "assert-revenue-growth",
        "assert-guidance-cut",
    ]
    assert [row["link_id"] for row in rows] == [resolved.link_id, dangling.link_id]
    for row in rows:
        empties = [
            column
            for column in (
                "assertion_id",
                "link_id",
                "critical",
                "referenced_data_snapshot_id",
                "data_source",
                "fetch_timestamp",
            )
            if not (isinstance(row[column], str) and row[column].strip())
        ]
        assert empties == [], f"empty cells {empties} in row {row}"

    dangling_row = rows[1]
    assert dangling_row["referenced_data_snapshot_id"] == "snap-never-recorded"
    assert dangling_row["data_source"] != "yfinance", "the dangling row borrowed evidence"
    assert dangling_row["fetch_timestamp"] != "2026-11-24T13:30:00+00:00"

    # The table must not make the chain look healthier than the audit says.
    report = recorder.audit()
    assert report.traceable is False
    assert "DANGLING_SNAPSHOT" in {finding.reason for finding in report.findings}


def test_render_table_is_empty_before_any_recording():
    """T-ADV boundary: an empty recorder renders zero rows, not a blank row."""
    recorder = TraceRecorder()
    recorder.record_snapshot(
        snapshot_id="snap-market-1",
        data_source="yfinance",
        fetch_timestamp="2026-11-24T13:30:00+00:00",
    )
    assert recorder.render_table() == []
    assert recorder.audit().checked_links == 0


def test_recorder_with_no_critical_links_is_never_traceable():
    """T-ADV / NO_CRITICAL_LINKS: unmeasurable completeness must fail closed.

    T6 shows non-critical links may be omitted; the converse -- a run where
    *only* non-critical assertions exist -- has no coverage. With N == 0 the
    completeness invariant is vacuous, so the audit must refuse to bless it:
    not traceable, N == M == 0, and the NO_CRITICAL_LINKS finding present even
    when every reference resolves.
    """
    recorder = _one_snapshot_recorder()
    recorder.record_assertion(
        assertion_id="assert-tone-shift",
        referenced_data_snapshot_id="snap-market-1",
        critical=False,
    )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )

    report = recorder.audit()

    assert report.checked_links == 0
    assert report.resolved_links == 0
    assert report.traceable is False, "an all-non-critical run must not be blessed"
    assert "NO_CRITICAL_LINKS" in {finding.reason for finding in report.findings}


def test_recorder_with_no_links_at_all_reports_both_floor_findings():
    """T-ADV: empty evidence + zero critical links -> both reasons, never one."""
    recorder = _one_snapshot_recorder()
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )
    report = recorder.audit()

    assert report.traceable is False
    reasons = {finding.reason for finding in report.findings}
    assert {"NO_CRITICAL_LINKS"} <= reasons


def test_no_critical_links_finding_plus_a_dangling_link_still_fails():
    """T-ADV: the two independent floors compose (storage bound + dangling)."""
    recorder = _one_snapshot_recorder()
    recorder.record_assertion(
        assertion_id="assert-tone-shift",
        referenced_data_snapshot_id="snap-market-1",
        critical=False,
    )
    recorder.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-never-recorded",
        critical=True,
    )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )
    report = recorder.audit()

    assert report.checked_links == 1
    assert report.resolved_links == 0
    assert report.traceable is False
    assert "DANGLING_SNAPSHOT" in {finding.reason for finding in report.findings}


def test_duplicate_final_decision_references_are_counted_once():
    """T-ADV / T8: repeated references are deduplicated (order preserved).

    A repeated reference is the same evidence, not extra evidence: it must not
    inflate a count, must not produce a spurious UNKNOWN_FINAL_REFERENCE, and
    must leave the verdict byte-identical to the deduplicated form.
    """
    with_dupes = build_recorder(
        final_refs=("snap-market-1", "snap-market-1", "snap-news-1", "snap-market-1")
    )
    clean = build_recorder(final_refs=("snap-market-1", "snap-news-1"))

    report = with_dupes.audit()
    assert report.traceable is True
    assert report.findings == ()
    assert report.to_dict() == clean.audit().to_dict()

    repeated = TraceRecorder()
    repeated.record_snapshot(
        snapshot_id="snap-market-1",
        data_source="yfinance",
        fetch_timestamp="2026-11-24T13:30:00+00:00",
    )
    repeated.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    recorded = repeated.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=["snap-market-1", "snap-market-1", "snap-market-1"],
    )
    assert recorded.referenced_snapshot_ids == ("snap-market-1",)


def test_duplicate_unknown_final_reference_is_reported_once():
    """T-ADV: duplicating an UNRESOLVED reference must not double the finding."""
    recorder = build_recorder(
        final_refs=("snap-market-1", "snap-never-recorded", "snap-never-recorded")
    )
    report = recorder.audit()

    unknown = [
        finding
        for finding in report.findings
        if finding.reason == "UNKNOWN_FINAL_REFERENCE"
    ]
    assert len(unknown) == 1
    assert unknown[0].referenced_data_snapshot_id == "snap-never-recorded"
    assert report.traceable is False


def test_second_final_decision_is_rejected_and_state_is_unchanged():
    """T-ADV / pinned R5: exactly one final decision per recorder.

    The first decision must survive untouched (never overwritten), and the
    rejected call must not leave a partially-applied second decision behind.
    """
    recorder = build_recorder(final_refs=("snap-market-1",))
    before_audit = recorder.audit().to_dict()
    before_table = recorder.render_table()

    with pytest.raises(TraceError):
        recorder.record_final_decision(
            decision_id="decision-second",
            referenced_snapshot_ids=("snap-news-1", "snap-fred-1"),
        )

    assert recorder.audit().to_dict() == before_audit
    assert recorder.render_table() == before_table
    assert before_audit["traceable"] is True


def test_second_final_decision_with_identical_content_is_still_rejected():
    """T-ADV: idempotent re-recording is a collision too, not a no-op."""
    recorder = build_recorder()
    with pytest.raises(TraceError):
        recorder.record_final_decision(
            decision_id=FINAL_DECISION_ID,
            referenced_snapshot_ids=FINAL_DECISION_REFS,
        )
    assert recorder.audit().traceable is True


def test_record_final_decision_return_type_is_frozen():
    """T-ADV: the return type is the recorder's own frozen record, not a dict.

    Callers serialize via ``to_dict()``; the object must be immutable so a
    caller cannot retro-fit evidence into an already-recorded decision.
    (The verdict is deliberately NOT asserted here: a recorder with no critical
    link is not traceable by design, and that floor has its own test.)
    """
    recorder = _one_snapshot_recorder()
    recorder.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    recorded = recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )

    assert type(recorded).__name__ == "_FinalDecision"
    assert type(recorded).__module__ == trace_recorder.__name__
    assert isinstance(recorded.referenced_snapshot_ids, tuple)
    assert recorded.referenced_snapshot_ids == ("snap-market-1",)
    assert recorded.decision_id == FINAL_DECISION_ID

    # Immutability: no attribute assignment, no in-place tuple mutation.
    # A frozen dataclass raises FrozenInstanceError; a tuple has no append.
    with pytest.raises(dataclasses.FrozenInstanceError):
        recorded.decision_id = "mutated"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        recorded.referenced_snapshot_ids.append("snap-news-1")  # type: ignore[attr-defined]
    assert recorder.audit().traceable is True


def test_final_decision_rejects_a_bare_string_of_references():
    """T-ADV: a string is a sequence of characters, never of snapshot ids."""
    recorder = _one_snapshot_recorder()
    with pytest.raises(TraceError):
        recorder.record_final_decision(
            decision_id=FINAL_DECISION_ID,
            referenced_snapshot_ids="snap-market-1",  # type: ignore[arg-type]
        )
    # Nothing was stored: the recorder still reports NO_FINAL_DECISION.
    assert "NO_FINAL_DECISION" in {f.reason for f in recorder.audit().findings}


@pytest.mark.parametrize(
    "referenced", ["", "   ", None, 1, b"snap-market-1"], ids=repr
)
def test_record_assertion_rejects_malformed_snapshot_references(referenced):
    """T-ADV: a blank or non-text reference is a protocol fault, not a link."""
    recorder = _one_snapshot_recorder()
    with pytest.raises(TraceError):
        recorder.record_assertion(
            assertion_id="assert-revenue-growth",
            referenced_data_snapshot_id=referenced,  # type: ignore[arg-type]
            critical=True,
        )
    assert recorder.render_table() == []


@pytest.mark.parametrize("critical", [1, 0, "True", "true", None, 1.0, []])
def test_non_bool_critical_flag_is_rejected_not_coerced(critical):
    """T-ADV / pinned A4: truthiness is not a declaration.

    ``1`` and ``"True"`` are truthy, but coercing them would let a producing
    agent pass a *guess*; the flag is the agent's explicit criticality
    declaration, so anything but a real bool is a protocol fault.
    """
    recorder = _one_snapshot_recorder()
    with pytest.raises(TraceError):
        recorder.record_assertion(
            assertion_id="assert-revenue-growth",
            referenced_data_snapshot_id="snap-market-1",
            critical=critical,  # type: ignore[arg-type]
        )
    assert recorder.render_table() == []
    assert recorder.audit().checked_links == 0


def test_rejected_snapshot_leaves_a_critical_link_dangling():
    """T-ADV / T2: a refused snapshot is never stored, so links stay unresolved."""
    recorder = TraceRecorder()
    with pytest.raises(TraceError):
        recorder.record_snapshot(
            snapshot_id="snap-market-1",
            data_source="yfinance",
            fetch_timestamp="2026-11-24T13:30:00+01:00",  # not UTC
        )
    recorder.record_assertion(
        assertion_id="assert-revenue-growth",
        referenced_data_snapshot_id="snap-market-1",
        critical=True,
    )
    recorder.record_final_decision(
        decision_id=FINAL_DECISION_ID,
        referenced_snapshot_ids=("snap-market-1",),
    )
    report = recorder.audit()

    assert report.traceable is False
    assert report.checked_links == 1
    assert report.resolved_links == 0
    reasons = {finding.reason for finding in report.findings}
    assert {"DANGLING_SNAPSHOT", "UNKNOWN_FINAL_REFERENCE"} <= reasons


def test_audit_report_finding_order_is_deterministic_across_instances():
    """T-ADV / T8: multi-finding reports sort identically on every instance."""
    kwargs = {"final_refs": ("snap-market-1", "snap-never-recorded")}
    first = build_recorder(**kwargs).audit()
    second = build_recorder(**kwargs).audit()

    assert first.to_dict() == second.to_dict()
    order = [reason.value for reason in trace_recorder.FINDING_PRECEDENCE]
    positions = [order.index(finding.reason) for finding in first.findings]
    assert positions == sorted(positions)

