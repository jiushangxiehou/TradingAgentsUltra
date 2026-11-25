# .opencode/rules.md — Always-On Behavioral Rules (D3)

> Project-level, always-on behavioral rules for the coding agent. **Human-only
> file** — the agent does not edit this.

## Always-on rules
1. Read `AGENTS.md` first; follow the architecture artifact reading order.
2. **Stop for approval before generating code.** Produce an execution plan
   first (traceability, interface contract, scope, testing strategy, steps).
3. **Extend the baseline, never replace it**, unless an ADR authorises.
4. **No non-agentic modification** — all code is produced by the coding agent.
5. **Every change updates `docs/ai-use-log.yaml`** before a PR can merge.
6. Respect authority boundaries: architecture blueprint and covenant
   (`docs/architecture/*`, `.agent/rules.md`) are authoritative; agent
   suggestions are advisory.
7. Run the deterministic offline tests and the full prior suite (zero
   regressions) before declaring work done.
8. Keep module ↔ architectural-element mapping consistent.

9. **No bypass of the gate or trace.** Do not edit a verdict, remove a trigger,
   skip the sidecar or claim a pass without the CLI/test evidence.
10. **Keep the D4 record current.** A change that affects a requirement, invariant,
    module boundary or gate updates the review memo, debt register, bug diary or
    verification map in the same work unit.
11. **Use the project environment.** Run the project `.venv`, not the global
    interpreter; never install a dependency silently or commit a key.
12. **Respect the pinned baseline.** The root layout is deliberate; a baseline
    edit needs an ADR/override, and `scripts/verify_baseline.py --strict` is a
    gate, not a suggestion.