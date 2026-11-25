# MCP Tool Manifest (D3)

> The tools the coding agent may call, and which roles may call them.

## Tool roles
| Role | Can call |
|------|----------|
| Root coding agent | `read_file`, `write_file`, `edit`, `bash`, `test`, `mcp__*` (guardrail/verify) |
| Plan agent | `read_file`, `search`, `glob` |
| Verification agent | `bash` (pytest), `read_file` |

## Allowed tools (seed)
| Tool | Scope | Roles |
|------|-------|-------|
| `read_file` | any whitelisted path | root, plan, verifier |
| `write_file` / `edit` | `src/**`, `test/**`, `prompts/**` | root |
| `bash` | build/test commands | root, verifier |
| `pytest` | run test suites | root, verifier |

## Disallowed (examples)
- Calling MCP tools outside the manifest.
- Writing to `.opencode/*`, `.agent/*`, `docs/code-governance/*` (human-only).
- Reading/writing paths outside the whitelist.

(TODO: finalize once permissions.jsonc is authoritative.)