# ADR-003: Evidence-Chain Traceability

- **Status:** Accepted
- **Decision owner:** CUI Haoyu (60760270)
- **Date:** 2026-11-24

## Context
The baseline writes only the final decision to the memory log; no chain links a
claim to the data snapshot it cited.

## Decision
Adopt a `TraceRecorder` that records each critical assertion as
assertion_id → referenced_data_snapshot_id → data_source + fetch_timestamp.
Non-critical assertions are recorded optionally. The final decision is
re-traceable to its evidence.

## Alternatives considered
- Logging raw report text only (baseline) — not auditable.
- Full per-token provenance — too heavy.

## Consequences
- Supports REQ-TRACEABILITY; auditability and renderable trace table.
- Storage/complexity cost; bounded by logging only critical assertions.

## Reopen conditions
Storage overhead too high, or evidence chain is incomplete → adjust the
critical-assertion classification.

## Architectural design process

The ADD iteration started from the auditability driver: the baseline memory log
keeps the decision but not the evidence behind it. Three candidates were
considered: raw report logging (too weak), full per-token provenance (too
heavy), and critical-assertion linking (selected). The selected contract is
`assertion_id → snapshot_id → data_source + fetch_timestamp`; the recorder
deduplicates identical snapshots and emits a sidecar/table for review. The
parallel-analyst integration later forced the evidence unit from per-thread
attribution to the G1 run-level set (ADR-006); that is a scope revision of this
decision, not a reversal. The consequence is a bounded storage cost and a
renderable audit trail; the reopen condition is a measured storage/completeness
problem.

> **CUI Haoyu note:** I own this element and implemented it in
> `src/trace_recorder.py`; the integration/run-level refinement is in ADR-006.