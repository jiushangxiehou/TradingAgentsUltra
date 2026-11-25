# ADR-008: Declared Baseline Overrides for the Dev Tree

- **Status:** Accepted
- **Decision owner:** CUI Haoyu (60760270), team lead
- **Date:** 2026-11-25
- **Amends:** ADR-006 §"declared scope limit" (baseline drift), the README baseline section
- **Related:** ADR-007 (dev is the submission tree)

## Context

The pinned TradingAgents 0.7.1 baseline is the repository root (`PINNED_COMMIT.txt`,
213 blobs). On `dev`, nineteen pinned files are modified because the two
enhancements must be installed at the call sites the graph actually uses:

- **feature-f (Fan Hao, 60835652)** — eleven files: the researchers, the three
  risk debators, both managers, `agents/state.py`,
  `graph/conditional_logic.py`, `graph/propagation.py`.
- **feature-z (ZhuXuan, 60377218)** — six files: `agents/analysts/turn.py`,
  `agents/analysts/sentiment_analyst.py`, `agents/post_screen.py`,
  `agents/structured.py`, `memory/reflection.py`, `llm_clients/factory.py`,
  plus `graph/trading_graph.py`.
- **shared** — `default_config.py` (both feature key sets).
- **CUI Haoyu (60760270)** — `graph/setup.py` (termination wiring, ADR-005).

`scripts/verify_baseline.py --strict` therefore failed on `dev` (19 altered
files). The covenant says two things at once: "editing a pinned file, or merging
a branch that does, requires an ADR or a declared override" and "the verifier is
not to be weakened to make the tree pass". The old verifier had no way to
express a *declared* difference, so the only way to pass was to undeclare it —
which is exactly the weakening the covenant forbids.

## Decision

### 1. A machine-readable declaration

`scripts/baseline-overrides.json` is the single declaration:

- `project_owned` — the five files the project owns on every layout
  (`README.md`, `.gitignore`, `.env.example`, `requirements.txt`,
  `.github/workflows/ci.yml`). Reported, never a failure.
- `dev_overrides` — the nineteen dev differences. Each entry names `path`,
  `owner` (a person, with student id), `requirement`, `commit`, `reason` and
  `adr`. The human-readable view is `docs/architecture/baseline-overrides.md`.

### 2. The verifier's rule is "declare, never silently skip"

`scripts/verify_baseline.py` now:

- fails on a **missing** pinned file;
- fails on an **altered** pinned file that is **not declared**;
- reports a declared alteration as `dev-override` (counted, printed with its
  owner);
- fails on a declaration whose path is not in the pinned set (`UNKNOWN`) — a
  typo is not a grant;
- fails under `--strict` on a **stale** declaration (a declared file that no
  longer differs), so the manifest cannot rot;
- keeps the vendor-layout rule unchanged: any extra file fails.

The verifier still fingerprints content with CRLF folded to LF and still catches
appended lines, altered bytes and extra files. What changed is that a declared
difference is *visible* instead of being a silent failure or a silent pass.

### 3. CI runs the verifier on every push and pull request

A dedicated `baseline-integrity` job runs `python scripts/verify_baseline.py --strict`.
A drifted file that nobody declared blocks the merge.

## Alternatives considered

- **Restore the nineteen files and port the enhancements into `src/`.**
  Rejected for this submission: the call sites are inside the graph and the
  agent factories (ADR-007 R-1), and a port duplicates ~1.6k lines. It remains
  the reopen path if an unmodified baseline is later required.
- **Allow all differences with `--allow-dirty`.** Rejected: it is the
  "weaken the verifier" failure the covenant names; undeclared drift would pass.
- **Keep a hard-coded exemption list inside the verifier.** Rejected: the
  exemptions must be reviewable in a diff with owners and reasons, not in code
  that changes quietly.
- **Mark dev's differences as project-owned files.** Rejected: a *modified*
  baseline file is not a *project-owned* file; conflating them hides the
  distinction the manifest exists to make.

## Consequences

- `python scripts/verify_baseline.py --strict` **passes on `dev`** because the
  nineteen differences are declared with owners and reasons, not because the
  check was removed.
- Removing an override (restoring a file) now requires deleting its declaration;
  a forgotten declaration fails `--strict`.
- Upgrading the baseline re-opens the declarations (ADR-006 R-5): every override
  must be re-verified against the new blob or re-implemented.
- The debt register entry "19 altered pinned files" changes from **open** to
  **declared / accepted**, with the reopen condition above.

## Reopen conditions

- **R-1** The team ports the implementations into `src/` and restores the
  pinned files — withdraw this ADR, remove the declarations, keep the verifier.
- **R-2** The baseline is upgraded — re-declare against the new manifest.
- **R-3** A declaration is found to describe a change that is not actually
  needed — remove it; stale declarations fail `--strict`.
- **R-4** D8 is re-scoped to an unmodified baseline — R-1 becomes the plan.

## Verification

```text
$ python scripts/verify_baseline.py --strict
layout       : root
pinned files : 213
project-owned: 5 declared
dev overrides: 19 declared, 0 unused
missing      : 0
undeclared   : 0
stale        : 0
baseline-verify: PASS (pinned baseline matches; declared differences only)
```

`test/offline/test_structural_fitness.py` also asserts that every declared
override names an existing file, an owner with a student id, and an ADR, and
that the verifier accepts the tree.
