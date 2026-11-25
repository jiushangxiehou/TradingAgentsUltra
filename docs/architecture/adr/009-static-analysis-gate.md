# ADR-009: The Static-Analysis Gate and Its Typing-Only Touch

- **Status:** Accepted
- **Decision owner:** CUI Haoyu (60760270), team lead
- **Date:** 2026-11-25
- **Related:** ADR-004 (guardrail contract), ADR-006 (gate order), D7 gate 2

## Context

D7 gate 2 requires lint, type check and dependency check on every commit, plus
contract/security/API-surface/permission checks on safety-relevant paths. The
workflow had a placeholder: `ruff check src test` and `pip check` were real
blocking checks, but **no type checker ran**, and the "safety-path" half was a
comment.

The project's own typing is uneven by design. `src/guardrail.py` is typed
precisely (frozen dataclasses, total trigger order); the decision adapter
deliberately passes `object`-typed values into a `Decision` so the frozen
guardrail, not the adapter, decides what is malformed (ADR-006, policy A+Bstrict).
A whole-repository mypy run would also have to type the pinned baseline and the
LangChain call sites, i.e. code the project does not own.

## Decision

### 1. mypy, scoped to the project-owned `src/`

`mypy.ini` checks `src/` with `ignore_missing_imports` and
`follow_imports = silent`: the baseline is treated as `Any`, so the gate
checks **our boundary** rather than other people's dynamic code.
`mypy>=1.11` joins `requirements.txt` and the lock file.

CI runs `python -m mypy` as a blocking job. The gate is also runnable locally
with the project venv, and it is reproducible: the config and the requirement
pin are in the repository.

### 2. The touch is typing-only, and it is recorded

Making `src/` clean required three small edits. None changes behaviour; all are
covered by the existing tests:

| File | Edit | Why |
|---|---|---|
| `src/trace_recorder.py` | `utcoffset()` narrowed once into a local | The old code called `utcoffset()` twice; mypy could not prove the second call non-`None`, and a custom `tzinfo` returning `None` would raise `AttributeError` instead of `TraceError`. The new code raises the documented `TraceError` in that case. |
| `src/integration/decision_adapter.py` | four `# type: ignore[arg-type]` with a comment | The `object` types are the policy: the frozen guardrail decides malformation (ADR-006). The ignores make that explicit rather than hiding it behind an `Any`. |
| `src/integration/trace_adapter.py` | `router_module: Any` (was `object`), parameters typed `Any` | The seam calls methods of the baseline router; `Any` is the honest type for a dynamically patched module. |

`src/guardrail.py` — the frozen safety boundary — was **not** modified. The
covenant's rule that a safety-critical change needs an ADR and human approval is
satisfied by this ADR plus the team lead's instruction of 2026-11-25; the
guardrail tests (39 cases, including the zero-escape negative test) pass
unchanged.

### 3. The safety-path checks are a script, not a comment

`scripts/check_safety_paths.py` runs the contract/security/API-surface/permission
checks the brief asks for:

- **contract** — the pure modules import only their allowlisted stdlib modules,
  call no clock/UUID, and keep their ADR reference in the module docstring;
- **security** — no network/OS/subprocess imports in the guardrail or the
  recorder; `.opencode/permissions.jsonc` still defaults to deny;
- **API surface** — the public names of the frozen modules match
  `docs/architecture/api-surface.json`; a changed surface fails until the
  manifest is updated with the change;
- **permission** — every whitelist path is declared, and the safety-critical
  files are covered by a guard rule.

## Alternatives considered

- **No type checker (keep the placeholder).** Rejected: gate 2 would stay
  partially unimplemented, which the README and the debt register already
  called out as the honest status.
- **mypy over the whole repository.** Rejected: thousands of findings in the
  pinned baseline and in LangChain typing would be silenced with a blanket
  ignore, which is worse than a scoped check that is actually enforced.
- **pyright.** Rejected: an extra Node toolchain in CI for no additional
  guarantee over mypy at this scope.
- **Leave the three files untouched and exclude them.** Rejected: it would
  shrink the checked surface to nothing interesting; the trace module is part
  of the trust boundary.

## Consequences

- A type error in `src/` now blocks a merge; the check is fast and local.
- The typing-only edits touch two files in the trace boundary; they are
  recorded here, in the review memo and in the AI-use log, and the full offline
  suite is the regression evidence.
- The checking surface is deliberately narrower than "all code": the pinned
  baseline and the dynamic graph are not type-checked. That is a scope decision,
  stated rather than implied.

## Reopen conditions

- **R-1** `src/` grows to wrap a substantial part of the graph — widen the
  scope and pay down the `Any` imports with typed protocols.
- **R-2** A real defect escapes because a baseline call site was treated as
  `Any` — add a typed protocol at the seam instead of widening the ignore.
- **R-3** mypy's rules hide a genuine error class the team needs — add the
  specific flag, not a global relaxation.

## Verification

```text
$ python -m mypy
Success: no issues found in 12 source files
$ python scripts/check_safety_paths.py
check-safety-paths: PASS (contract, security, API surface, permission)
```
