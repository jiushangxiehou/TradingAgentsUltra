# Permission Model

> File-level read/write rights for each AI coding agent role. Default = no
> read, no write; every path is explicitly whitelisted. Machine-readable form:
> `.opencode/permissions.jsonc` (authoritative).

## Roles
- **Root coding agent:** broad read, scoped write.
- **Plan agent:** read-only on architecture artifacts.
- **Verification agent:** read-only on code; read-write on tests.
- **Human:** full; edits governance files only.

## Whitelist (seed)
| Path | Root | Plan | Verifier |
|------|------|------|----------|
| `src/**` | RW | R | R |
| `test/**` | RW | R | RW |
| `docs/req/**` | R | R | R |
| `docs/architecture/**` | R | R | R |
| `docs/code-governance/**` | R | R | R |
| `.opencode/*` | R | R | R |
| `.agent/*` | R | R | R |
| `prompts/**` | RW | R | R |
| `AGENTS.md`, `Prompt.md` | R | R | R |

## Enforcement

- Default is **deny**: a path not in the whitelist is not readable or writable.
- `.opencode/permissions.jsonc` is the machine-readable authority; this markdown
  table explains the intent and must not be treated as a second grant.
- Human-only files (`.opencode/*`, `.agent/*`, `docs/code-governance/*`, the
  baseline pin) may be edited only by a human reviewer; the agent may read them.
- A write to the pinned baseline, the guardrail/trace contracts or an invariant
  requires an ADR + human approval, in addition to the path permission.
- The verification agent may read code and read/write tests; it may not change
  production code or the guardrail.
- Any path outside the whitelist is a permission defect, not a convenience.

> **CUI Haoyu note:** the trace/guardrail integration files are in `src/**` and
> are subject to the root-agent/verifier split above; no special write exception
> is claimed for them.