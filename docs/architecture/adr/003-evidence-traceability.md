# ADR-003: Evidence-Chain Traceability

- **Status:** Proposed
- **Decision owner:** (fill in)
- **Date:** (fill in)

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
(TODO.)