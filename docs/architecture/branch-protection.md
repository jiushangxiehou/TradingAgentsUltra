# Branch Protection (D7)

> Branch protection is a GitHub repository setting, not a file. This document is
> the policy the settings must implement, and the record of what is still a
> manual step. Reviewed 2026-11-25.

## Required checks on `dev` (and `main`)

Every job in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml),
plus the aggregate `All blocking gates` job:

| Check | Gate | What it proves |
|---|---|---|
| Gate 3 — schema | 3 | `requirements.yaml` still validates against its schema |
| Gate 2 — static analysis | 2 | ruff, mypy (ADR-009), `pip check` |
| Gate 2 — safety paths | 2 | contract, security, API surface, permissions |
| ADR-008 — baseline integrity | — | no undeclared drift from the pinned baseline |
| Gate 1 — test approval | 1 | every changed test is approved in the base manifest |
| Gate 5 — offline suite | 5 | the deterministic suite passes |
| Gate 5 — upstream regression | 5 | the pinned suite passes (`-m "not integration"`) |
| Gate 4 — semantic evaluation | 4 | fixed eval set, prompt constraints, model baseline |
| Gate 6 — AI-use log | 6 | code/prompt change logged |
| All blocking gates | — | aggregate; use this as the single required check |

## Required review

- **`docs/architecture/`**, **`docs/code-governance/`**, **`.opencode/`**,
  **`.agent/`** — one human review; these are the governance files.
- **`src/guardrail.py`**, **`src/trace_recorder.py`**, **`src/integration/`** —
  one human review **and** a linked ADR (the safety-critical rule in
  `.agent/rules.md`).
- **`scripts/baseline-overrides.json`** — one human review; declaring a baseline
  difference is a decision, not a convenience.
- **`docs/test-approval.yaml`** — one human review; this is the compensating
  control for the approval gate's bootstrap path.
- **`docs/ai-use-log.yaml`** — one human review; the log is evidence.

`.github/CODEOWNERS` requests these reviewers automatically.

## Manual checklist — what to tick in GitHub

Repository → **Settings** → **Branches** → *Add branch protection rule*
(or *Add ruleset* for the newer UI). Do it once for `dev` and once for
`main`.

**1. Target the branch**

- [ ] Branch name pattern: `dev` (repeat for `main`)
- [ ] (Optional) Apply the same rule to tags: `v*`

**2. Protect the branch**

- [ ] Require a pull request before merging
- [ ] Required approvals: **1**
- [ ] Dismiss stale pull request approvals when new commits are pushed
- [ ] Require review from **Code Owners** (uses `.github/CODEOWNERS`)
- [ ] Require approval of the most recent reviewable push
- [ ] Require conversation resolution before merging
- [ ] (Optional) Require linear history
- [ ] (Optional) Require signed commits

**3. Require status checks to pass**

- [ ] Require status checks to pass before merging
- [ ] Require branches to be up to date before merging
- [ ] Add **every** check below (the names are the `name:` fields of the jobs
      in `.github/workflows/ci.yml`; GitHub shows them after one push):
  - [ ] `Gate 3 — schema`
  - [ ] `Gate 2 — static analysis`
  - [ ] `Gate 2 — safety paths`
  - [ ] `ADR-008 — baseline integrity`
  - [ ] `Gate 1 — test approval`
  - [ ] `Gate 5 — offline suite`
  - [ ] `Gate 5 — upstream regression`
  - [ ] `Gate 4 — semantic evaluation`
  - [ ] `Gate 6 — AI-use log`
  - [ ] `All blocking gates`  ← the aggregate; this is the one to require if
        you only require one

**4. Access**

- [ ] Do not allow bypassing the above settings
- [ ] Restrict who can push to matching branches (or at least: no direct pushes)

**5. Rules that apply to everyone**

- [ ] Block force pushes
- [ ] Restrict deletions

**6. After the first green CI run**

- [ ] Open a trivial PR and confirm the required checks appear and a missing
      review blocks the merge
- [ ] Confirm `CODEOWNERS` requests the reviewer on `docs/architecture/`,
      `docs/test-approval.yaml`, `docs/ai-use-log.yaml` and
      `scripts/baseline-overrides.json`

> The exact status-check names depend on the job `name:` fields; if a name is
> edited in the workflow, update this list and the required checks together.

## Status (honest)

| Item | State |
|---|---|
| Workflow implements the nine jobs | **Done** (this repository) |
| CODEOWNERS declares the review owners | **Done** (owner handle only; add the other members' handles) |
| Required checks configured on `dev`/`main` | **Manual step** — GitHub Settings → Branches → protect `dev`, `main`; require the aggregate check and one approval |
| "Dismiss stale approvals", "require review from code owners" | **Manual step** in the same settings |
| Force-push / deletion protection | **Manual step** |

The repository cannot encode the settings itself. The team lead must apply them
once on GitHub; until then, the *workflow* is real but a merge could bypass it.
That limitation is recorded in the debt register and the report rather than
implied to be done.