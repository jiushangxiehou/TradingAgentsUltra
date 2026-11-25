# Memory / State Design

> What state survives across sessions, interruptions, and versions.

## Survives across sessions / versions
- **Memory log:** past decisions and their settlement reflections
  (`~/.tradingagents/memory/trading_memory.md`), loaded for the Portfolio
  Manager (point-in-time as of the trade date).
- **Checkpoints:** per-ticker SQLite (`~/.tradingagents/cache/checkpoints/*.db`)
  for resume, cleared on successful completion.
- **Run reports and state JSON:** under `results_dir`.

## Write & retrieval policy
- Memory log is append-only; each completed run appends its decision.
- Settlement fetches the realised return and generates a reflection per decision.
- Retrieval filters lessons by the trade date (point-in-time) for historical runs.

## Ownership
- **Memory log:** owned by `TradingMemoryLog` / `TradingAgentsGraph`; append-only.
  The graph writes a decision, settlement and reflection; it does not rewrite
  past entries. Rollback means restoring a backup of the markdown file, not
  editing a decision in place.
- **Checkpoints:** owned by the graph checkpointer; one SQLite database per
  ticker/date/portfolio fingerprint. A successful run clears its checkpoint; a
  crashed run can resume from the last node. The checkpoint signature includes
  the analyst selection, debate/risk depth and settings digest, so a changed run
  starts fresh instead of silently resuming stale state.
- **Reports and state JSON:** owned by the CLI/integration run; written under the
  run's `results_dir`. They are immutable artefacts; rollback is a file restore,
  not an overwrite.
- **Sidecar:** owned by `GuardedTradingAgentsGraph`; written after the memory log
  so a trace failure cannot cost the decision its memory entry. A failed write
  is recorded as `sidecar_error`.

## Retention
- `memory_log_max_entries` (when set) prunes the oldest **resolved** entries;
  pending entries are never pruned.
- Checkpoints are cleared on successful completion and are intended for crash
  resume, not long-term storage.
- Run reports/state/sidecars are retained locally for audit. They are not
  automatically rotated; the team should archive or remove them deliberately.
- `results_dir`, `data_cache_dir` and `memory_log_path` are configurable through
  `TRADINGAGENTS_*` variables; the default is `~/.tradingagents`.

## Privacy and boundaries
- No API keys are recorded; `run_settings` uses an allowlist and the guardrail
  sidecar carries the declared book/limits, not credentials.
- The sidecar’s `load_report` contains the declared size, short, cash and
  position context. Treat run artefacts as account-sensitive even when the code
  is public.
- Do not commit `.env`, `agent.env`, keys or transcripts containing secrets.

## Privacy
- No API keys are recorded (see `run_settings` allowlist). Do not include keys.