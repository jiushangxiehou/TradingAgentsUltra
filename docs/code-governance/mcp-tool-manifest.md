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

## Enforcement and boundaries

- `.opencode/permissions.jsonc` is authoritative for the path/role rights; this
  manifest is the tool view of the same contract.
- A tool call outside the manifest is denied. The guardrail/verify MCP helpers
  are read-only checks; they do not grant a write or a decision override.
- `bash` is limited to build/test commands in the repository; it is not a
  general escape from the path whitelist.
- `pytest` may run the offline suite without keys; live tests need the
  environment keys and are not part of the default agent loop.
- The agent may not call an external MCP server that is not listed here.

> **CUI Haoyu note:** the guardrail/trace verification was run through the
> offline test suite and the guarded CLI, not through a new privileged tool.