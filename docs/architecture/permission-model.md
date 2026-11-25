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

(TODO: finalize; default-deny everywhere. This is a seed, not the authority —
`.opencode/permissions.jsonc` is authoritative.)