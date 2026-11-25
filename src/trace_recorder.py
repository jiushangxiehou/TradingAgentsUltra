"""Evidence-chain trace recorder (REQ-TRACEABILITY, ADR-003).

ADR-003 / REQ-TRACEABILITY / INV-TRACE-COMPLETENESS

Records the evidence chain assertion_id -> referenced_data_snapshot_id ->
data_source + fetch_timestamp, and audits a final decision against it. Pure
and in-memory only: no clock, no uuid, no network, no LLM. Every timestamp is
supplied by the caller, and every identity is content-derived, so the same
recorded content always produces byte-identical records and reports.

Pinned semantics (requirements session + architecture session)
--------------------------------------------------------------
critical    ``record_assertion`` takes ``critical`` as keyword-only with no
            default. The producing agent must state explicitly whether an
            assertion is critical; omitting the flag is a ``TypeError``, never
            a guess.
link_id     content-derived from (assertion_id, referenced_data_snapshot_id).
            Re-recording the same pair is a collision -> ``TraceError``; a
            recorded link is never overwritten. Likewise a repeated
            ``snapshot_id`` is rejected, and a second
            ``record_final_decision`` is rejected.
Timestamp   ``fetch_timestamp`` must be UTC ISO-8601, timezone-aware, with a
            zero UTC offset, and parseable by ``datetime.fromisoformat``.
            Anything else raises ``TraceError`` and is NOT stored, so a later
            decision citing it stays an unresolved reference.
Dangling    ``record_assertion`` never drops a link. A reference to a snapshot
            that was never recorded is stored as-is and surfaces as the
            ``DANGLING_SNAPSHOT`` finding when ``audit()`` runs.
Audit       ``checked_links`` counts recorded critical links (N);
            ``resolved_links`` counts those whose snapshot was recorded (M).
            ``traceable`` requires every critical link resolved, at least one
            final-decision reference that resolves, and no findings.
Table       ``render_table()`` returns one row per recorded link, in insertion
            order, with no empty cells.

Finding reasons (frozen vocabulary)
-----------------------------------
``DANGLING_SNAPSHOT``        a recorded assertion cites a snapshot never recorded.
``UNKNOWN_FINAL_REFERENCE``  the final decision cites a snapshot never recorded.
``NO_FINAL_DECISION``        no final decision was recorded.
``NO_EVIDENCE``              the final decision references no snapshot at all.
``NO_CRITICAL_LINKS``        nothing critical was asserted, so completeness is
                             unmeasurable; the audit refuses to bless it.
``EMPTY_FIELD``              an identifier or source/decision field was blank.

Audit boundary -- recorded assertions only (pinned by the reviewer)
-------------------------------------------------------------------
``audit()`` audits recorded assertions only. It measures whether each assertion
that was given to ``record_assertion`` is resolvable. It can never detect a
critical assertion that was never passed to the recorder at all -- nothing in
the recorder's memory can testify to a call that did not happen. A critical
assertion silently omitted by a producing agent therefore leaves NO trace and
NO finding. Closing that never-called gap needs an interface change (the
producing agents must declare their critical assertions up-front) and is
deferred to the next ADR.

One-snapshot-per-assertion workaround
-------------------------------------
``link_id`` is derived from (assertion_id, referenced_data_snapshot_id), so one
assertion id carries exactly one evidence snapshot. An assertion resting on
several pieces of evidence is therefore recorded under distinct assertion ids
(e.g. ``assert-revenue-growth#1``, ``assert-revenue-growth#2``), one snapshot
each, and every one of those links is audited separately.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final


class TraceError(ValueError):
    """A recorder *protocol* fault: a collision, a bad timestamp, bad input."""


class FindingReason(str, Enum):  # noqa: UP042 - pinned enum base; StrEnum changes str/format semantics
    """Frozen finding vocabulary. Every audit finding names exactly one."""

    DANGLING_SNAPSHOT = "DANGLING_SNAPSHOT"
    UNKNOWN_FINAL_REFERENCE = "UNKNOWN_FINAL_REFERENCE"
    NO_FINAL_DECISION = "NO_FINAL_DECISION"
    NO_EVIDENCE = "NO_EVIDENCE"
    NO_CRITICAL_LINKS = "NO_CRITICAL_LINKS"
    EMPTY_FIELD = "EMPTY_FIELD"


# Pinned reporting order, so a report with several findings is deterministic.
FINDING_PRECEDENCE: Final[tuple[FindingReason, ...]] = (
    FindingReason.EMPTY_FIELD,
    FindingReason.DANGLING_SNAPSHOT,
    FindingReason.NO_FINAL_DECISION,
    FindingReason.NO_EVIDENCE,
    FindingReason.UNKNOWN_FINAL_REFERENCE,
    FindingReason.NO_CRITICAL_LINKS,
)


# ---------------------------------------------------------------------------
# Frozen records
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DataSnapshot:
    """One fetched evidence snapshot: what was read, from where, and when."""

    snapshot_id: str
    data_source: str
    fetch_timestamp: str

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "data_source": self.data_source,
            "fetch_timestamp": self.fetch_timestamp,
        }


@dataclass(frozen=True, slots=True)
class TraceLink:
    """One assertion -> evidence edge. ``critical`` is the agent's own flag."""

    link_id: str
    assertion_id: str
    referenced_data_snapshot_id: str
    critical: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "link_id": self.link_id,
            "assertion_id": self.assertion_id,
            "referenced_data_snapshot_id": self.referenced_data_snapshot_id,
            "critical": self.critical,
        }


@dataclass(frozen=True, slots=True)
class AuditFinding:
    """One reason the audit failed. A failure, never a warning."""

    assertion_id: str
    reason: str
    referenced_data_snapshot_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "assertion_id": self.assertion_id,
            "reason": self.reason,
            "referenced_data_snapshot_id": self.referenced_data_snapshot_id,
        }


@dataclass(frozen=True, slots=True)
class AuditReport:
    """The audit verdict: ``checked_links`` is N, ``resolved_links`` is M."""

    traceable: bool
    checked_links: int
    resolved_links: int
    findings: tuple[AuditFinding, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "traceable": self.traceable,
            "checked_links": self.checked_links,
            "resolved_links": self.resolved_links,
            "findings": [finding.to_dict() for finding in self.findings],
        }


# ---------------------------------------------------------------------------
# Internal state: the final decision (not part of the frozen public records)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _FinalDecision:
    decision_id: str
    referenced_snapshot_ids: tuple[str, ...]


# ---------------------------------------------------------------------------
# Content-derived identity and validation
# ---------------------------------------------------------------------------

def _link_id(assertion_id: str, referenced_data_snapshot_id: str) -> str:
    """``link_id`` is a pure function of (assertion_id, snapshot_id).

    No counter, no uuid, no clock -- so the same pair always yields the same
    id, and a differing pair cannot collide.
    """
    payload = f"{assertion_id}\x00{referenced_data_snapshot_id}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"tl-{digest[:16]}"


def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TraceError(f"{field} must be a non-empty string, got {value!r}")
    return value


def _require_utc_iso8601(value: object) -> str:
    """Accept only a tz-aware ISO-8601 timestamp whose UTC offset is zero."""
    text = _require_text(value, "fetch_timestamp")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TraceError(f"fetch_timestamp is not ISO-8601: {text!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TraceError(f"fetch_timestamp must be timezone-aware: {text!r}")
    if parsed.utcoffset().total_seconds() != 0:
        raise TraceError(f"fetch_timestamp must be UTC (zero offset): {text!r}")
    return text


# ---------------------------------------------------------------------------
# The recorder
# ---------------------------------------------------------------------------

class TraceRecorder:
    """Append-only, in-memory evidence-chain recorder.

    Every ``record_*`` call either stores its record or raises ``TraceError``;
    nothing is silently dropped and nothing is overwritten. Inspection goes
    through ``render_table()`` and ``audit()`` only.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, DataSnapshot] = {}
        self._links: list[TraceLink] = []
        self._link_ids: set[str] = set()
        self._final_decision: _FinalDecision | None = None

    # -- recording ---------------------------------------------------------

    def record_snapshot(
        self, *, snapshot_id: str, data_source: str, fetch_timestamp: str
    ) -> DataSnapshot:
        """Record one evidence snapshot; a repeated id is rejected.

        REQ-TRACEABILITY: the validator runs BEFORE anything is stored, so a
        rejected timestamp leaves the recorder exactly as it was.
        """
        snapshot_id = _require_text(snapshot_id, "snapshot_id")
        data_source = _require_text(data_source, "data_source")
        fetch_timestamp = _require_utc_iso8601(fetch_timestamp)

        if snapshot_id in self._snapshots:
            raise TraceError(
                f"duplicate snapshot_id: {snapshot_id!r} (already recorded; "
                "evidence is never overwritten)"
            )

        snapshot = DataSnapshot(
            snapshot_id=snapshot_id,
            data_source=data_source,
            fetch_timestamp=fetch_timestamp,
        )
        self._snapshots[snapshot_id] = snapshot
        return snapshot

    def record_assertion(
        self, *, assertion_id: str, referenced_data_snapshot_id: str, critical: bool
    ) -> TraceLink:
        """Record one assertion -> snapshot link; never drops, never overwrites.

        REQ-TRACEABILITY / INV-TRACE-COMPLETENESS. A dangling reference is
        stored as-is -- it is a failure the audit must surface, not a record
        the recorder may discard. ``critical`` has no default: the producing
        agent states it explicitly.
        """
        assertion_id = _require_text(assertion_id, "assertion_id")
        referenced_data_snapshot_id = _require_text(
            referenced_data_snapshot_id, "referenced_data_snapshot_id"
        )
        if not isinstance(critical, bool):
            raise TraceError(f"critical must be a bool, got {type(critical).__name__}")

        link_id = _link_id(assertion_id, referenced_data_snapshot_id)
        if link_id in self._link_ids:
            raise TraceError(
                f"duplicate link: {link_id} for ({assertion_id!r}, "
                f"{referenced_data_snapshot_id!r}) (already recorded; "
                "links are never overwritten)"
            )

        link = TraceLink(
            link_id=link_id,
            assertion_id=assertion_id,
            referenced_data_snapshot_id=referenced_data_snapshot_id,
            critical=critical,
        )
        self._links.append(link)
        self._link_ids.add(link_id)
        return link

    def record_final_decision(
        self, *, decision_id: str, referenced_snapshot_ids: tuple[str, ...] | list[str]
    ) -> _FinalDecision:
        """Record the one final decision and the snapshots it cites.

        Exactly one final decision per recorder: a second call is a
        ``TraceError``. References are stored verbatim (deduplicated, order
        preserved) so an unknown one can be reported by the audit.
        """
        decision_id = _require_text(decision_id, "decision_id")
        if self._final_decision is not None:
            raise TraceError(
                f"duplicate final decision: {decision_id!r} "
                f"(already recorded {self._final_decision.decision_id!r})"
            )
        if isinstance(referenced_snapshot_ids, str):
            raise TraceError("referenced_snapshot_ids must be a sequence, not a string")

        refs: list[str] = []
        for reference in referenced_snapshot_ids:
            reference = _require_text(reference, "referenced_snapshot_ids entry")
            if reference not in refs:
                refs.append(reference)

        decision = _FinalDecision(
            decision_id=decision_id,
            referenced_snapshot_ids=tuple(refs),
        )
        self._final_decision = decision
        return decision

    # -- inspection --------------------------------------------------------

    def audit(self) -> AuditReport:
        """Walk the recorded chain and report whether it is traceable.

        REQ-TRACEABILITY / INV-TRACE-COMPLETENESS. Audits recorded assertions
        only -- see the module docstring's audit boundary. N (``checked_links``)
        counts recorded critical links; M (``resolved_links``) counts those
        whose snapshot was recorded. ``traceable`` requires M == N with N > 0,
        at least one resolving final-decision reference, and no findings.
        """
        findings: list[AuditFinding] = []

        # A snapshot with a blank source or timestamp would defeat the chain.
        for snapshot in self._snapshots.values():
            if not snapshot.data_source.strip() or not snapshot.fetch_timestamp.strip():
                findings.append(
                    AuditFinding(
                        assertion_id="",
                        reason=FindingReason.EMPTY_FIELD.value,
                        referenced_data_snapshot_id=snapshot.snapshot_id,
                    )
                )

        checked_links = 0
        resolved_links = 0
        for link in self._links:
            if not link.critical:
                continue  # non-critical links are optional (storage bound)
            checked_links += 1
            if link.referenced_data_snapshot_id in self._snapshots:
                resolved_links += 1
            else:
                findings.append(
                    AuditFinding(
                        assertion_id=link.assertion_id,
                        reason=FindingReason.DANGLING_SNAPSHOT.value,
                        referenced_data_snapshot_id=link.referenced_data_snapshot_id,
                    )
                )

        decision = self._final_decision
        decision_id = decision.decision_id if decision is not None else ""
        final_references = decision.referenced_snapshot_ids if decision is not None else ()

        if decision is None:
            findings.append(
                AuditFinding(
                    assertion_id="",
                    reason=FindingReason.NO_FINAL_DECISION.value,
                    referenced_data_snapshot_id="",
                )
            )
        elif not final_references:
            findings.append(
                AuditFinding(
                    assertion_id=decision_id,
                    reason=FindingReason.NO_EVIDENCE.value,
                    referenced_data_snapshot_id="",
                )
            )

        for reference in final_references:
            if reference not in self._snapshots:
                findings.append(
                    AuditFinding(
                        assertion_id=decision_id,
                        reason=FindingReason.UNKNOWN_FINAL_REFERENCE.value,
                        referenced_data_snapshot_id=reference,
                    )
                )

        if checked_links == 0:
            # Nothing critical was asserted: completeness is unmeasurable, so
            # the audit must not bless the run as traceable (fail closed).
            findings.append(
                AuditFinding(
                    assertion_id=decision_id,
                    reason=FindingReason.NO_CRITICAL_LINKS.value,
                    referenced_data_snapshot_id="",
                )
            )

        traceable = (
            not findings
            and checked_links > 0
            and resolved_links == checked_links
            and any(reference in self._snapshots for reference in final_references)
        )

        order = {reason.value: index for index, reason in enumerate(FINDING_PRECEDENCE)}
        findings.sort(
            key=lambda finding: (
                order[finding.reason],
                finding.assertion_id,
                finding.referenced_data_snapshot_id,
            )
        )

        return AuditReport(
            traceable=traceable,
            checked_links=checked_links,
            resolved_links=resolved_links,
            findings=tuple(findings),
        )

    def render_table(self) -> list[dict[str, object]]:
        """One row per recorded link, in insertion order, with no empty cells.

        The row joins the link to its snapshot, so the reviewer sees the
        citation and its source on the same line. A dangling link prints an
        explicit placeholder instead of a blank cell.
        """
        rows: list[dict[str, object]] = []
        for link in self._links:
            snapshot = self._snapshots.get(link.referenced_data_snapshot_id)
            rows.append(
                {
                    "assertion_id": link.assertion_id,
                    "link_id": link.link_id,
                    "critical": str(link.critical),
                    "referenced_data_snapshot_id": link.referenced_data_snapshot_id,
                    "data_source": snapshot.data_source if snapshot is not None else "(unresolved)",
                    "fetch_timestamp": (
                        snapshot.fetch_timestamp if snapshot is not None else "(unresolved)"
                    ),
                }
            )
        return rows
