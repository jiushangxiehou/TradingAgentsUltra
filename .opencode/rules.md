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

(TODO: expand with project-specific rules as they emerge.)