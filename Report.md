# Project Report (D6)

> **Formatting note.** “Point 12” in the project brief refers to **12-point
> font size**, not a report section. The final report must be more than 15
> pages at 12-point, single-line spacing and must stay within 10,000 words
> (excluding diagrams). This draft supplies the required content; final page
> expansion and typographic formatting remain a team pass.
>
> **Scope note.** Team-wide relative contributions are intentionally not
> computed in this pass. CUI Haoyu's contribution and self-reflection are
> recorded; rows and reflection sections for other members are left blank for
> them to complete.

## 1. Team and contribution

| Student | Student ID | Relative contribution | Sprint 1–5 (hrs/story points) |
|---------|-----------|----------------------|-------------------------------|
| CUI Haoyu | 60760270 | TBD (team weighting later) | TBD |
| (team member 2) | (student ID) | TBD | TBD |
| (team member 3) | (student ID) | TBD | TBD |

> Mean contribution = sum / n. The team will apply the pro-rated weighting from
> the introduction slide after all members have recorded their effort. The
> table above is a shape, not a claim about missing members.

### 1.1 Individual contribution — CUI Haoyu (60760270)

**Owned scope.** REQ-HARD-GUARDRAIL and REQ-TRACEABILITY, plus the ADR-006
integration that makes the pinned TradingAgents 0.7.1 pipeline actually call
both modules. I did not own REQ-CONTEXT-BUDGET, REQ-STRUCTURED-DEBATE or
REQ-TERMINATION-DISCIPLINE; those modules and tests remain with their owners.

**Delivered.**

- `src/guardrail.py` — deterministic, fail-closed gate: `MALFORMED_DECISION`,
  `POSITION_LIMIT`, `SHORT_EXCEEDS_CASH` and `ILLEGAL_RATING`, one audit record
  per rejection, and the legal `Hold` / `REVIEW/HOLD` fallback.
- `src/trace_recorder.py` — `DataSnapshot` / `TraceLink`, critical assertions,
  `traceable`, checked/resolved links, findings, and the renderable trace table.
- `src/integration/` — `GuardedTradingAgentsGraph`, decision adapter with the
  explicit A+B-strict `ExecutionIntent` (`size_pct`, `short_amount`,
  `available_cash`), gate support, trace adapter, guarded CLI entry, and the
  `guardrail_trace_<date>.json` sidecar.
- Verification — 429 deterministic offline tests, 9 full-graph end-to-end
  tests, the full upstream regression suite, ruff/schema checks, and baseline
  verification in both layouts: 213/213 pinned files in the earlier vendor
  layout, then 208 pinned files plus 5 declared project overrides after the
  move to the current root layout.
- D5 — authored and annotated the seven session transcripts (01–07), now
  published on `feature-c` (25,551 lines, 1.53 MB).
- Governance and operations — ADR-006; trace-matrix and structural-constraint
  integration rows; README guarded-pipeline and root-layout guidance;
  AI-use-log entries 007–008; the `pythonpath=.` CI fix and the `feature-c` CI
  trigger.

**Additional local work (not part of `feature-c`).** A Tkinter guarded console
for launching and auditing runs was prototyped locally in `team-app-dev` and is
kept out of the branch by `.gitignore`; it is not claimed as a team-app
deliverable.

**Effort and relative weight.** The Sprint 1–5 hours/story points and the
team-wide relative-contribution weights are deliberately left as `TBD` for the
team pass.

### 1.2 Other members

Other members should add one row each to the table and, where relevant, the
requirement ownership they held. No names or effort numbers are inferred here.
The dev branch shows two module-ownership clusters that should be confirmed by
their owners:

| Area | Evidence in the dev tree | Owner |
|---|---|---|
| Structured debate | `tradingagents/debate/**`, graph/agent wiring, commit `a871245` | feature-f owner (to confirm) |
| Context budget | `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `deepseek_context_adapter.py`, commits `f20c6c9`–`7de8935` | feature-z owner (to confirm) |
| Termination discipline | `src/termination_controller.py` (stub only) | unassigned / to confirm |

## 2. Software engineering process

### 2.1 Baseline and scope

The team worked on the pinned TradingAgents 0.7.1 baseline rather than a
re-imagined application. The baseline commit is
`9fa1196fffbcfd9de5146d2dd2869df84ab99838`; the tree is kept at the repository
root in `feature-c` and in the earlier vendor layout during development. Five
requirements were chosen: context budgeting, structured debate, evidence
traceability, a hard guardrail, and termination discipline. The machine-readable
registry contains the IDs, fit criteria, MoSCoW priorities and source links.

This choice has two consequences. First, every enhancement has to fit an
existing multi-agent graph whose analysts run in parallel and whose final
decision passes through `record_decision`. Second, the project must be explicit
about what is allowed to change: feature-c treats the baseline as pinned and
adds an integration layer, while the dev integrations for structured debate and
context budgeting modify baseline modules directly. The report records that
tension rather than hiding it.

### 2.2 Supervised agent workflow

The coding agent is OpenCode. The governance chain is:

```text
AGENTS.md → Prompt.md → execution plan → human approval → incremental build
          → deterministic tests → human verification gate → integration
```

`Prompt.md` is a launch instruction, not an unattended loop: it requires a plan
covering traceability, interface contracts, scope boundaries, testing strategy
and ordered steps, then a stop for human approval before code. Each stage after
that has a human gate. The D5 transcripts record the interventions as
`APPROVE`, `REJECT`, `REDIRECT`, `AUTHORIZE`, `RESOLVE` and `DEFER`.

The team used the sessions as process evidence, not as a marketing artefact. The
transcripts show the agent proposing work, the student rejecting or redirecting
it, and the next attempt being constrained by the decision. Seven sessions cover
requirements classification, architecture evaluation, plan approval and the
guardrail build, the trace recorder, verification/revision, baseline
integration, and module integration.

### 2.3 Branch and integration workflow

The work was split by feature:

- `feature-c` — project overlay, guardrail/trace integration, root layout,
  baseline verifier and CI.
- `feature-f` — structured debate engine and graph/agent wiring.
- `feature-z` — context-budget core, budgeted model, DeepSeek adapter and tests.
- `dev` — integration branch. The three feature branches were merged with
  explicit merge commits (`4286f27`, `1cedaec`, `a9d23ec`), followed by a CI
  trigger fix (`6aaae7e`) and the transcript publication merge (`a8597af`).

Merging was not treated as a formality. The team ran the offline suite on the
merged tree, ran the upstream suite, checked the guardrail/trace end-to-end
tests, and recorded the two environment-only Windows `PermissionError` cases
that passed when rerun outside the temp directory. The integration exposed the
baseline-drift issue: feature-f and feature-z change 19 pinned files, so the
strict baseline verifier fails on dev even though the runtime tests pass. That
is recorded as debt rather than waved away.

### 2.4 Verification process

Verification is layered:

1. **Structural** — imports, module boundaries, permissions, the pinned-baseline
   verifier, and lint. The root-layout verifier checks 208 pinned files and
   reports the five declared overrides separately.
2. **Regression** — the 429-test deterministic offline suite, 9 full-graph
   end-to-end tests, and the upstream suite. On dev, the upstream run passed
   1,496 tests with six skips and two environment-only failures; the two were
   rerun from a project-writable directory and passed.
3. **Behavioural** — the guardrail/trace invariants and the live prose
   faithfulness/relevancy target. The guardrail and trace layers have negative
   tests; the live prose test is still a stub, which is one of the unmet D4/D7
   items.

A real live run was executed on the dev branch: NVDA on 2026-11-20, four
analysts, DeepSeek quick/deep models, 14 minutes 28 seconds. It produced an
`Underweight` decision that passed the guardrail, a sidecar with 34 evidence
snapshots and 170 resolved links, zero findings and zero capture errors, a
14 KB+ report tree, and a memory-log entry. The trace recorded explicit
no-data evidence for FRED, Reddit and StockTwits instead of pretending those
sources answered. This is the strongest end-to-end evidence that the integration
works on the real graph.

### 2.5 How the process was optimised

The team's optimisations were driven by observed failure modes:

- deterministic offline tests before live calls, so a network failure does not
  erase the ability to test the gate;
- an explicit execution intent at the guarded boundary, so safety does not
  depend on parsing model prose;
- a run-level evidence set (G1) instead of per-thread attribution, because the
  analysts run in parallel;
- a baseline verifier that auto-detects vendor/root layouts, so the layout
  migration cannot silently drift;
- the AI-use-log gate, which forced the style/CI changes to be recorded rather
  than merged invisibly;
- a real `ruff check src test` + `pip check` static-analysis job, replacing the
  original placeholder;
- review memos and a bug diary populated from the integration work rather than
  left as templates.

The process is not finished. The test-approval gate, semantic-evaluation gate,
branch protection, termination implementation and module-boundary reconciliation
remain open; they are listed in `docs/debt-register.md` and in the CI/README
status table.

### 2.6 Work increments in practice

The D5 archive records seven supervised sessions; the commit/CI record groups
them into five increments. The increments are not a claim about calendar-week
boundaries; they are the order in which the work became authoritative.

**Increment 1 — requirements and architecture.** The agent classified the five
requirements, compared architecture candidates and produced the blueprint/ADRs.
The human gate approved the requirement set and the selected architecture. The
outputs are `requirements.yaml`, the schema, the blueprint, ADR-001–005 and the
initial trace matrix. The rejected alternatives were not discarded: the option
ledger and the evaluation table keep them available for a later reconsideration.

**Increment 2 — plan and guardrail.** The agent produced the plan required by
`Prompt.md`, then built the guardrail. The human stopped the work before code and
rejected the current-book sizing policy. The replacement made the execution
intent explicit and fail-closed. The increment produced `src/guardrail.py`, the
decision adapter, the gate tests and the first red/green cycle. The key lesson
was that the safety property lived in the boundary contract, not in a parser.

**Increment 3 — trace recorder.** The agent built snapshots, links, assertions
and findings. Human review rejected per-thread attribution for the parallel
analysts and chose the G1 run-level evidence set. The increment produced
`src/trace_recorder.py`, `src/integration/trace_adapter.py` and the trace tests.
The no-data placeholders were added so an unavailable vendor would be evidence
of absence, not a silent gap.

**Increment 4 — verification and baseline.** The team ran the offline and
full-graph suites, found and fixed the trace defects, moved to the root layout,
added the dual-layout verifier, repaired the CI import and AI-use-log gates, and
recorded the audit-timing caveat. The outputs are the 429-test offline suite,
the 9-test E2E suite, the verifier, the root-layout README/ADR note and
AI-use-log entry 008.

**Increment 5 — module integration and publication.** The feature-f and
feature-z branches were merged into dev, the guardrail/trace path was run on a
real four-analyst analysis, and the D5 transcripts were published. The outputs
are the merge commits, the dev CI run, the live sidecar/report/memory evidence
and the 25,551-line transcript set. The integration also exposed the 19-file
baseline drift and the module-map disagreement, which are recorded as open debt
rather than resolved by assertion.

## 3. Requirement volatility, defect trends and ambiguity resolution

### 3.1 Requirement volatility

The five requirement IDs remained stable across the project. There was no
rename, no removal and no new requirement added at integration time. What
changed was the **interpretation** of existing requirements:

- the guardrail moved from inferred current-book sizing to an explicit
  execution intent;
- the trace moved from per-analyst attribution to a run-level evidence set;
- the baseline moved from a vendor directory to a root-layout repository with
  five declared overrides;
- the report's “Point 12” was clarified as 12-point font size, not a section.

The AI-use log has eight entries spanning requirements, architecture,
guardrail, trace, verification, baseline integration, module integration and
the root-layout/CI changes. That is a requirement-history record, but the team
did not maintain a separate numerical volatility chart. The report treats the
stable IDs plus the recorded reinterpretations as the available evidence.

### 3.2 Ambiguity resolution

| Ambiguity | Options considered | Decision and why | Evidence |
|---|---|---|---|
| How should position size be checked? | Current-book sizing (policy C); parse the trader's prose (A); rating-only with `NOT_EVALUATED` (B-lax); explicit intent (A+B-strict) | Chose explicit intent. Current-book sizing lets a new oversized Buy pass at `size_pct=0`; parse-only makes the verdict depend on wording; rating-only leaves size unchecked. Missing inputs fail closed to `Hold`. | ADR-006 §2; D5 sessions 03/07; `test_integration_decision.py` |
| How should evidence be attributed when analysts run in parallel? | Per-thread/per-analyst G2-lite; run-level G1 | Chose G1. Parallel analysts make per-thread attribution unreliable; a run-level set is honest, deduplicated, and still lets every assertion cite evidence. | ADR-006 §3; `trace_adapter.py`; live run 34 snapshots/170 links |
| Should the baseline be modified or extended? | Vendor copy and edits; root layout with a strict baseline and an integration layer; root layout with feature edits | feature-c uses the root layout with 208 pinned + 5 overrides. The dev feature branches edit 19 pinned files; that is recorded as debt and a reconciliation decision is still required. | README; `verify_baseline.py`; debt register |
| What does “Point 12” mean? | A report section; 12-point font | Clarified by the project owner: it is 12-point font size. The placeholder section was removed and the formatting note added. | This report; project brief |
| What should happen when a data vendor has no key or no data? | Omit the source; fabricate; record evidence of absence | Record evidence of absence as `(no-data)` and keep the run going. The live run demonstrates FRED/Reddit/StockTwits no-data entries. | `trace_adapter.py`; live sidecar |

### 3.3 Defect trends

The bug diary records eight significant defects from the supervised build. They
cluster into three periods:

| Period | Defect class | Representative defect | Outcome |
|---|---|---|---|
| Guardrail/trace build | correctness and evidence integrity | non-dict state raised in the adapter; capture patches double-installed; capture faults were silently dropped; no-data markers matched prose; `build_trace` caught only `TraceError` | fixed with fail-closed normalization, idempotent capture, a capture-error journal, anchored placeholders and a broad trace-failure guard; regression tests added |
| CI and baseline integration | process/CI | `ModuleNotFoundError: src` from the pytest console script; AI-use-log gate blocked a style-only `src/` change | `pythonpath=.` and AI-use-log entry 008; CI passed |
| Dev integration | environment and drift | two Windows temp `PermissionError` cases; 19 altered pinned files | reran the two cases in a project-writable directory (both passed); baseline drift recorded as an open debt, not treated as a test failure |

The trend is not a simple “fewer bugs every sprint” curve. The early bugs were
in the evidence and gate contracts; after those were fixed the failure surface
moved to integration and CI. The number of deterministic tests grew from the
initial guardrail/trace suite to 429 offline tests plus 9 full-graph end-to-end
tests; the dev upstream suite is 1,496 passing tests. The remaining defects are
mostly unbuilt features and missing gates, not regressions in the implemented
paths.

### 3.4 Ambiguity and defect handling

The team's rule is that an ambiguity is resolved in an artefact, not in a chat
message. Policy choices went to ADR-006; invariant changes went to
`invariants.md` and a regression test; a change to the baseline went to the
verifier and README; a process failure went to the bug diary/debt register.
That rule is unevenly applied — the D4 records were templates for most of the
project — but the integration pass made the chain visible.

### 3.5 Test strategy and negative testing

The test strategy is deliberately asymmetric: the deterministic layer is wide,
the live layer is narrow. This is a response to the project's failure modes. A
live model/data run is expensive and non-deterministic; the guardrail and trace
contracts must be exercised without it. The offline suite therefore drives the
real graph with a scripted model and local vendor answers, and the live suite is
reserved for the API-dependent prose and data paths.

The layers are:

- **Unit/contract tests** for the guardrail decision/limits/audit records, the
  adapter's `ExecutionIntent` mapping, trace ids/links and the sidecar shape.
- **Negative tests** for malformed decisions, illegal ratings, position and
  short limits, missing state, capture faults, trace-build failures and
  no-data evidence. The guardrail tests are designed to fail if a trigger is
  removed; the trace tests are designed to fail if evidence is silently lost.
- **Integration tests** for the guarded graph and the CLI entry, including the
  in-place `final_state` mutation that the CLI's report path holds.
- **End-to-end tests** with all analysts, both debates, the trader and the
  portfolio manager. The nine full-graph tests are the bridge between the
  scripted seams and the real LangGraph.
- **Regression** against the upstream tree and the deterministic project suite;
  the dev tree's 1,496 passing tests are the broadest current signal.
- **Structural** checks for the baseline layout, ruff and the module map. The
  module-map check is still a TODO; the dev/team-app mismatch is recorded.

The biggest testing lesson is that a test which only checks the happy path can
make a safety feature look finished while missing the failure that matters. The
fail-closed cases (missing cash, missing intent, config error, trace error) were
added because the human asked what happens when the input is absent or broken.
The live prose test remains a stub; until it exists, the behavioural layer is
only partially evidenced.

## 4. Artifact co-evolution

### 4.1 The chain

The intended chain is:

```text
requirements.yaml
  → ADR + invariants + trace matrix
    → module + tests
      → CI gates + AI-use log
        → report and review records
```

When the guardrail/trace integration was designed, ADR-006 was added, the trace
matrix and structural-constraints rows were updated, `src/integration/**` was
created, the offline and full-graph tests were added, the README guarded-pipeline
section was written, and AI-use-log entries 007–008 were recorded. The report's
`SIZE_DISAGREEMENT` and operator-note behaviour are visible consequences of the
same chain.

### 4.2 Root-layout migration

The migration from a vendor directory to the root layout forced a coordinated
update: the baseline verifier gained dual-layout detection; the five declared
overrides were listed; README setup and test commands changed; ADR-006 gained a
root-layout note; the CI install step gained a vendor/root conditional; the
`pythonpath=.` fix made the console-script test job importable; and AI-use-log
entry 008 recorded the change. This is the clearest example of artifacts moving
together rather than code alone.

### 4.3 Dev integration

The feature-f/feature-z integration added the structured-debate and
context-budget implementations, their tests, and stage-5.2 acceptance
documents. The merge commits are explicit and the dev CI was made to run. The
co-evolution is incomplete in two respects:

1. the runtime modules live under `tradingagents/` while the feature-c element
   map points at `src/context_assembler.py` and `src/structured_debater.py`;
2. 19 pinned files are modified on dev, so the strict baseline verifier does not
   pass there.

Both are recorded in the debt register. They are not papered over by editing the
verifier or by claiming the dev tree is byte-identical to the baseline.

### 4.4 Co-evolution controls and gaps

Controls that worked:

- the baseline verifier;
- the AI-use-log gate (it blocked a real style-only change until entry 008 was
  added);
- the trace matrix and invariant register when a new contract was added;
- the D5 transcripts as a record of why a change was accepted or rejected.

Controls that are still weak:

- D4 review/debt/bug records were templates until this pass;
- branch protection is absent;
- the test-approval and semantic-evaluation gates are not implemented;
- the module map and the dev implementation locations disagree.

### 4.5 Authority boundaries and decision rights

The project distinguishes **advisory** output from **authoritative** decisions.
The coding agent's suggestions, the model's report prose and the GUI's operator
notes are advisory. The architecture blueprint, the project covenant, the ADRs,
the frozen guardrail and the CI gates are authoritative. A human gate is the
only thing that turns an agent proposal into a committed change.

| Decision | Authority | Evidence |
|---|---|---|
| Requirement meaning / fit criterion | Requirement registry + human approval | D1, D5 session 01 |
| Architecture choice and rejected alternatives | Blueprint + ADR + human approval | D2, ADR-001–006 |
| Safety-critical change | ADR + human approval; guardrail remains frozen | `AGENTS.md`, `Prompt.md`, ADR-006 |
| Pinned-baseline change | ADR or declared project override | README, verifier, debt register |
| Guardrail verdict | deterministic `src/guardrail.py`, never the model | ADR-006, tests |
| Trace evidence | recorder output + sidecar; never a model narrative | trace adapter, live sidecar |
| Report contribution/formatting | student/team, not the agent | this report |

The authority boundary is also a limitation. The guardrail checks the declared
execution intent; it cannot prove that the execution layer will obey that
intent. The operator note for a rating/intent direction mismatch is a reading
aid, not a new authority. Making that a hard rule would require a policy
decision and an ADR, not a silent code change.

## 5. Human oversight that caught what the agent did not

The project's central claim is that the agent was supervised, not autonomous.
The following interventions are the concrete evidence.

| Intervention | What the agent proposed | What the human caught | Result |
|---|---|---|---|
| Guardrail policy | Current-book sizing (policy C) | A ticker with no position yields `size_pct=0`, so a new oversized Buy passes; a risk-reducing Sell can be rejected | Replaced with explicit `ExecutionIntent`; missing inputs fail closed |
| Trace attribution | Per-thread/per-analyst G2-lite | Parallel analysts make per-thread attribution unreliable | Replaced with the G1 run-level evidence set |
| False implementation claim | A report said `gate_support` imported `json` | It did not; the claim was corrected and the AST ban was kept | Prevented a false architecture statement |
| Trace defects | Capture/wrapper code looked correct | Human review and negative tests found double-install, silent observer faults, unanchored no-data matching, and an over-narrow `TraceError` catch | Fixed with idempotent capture, a capture-error journal, anchored placeholders, and a broad trace-failure guard |
| Audit timing | A 213/213 baseline claim | `--help` had written 87 `__pycache__` files under the vendor tree; the claim was made before the sequencing issue was visible | Cleaned, reran, PASS; the sequencing caveat was recorded |
| CI import | “Tests pass locally” | GitHub Actions used the `pytest` console script and could not import `src` | `pythonpath=.`; CI passed |
| AI-use-log gate | Style-only `src/` change with no log entry | The gate correctly blocked it | Entry 008 added; the gate is demonstrably real |
| Report metrics | A report said 432 collected tests | The actual collected count was 431 | Corrected; the lesson is to quote the command output, not a recollection |
| Point 12 | Treated as an unknown report section | The brief's “Point 12” means 12-point font size | Placeholder removed; formatting note added |

> **CUI Haoyu note:** I was the human in the loop for the policy-C, G2-lite,
> trace-defect, CI and report-metric interventions. The guardrail and trace
> modules are mine; the context-budget/structured-debate code is the other
> owners' work and is described here as integration evidence, not as my claim.

The pattern is consistent: the agent was good at producing a plausible first
implementation and weak at noticing the boundary conditions that made it unsafe
or unverifiable. Human review supplied the adversarial question — what happens
when the input is missing, the thread is parallel, the data source has no key,
or the test environment differs? — and the deterministic tests made the answer
permanent.

## 6. Reflections

### 6.1 CUI Haoyu (60760270)

My main contribution was the guardrail/trace layer and its integration into the
pinned graph. The most important thing I learned is that a safety feature is not
a function that returns a boolean; it is a contract about what happens when the
input is absent, malformed, parallel, or late. The first design I accepted —
current-book sizing — looked reasonable until the adversarial case showed that
a new oversized Buy would pass at zero position. Rejecting it in favour of an
explicit execution intent changed the module boundary, the CLI, the tests and
the report. The same happened with the trace: per-thread attribution was
attractive until I understood that the analysts run concurrently. The run-level
G1 set was less precise but more honest.

I also learned how easily an agent's confident prose can hide a defect. The
trace capture looked correct in review; the negative tests found the
double-install, the swallowed observer fault, the unanchored no-data marker and
the over-narrow exception catch. The audit also caught me: a baseline claim was
made before the `__pycache__` sequencing issue was cleaned up, and a test count
was quoted from memory rather than from the command. Those are process failures,
not just code failures.

My weakness was sequencing. I tended to push the next integration before the
D4 review/debt/bug records were current, which made the evidence chain less
useful than it should have been. Next time I would keep the review memo, debt
register and bug diary in the same commit as the change, and I would make the
module-boundary reconciliation a condition of merging the dev features rather
than a follow-up debt. I would also keep the report's formatting and page
requirements visible from the start; “Point 12” is a font size, not a section,
and a last-minute clarification should not be necessary.

### 6.2 Other members

> Each other member should add a 300–500-word reflection here with their name
> and student ID. Do not infer or write another member's reflection.

#### (Team member 2 — name and student ID)

(Reflection to be completed by the member.)

#### (Team member 3 — name and student ID)

(Reflection to be completed by the member.)

## 7. Verification evidence summary

| Evidence | Result | Where |
|---|---|---|
| Deterministic offline suite (feature-c) | 429 passed, 2 deselected | `pytest test/offline -m offline -q` |
| Full-graph end-to-end | 9 passed | `test/offline/test_integration_end_to_end.py` |
| Dev upstream suite | 1,496 passed, 6 skipped, 2 environment-only failures; both rerun and passed outside Windows Temp | dev workspace |
| Current team-app upstream collection | 1,414 tests collected | `pytest tests --collect-only -q` |
| Baseline, vendor layout | 213/213 pinned files | earlier verifier run |
| Baseline, root layout | 208 pinned + 5 declared overrides; PASS | `scripts/verify_baseline.py --strict` |
| Live guarded run | NVDA 2026-11-20, 14m28s, `Underweight`, guardrail PASS, 34 snapshots, 170/170 links, 0 findings, 0 capture errors | dev live artifacts |
| Feature-c CI | success | GitHub Actions |
| Dev CI after the feature merges | success | GitHub Actions |
| Static analysis (current) | `ruff check src test` PASS; `pip check` compatible (97 packages) | local venv |

Known unmet verification items: termination has no passing test; the live prose
faithfulness/relevancy test is a stub; the semantic-evaluation gate and branch
protection are not implemented.

## 8. Formatting and pending team inputs

- **Formatting:** final report at 12-point font, single-line spacing, more than
  15 pages; maximum 10,000 words excluding diagrams. This draft is a
  content-complete skeleton, not a typeset submission.
- **Team relative contributions:** intentionally not computed. Add the other
  members' rows, Sprint 1–5 effort and the pro-rated weights in the team pass.
- **Other members' reflections:** add one 300–500-word section per member with
  name and student ID.
- **Point 12:** 12-point font size; there is no Section 12.
- **Remaining engineering gaps:** termination implementation, baseline/module
  reconciliation, test-approval gate, semantic-evaluation gate, branch
  protection, and the 19-file baseline drift on dev.

## Appendix A — Work phases and human gates

| Phase | Work | Artifacts / evidence | Human gate |
|---|---|---|---|
| 0. Baseline | Pin TradingAgents 0.7.1, establish the vendor/root layout and the five requirements | `PINNED_COMMIT.txt`, `BASELINE_MANIFEST.txt`, `docs/req/requirements.yaml` | Approve the baseline and scope |
| 1. Requirements | Classify functional, invariant, quality and performance requirements; define fit criteria | D1 registry + schema; transcript 01 | Approve the requirement set |
| 2. Architecture | Evaluate candidates, choose the layered/integration design, write ADRs and invariants | D2 blueprint, ADR-001–006, evaluation table, trace matrix | Approve the architecture and the rejected options |
| 3. Plan | Produce traceability, interface contracts, scope, test strategy and ordered steps | `Prompt.md` execution plan; transcript 03 | Stop before code |
| 4. Guardrail build | Build the deterministic gate, audit record, Hold fallback and negative tests | `src/guardrail.py`, 429-test offline suite | Approve each trigger and fail-closed behaviour |
| 5. Trace build | Build DataSnapshot/TraceLink, assertions, findings and the sidecar | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | Review evidence coverage and G1 scope |
| 6. Verification/revision | Run the offline, full-graph and upstream suites; revise the architecture from evidence | Transcript 05; bug diary; D4 records | Accept or reject the verification evidence |
| 7. Baseline integration | Move to the root layout, add the dual-layout verifier, repair CI | README, verifier, CI runs, AI-use log 008 | Approve the migration and the override list |
| 8. Module integration | Merge feature-c/f/z into dev; publish D5; reconcile the module map | Merge commits, dev CI, live run, transcript 07 | Approve the integration and record the debt |

The phases are not a waterfall: the guardrail and trace work forced
revisions to the architecture, and the dev merges forced a second look at the
baseline and module map. The human gate is the point where a change becomes
authoritative; the agent's output before that point is advisory.

## Appendix B — Requirement-to-evidence map

| Requirement | Type / priority | Implementation | Primary evidence | Status |
|---|---|---|---|---|
| REQ-CONTEXT-BUDGET | performance / Must | dev: `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `deepseek_context_adapter.py`; team-app: `src/context_assembler.py` stub | `tests/test_context_budget_core.py`, `tests/test_budget_agent_integration.py` (dev) | Dev-complete; not yet ported to team-app |
| REQ-STRUCTURED-DEBATE | quality / Should | dev: `tradingagents/debate/**` and graph/agent wiring; team-app: `src/structured_debater.py` stub | `tests/test_debate_opening.py`, `tests/test_structured_agents.py` (dev) | Dev-complete; not yet ported to team-app |
| REQ-TRACEABILITY | functional / Must | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | `test/offline/test_traceability.py`, `test/offline/test_integration_trace.py`, E2E | Complete |
| REQ-HARD-GUARDRAIL | invariant / Must | `src/guardrail.py`, `src/integration/decision_adapter.py`, `gate_support.py`, `governed_graph.py` | `test/offline/test_guardrail.py`, decision/gate/E2E tests | Complete |
| REQ-TERMINATION-DISCIPLINE | performance / Should | `src/termination_controller.py` (constant-only stub) | `test/offline/test_termination.py` (`NotImplementedError`) | Missing |

D1 itself validates: 5 requirements, schema PASS, all with fit criterion,
machine-checkable criterion, priority, source, statement and tradeoff. The
registry uses functional/invariant/quality/performance types; there is no
cost/governance/security-typed entry, which is a minor coverage note rather than
a schema failure.

## Appendix C — Commit and branch map

| Ref | Purpose | Evidence |
|---|---|---|
| `644676f` | Pinned TradingAgents 0.7.1 root baseline | main/dev/feature-f/feature-z base |
| `b3d2e1c` | Initial CS5351 feature-c overlay | D1–D5 content, integration package |
| `f27790b` | Run the blocking gates on feature-c | CI trigger |
| `1f32c0a` | Root-layout ruff fixes and `pythonpath=.` | CI import fix |
| `1bce89f` | AI-use-log entry 008 | CI log gate fix |
| `1a76cae` | Stop publishing transcripts (superseded by `ebae615`) | local-only history |
| `ebae615` | Publish seven D5 transcripts | feature-c D5 |
| `a871245` | Structured debate (feature-f) | `tradingagents/debate/**` |
| `f20c6c9`, `3313ad0`, `7de8935` | Context-budget core/integration (feature-z) | `tradingagents/graph/context_budget.py` |
| `4286f27` | Merge feature-c into dev | dev integration |
| `1cedaec` | Merge feature-f into dev | dev integration |
| `a9d23ec` | Merge feature-z into dev | dev integration |
| `6aaae7e` | Run CI on dev | dev CI trigger |
| `a8597af` | Merge transcript publication into dev | D5 in dev |

CI evidence: feature-c run `45583328014` (success), dev run `45583480042`
(success); earlier feature-c run `45518942342` and dev run `45581334303` also
passed.

## Appendix D — D5 transcript index

| Transcript | Stage | Focus | Representative human intervention |
|---|---|---|---|
| 01 | Requirements classification | Split functional, invariant, quality and performance requirements; define fit criteria | Approve/redirect the requirement set |
| 02 | Architecture evaluation | Compare candidate architectures; choose the layered/integration design | Reject alternatives; approve the selected design |
| 03 | Plan approval and guardrail build | Plan before code; build the gate; test-first red state | Stop for approval; reject policy C |
| 04 | Trace recorder build | Data snapshots, evidence links, findings | Review evidence scope; reject weak attribution |
| 05 | Verification and revision | Run tests; revise architecture from evidence | Accept/reject test evidence |
| 06 | Baseline integration | Install the pinned baseline; verify layout | Approve the baseline and override list |
| 07 | Module integration | Wire guardrail/trace into the real pipeline | Resolve scope/evidence issues; approve |

Each transcript is annotated at the intervention point with the reason. The
transcripts are long (25,551 lines total) because they include the raw tool and
model output, not a summary; the annotation is what makes the process auditable.

## Appendix E — Defect log summary

| ID | Class | Symptom | Root cause | Fix | Invariant |
|---|---|---|---|---|---|
| Bug-001 | correctness | Adapter raised on non-dict final state | Assumed mapping | Normalize to `{}`; test | Gate must not raise |
| Bug-002 | evidence integrity | Capture patches double-installed | Non-idempotent `with` | Idempotent enter/finish | Trace completeness |
| Bug-003 | observability | Capture faults silently dropped | Swallowed exceptions | `capture_errors` journal | Trace completeness |
| Bug-004 | evidence integrity | No-data marker matched prose | Unanchored substring | Anchored placeholder | Trace completeness |
| Bug-005 | resilience | Trace build only caught `TraceError` | Narrow catch | Catch `Exception`; `trace_error` | Rating integrity |
| Bug-006 | security | Guardrail config error raised | No fail-closed translation | `config_error_result` | Zero escape |
| Bug-007 | CI | `ModuleNotFoundError: src` | Console-script path | `pythonpath=.` | None |
| Bug-008 | process | AI-use-log gate blocked style-only change | Missing log entry | Entry 008 | None |

The full symptom/reproduction/root-cause/fix text is in `docs/bug-diary.md`.
The trend is from gate/evidence defects toward integration/CI defects, not a
monotone decline; the remaining gaps are mostly unbuilt features and gates.

## Appendix F — Verification commands and results

| Command / evidence | Result |
|---|---|
| `pytest test/offline -m offline -q` | 429 passed, 2 deselected |
| `pytest test/offline/test_integration_end_to_end.py` | 9 passed |
| `pytest tests -q -m "not integration"` on dev | 1,496 passed, 6 skipped; 2 environment-only failures, both pass when rerun in a project-writable directory |
| `pytest tests --collect-only -q` on team-app | 1,414 tests collected |
| `scripts/verify_baseline.py --strict` | PASS: 208 pinned + 5 declared overrides in root layout; earlier 213/213 vendor |
| `ruff check src test` | PASS |
| `ruff check gui` (local GUI, not team-app) | PASS |
| `pip check` / `uv pip check` | 97 packages compatible |
| Live run | NVDA 2026-11-20, 14m28s, Underweight, PASS, 34 snapshots, 170/170 links, 0 findings |
| Feature-c CI | success |
| Dev CI | success |

The live run is not a mock: it calls Yahoo, SEC EDGAR, news/macro/prediction
tools and DeepSeek, and writes the sidecar/report/memory chain. Its trace
records `fred (no-data)`, `reddit (no-data)` and `stocktwits (no-data)` as
explicit evidence of absence.

## Appendix G — Open gaps and suggested action

| Gap | Impact | Suggested action | Owner |
|---|---|---|---|
| Termination not implemented | D8/D4 incomplete | Implement repeat/stall/budget termination and a failing-then-passing test | owner to confirm |
| Context budget/structured debate not in team-app | D8 incomplete if team-app is the submission | Port dev modules into the declared `src/` boundaries or merge dev as the submission | module owners |
| 19 pinned files altered on dev | Baseline verifier fails on dev | Approve a controlled override ADR or port into `src/` and restore pinned files | module owners + CUI |
| Test-approval gate / semantic-evaluation gate / branch protection | D7 incomplete | Wire the gates and configure required checks + human review | team lead |
| Live prose semantic test is a stub | D4 behavioural layer incomplete | Add DeepEval or a fixed deterministic replay with a documented threshold | owner to confirm |
| Other members' contributions/reflections | D6 incomplete | Each member adds their row, effort and 300–500-word reflection | each member |
| Team relative weights | D6 incomplete by instruction | Apply the agreed effort measure and pro-rate | team |

> **CUI Haoyu note:** I can own the baseline reconciliation and the guardrail/
> trace evidence; the termination implementation, the module ports and the
> CI/branch-protection settings need their owners or a team decision.

## Appendix H — D1–D9 deliverable map

| Deliverable | Status in `team-app` | Evidence / remaining gap |
|---|---|---|
| D1 Requirements | Complete at file/schema level | 5 requirements with fit criteria, priorities, sources; schema PASS; AI-use log 8 entries. No cost/governance/security-typed entry (minor). |
| D2 Architecture | Files complete; populated with one open ADR | Blueprint, ADR-001–006, invariants, trace matrix, memory, permission, runtime catalog, evaluation table/logbook, risk list and option ledger are populated; ADR-001/002 still need owner confirmation, and ADR-005 remains Proposed because termination is unimplemented. The layered-context/reinjection section is in ADR-001. |
| D3 Governance | Files complete; populated | `AGENTS.md` integration contracts, structural constraints, permissions, rules/covenant and the MCP manifest are populated. The module-to-element fitness check is still a follow-up, not a claimed gate. |
| D4 Verification | Populated from the integration | Review memos, debt register, bug diary and test-to-requirement map added. Live prose semantic test is a stub; semantic gate absent. |
| D5 Transcripts | Complete | Seven annotated sessions + README; published on feature-c and merged to dev. |
| D6 Report | This draft | Own contribution and reflection recorded; team contribution/weights/other reflections left blank by instruction; Point 12 is 12-point font, not a section. |
| D7 GitHub/CI | Partial | Real repo and commit history; schema/tests/AI-use-log/ruff+pip-check jobs exist. Test-approval, semantic-evaluation and branch protection still missing; README now documents the design/status. |
| D8 Source/tests | Partial | Guardrail/trace/integration complete; context budget and structured debate complete on dev but not on team-app; termination still missing in both. |
| D9 Prompt | Complete | `Prompt.md` requires plan-first, human approval, staged build and gates. |

## Appendix I — Governance and verification checklist

| Check | How it is satisfied | Status |
|---|---|---|
| Requirements are machine-readable and schema-valid | YAML registry + JSON schema + CI schema gate | Pass |
| Every fit criterion has a test | Guardrail/trace rows mapped in verification-constraints; context/debate dev tests; termination missing | Partial |
| Every invariant has a negative test | guardrail trigger tests; trace completeness tests | Guardrail/trace pass; termination n/a |
| Every test references a requirement/invariant | Trace/guardrail test docstrings and names | Pass for owned modules |
| Full prior suite runs with zero regressions | 429 offline + 9 E2E + upstream; dev 1,496 | Pass for implemented paths |
| New code/prompts update the AI-use log | CI gate + entry 008 | Pass (gate is real) |
| Review memo per integration unit | D4 review memos for the feature-c/dev units | Pass for reviewed units |
| Debt and bug records are current | D4 debt register/bug diary populated in this pass | Pass (ongoing) |
| Human approval before code | `Prompt.md`, D5 transcripts, merge/review gates | Pass |
| Semantic evaluation | Live prose stub / missing CI gate | Fail/partial |
| Branch protection | GitHub branches unprotected | Fail |

## Appendix J — Limitations and next actions

The report's strongest evidence is the actual live run and the deterministic
guardrail/trace tests; its weakest evidence is the semantic layer and the
team-process records. The following limitations are material:

1. **Two trees, not one.** `feature-c` is the clean integration branch;
   `dev` contains the complete structured-debate and context-budget work. The
   report describes dev as the integration source, but the team must decide
   which branch is the submission and reconcile the module boundaries.
2. **Baseline drift.** The dev features alter 19 pinned files. The strict
   verifier fails on dev. A controlled override ADR or a port into `src/` is a
   prerequisite for claiming baseline compliance.
3. **Termination is not implemented.** The requirement has an ADR and a
   placeholder, but no controller and no passing test. This is a real D8 gap,
   not a documentation formatting issue.
4. **The semantic gate is not wired.** The live prose test and the fixed
   evaluation replay are still missing, so the behavioural layer is only
   partially evidenced.
5. **Branch protection and two gates are missing.** The repository is public and
   the CI jobs that exist are real, but the six-gate design is not yet fully
   enforced.
6. **D6 team data is pending.** The other members' names, student IDs, effort,
   relative weights and 300–500-word reflections are intentionally blank. The
   final report must add them and format at 12-point single spacing to exceed
   15 pages.

The next actions are therefore concrete: implement termination; choose and
reconcile the submission tree; close the baseline drift with an ADR or a port;
wire the semantic/test-approval gates and branch protection; add the live prose
test; and complete the team contribution/reflection sections. None of these
should be hidden behind a claim that the project is already complete.

> **CUI Haoyu note:** for my part, the guardrail/trace evidence, the D5
> transcripts and the baseline verifier are ready. The remaining items above
> are either other owners' modules or team-level decisions; I have marked them
> instead of inventing their outcomes.
