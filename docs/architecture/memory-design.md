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
- (TODO: who owns each state artifact; how rollback happens.)

## Retention
- (TODO: retention/rotation; `memory_log_max_entries` prunes oldest resolved.)

## Privacy
- No API keys are recorded (see `run_settings` allowlist). Do not include keys.