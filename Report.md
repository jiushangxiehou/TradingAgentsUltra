# Project Report (D6)

> **Formatting note.** “Point 12” in the project brief refers to **12-point
> font size**, not a report section. The final report must be more than 15
> pages at 12-point, single-line spacing and must stay within 10,000 words
> (excluding diagrams). This draft supplies the required content; final page
> expansion and typographic formatting remain a team pass.
>
> **Team note.** The submission tree is `dev` (ADR-007). All three members,
> their student IDs, their story-point areas, their owned requirements and their
> reflections are recorded below. The team agreed an **equal three-way split**
> (mean contribution = 1.0, so each member's relative weight is 1.00) on
> 2026-11-25; the evidence column is the record behind that decision.

## 1. Team and contribution

| Student | Student ID | Story points / owned requirement(s) | Contribution evidence | Relative contribution |
|---|---|---|---|---|
| CUI Haoyu | 60760270 | Safety boundary (REQ-HARD-GUARDRAIL) + evidence-chain traceability (REQ-TRACEABILITY); ADR-006 integration and the D7/D8 governance round | `src/guardrail.py`, `src/trace_recorder.py`, `src/integration/**`, ADR-003/004/006/009, seven D5 transcripts, gates | **1.00** |
| ZhuXuan | 60377218 | Context retrieval and budget (REQ-CONTEXT-BUDGET) | `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `deepseek_context_adapter.py`, six pinned call sites, stage-5.2 reports, acceptance report | **1.00** |
| Fan Hao | 60835652 | Structured debate (REQ-STRUCTURED-DEBATE) and termination discipline (REQ-TERMINATION-DISCIPLINE) | `tradingagents/debate/**`, eleven pinned call sites, debate tests, contribution report and session record; termination requirement ownership (integration wiring: CUI Haoyu) | **1.00** |

> **How the weight was computed.** Three equal shares, agreed by the team on
> 2026-11-25: sum = 3, mean = 1.0, each weight = 1.00. The course example
> pro-rates by effort; this team's agreed effort measure is the story-point
> area above, split three ways, because the three areas are the project's three
> requirement clusters (safety/trace, context/budget, debate/termination) and
> each member led one. The evidence column is the record behind the allocation:
> every artifact named there is in the repository and attributable in
> `docs/ai-use-log.yaml` and the commit history.
>
> **Termination discipline belongs to Fan Hao's story points** (requirement
> ownership: the repeat/stall/budget policy and the debate termination policy).
> The analyst-loop integration and the controller-test wiring were implemented by
> CUI Haoyu and are recorded in `docs/ai-use-log.yaml` entry 010; that is an
> integration contribution, not a change of requirement ownership.

### 1.1 Individual contribution — CUI Haoyu (60760270)

**Owned scope.** REQ-HARD-GUARDRAIL and REQ-TRACEABILITY, plus the ADR-006
integration that makes the pinned TradingAgents 0.7.1 pipeline actually call
both modules. I did not own REQ-CONTEXT-BUDGET or REQ-STRUCTURED-DEBATE; those
modules remain with their owners. I added the termination-controller
integration to close the D8 gap after the dev merge (ADR-005).

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
- Termination discipline — `tradingagents/graph/termination.py` (repeat/max
  tool-round check and stateful `TerminationController`) plus the
  `src/termination_controller.py` facade; the analyst loop wraps up on a
  repeated tool-call round or the round cap; 7 offline cases cover repeat,
  distinct, cap, budget, stall, reset and invalid thresholds.
- Verification — 441 deterministic offline tests (429 core + 12
  termination/budget cases), 9 full-graph end-to-end tests, the full upstream
  regression suite, ruff/schema checks, and baseline verification in both
  layouts: 213/213 pinned files in the earlier vendor layout, and 213 pinned
  files with 24 declared differences (5 project-owned + 19 dev overrides) after
  the move to the root layout (ADR-008).
- D5 — authored and annotated the seven session transcripts (01–07), published
  on `feature-c`, merged to `dev`, and consolidated into
  `transcripts/D5-team-session-transcripts.md` (25,551 lines of Part A, 1.53 MB).
- Governance and operations — ADR-006; trace-matrix and structural-constraint
  integration rows; README guarded-pipeline and root-layout guidance;
  AI-use-log entries 007–008; the `pythonpath=.` CI fix and the `feature-c` CI
  trigger.

**Additional local work (not part of the graded feature branches).** A Tkinter guarded console
for launching and auditing runs was prototyped locally in `team-app-dev` and is
kept out of the branch by `.gitignore`; it is not claimed as a team-app
deliverable.

**Effort and relative weight.** The Sprint 1–5 hours/story points and the
team-wide relative-contribution weights are deliberately left as `TBD` for the
team pass.

### 1.2 Individual contribution — ZhuXuan (60377218)

**Owned scope.** REQ-CONTEXT-BUDGET (ADR-001), from the News Analyst pilot to
the all-agent budget boundary.

**Delivered.** The budget core (`tradingagents/graph/context_budget.py`:
layering, tool-call/result pairing by id, explicit future-availability
filtering, one deterministic compaction pass, at most two counts, a one-time
send permit bound to the counted bytes), the graph-agent boundary
(`budgeted_model.py`), the CityU local-estimate transport
(`deepseek_context_adapter.py`), and the six pinned call-site integrations
(`agents/analysts/turn.py`, `sentiment_analyst.py`, `post_screen.py`,
`agents/structured.py`, `memory/reflection.py`, `llm_clients/factory.py`) plus
`graph/trading_graph.py` and `default_config.py`. The acceptance documents are
`docs/stage-5.2-phase-1..4-*.md` and `docs/req-context-budget-acceptance.md`.

**Evidence.** Commits `f20c6c9` (core), `3313ad0` (agent integration),
`7de8935` (CityU estimate and final delivery); 40 core + 13 integration + 5
offline configuration tests; the paired synthetic test retains 2/2 facts and
5/5 standing constraints while the mock request falls from 17,155 to 10,266
byte-units.

**Scope limits recorded by the owner.** The CityU counter is a local estimate
(`count_unit=local_token_estimate`, `counter_exact=false`); real provider token
counts and real model-output faithfulness were not verified. The raw session
export for D5 is not in the repository; the supervision summary is supplied
instead.

### 1.3 Individual contribution — Fan Hao (60835652)

**Owned scope.** REQ-STRUCTURED-DEBATE (ADR-002) and REQ-TERMINATION-DISCIPLINE
(policy ownership: the repeat threshold, the budget/stall signals and the
max-round cap). The analyst-loop wiring and the controller integration for the
termination requirement were implemented by CUI Haoyu (ADR-005, AI-use log entry
010); the requirement ownership and its story points are Fan Hao's.

**Delivered.** The typed debate protocol (`tradingagents/debate/schemas.py`:
`DebateTurn`, `DebateClaim`, `DebateRebuttal`, `TurnAudit`,
`TerminationDecision`), the stable evidence catalog
(`tradingagents/debate/evidence.py`), and the engine
(`tradingagents/debate/engine.py`: binding, backend validation of claims,
evidence ids and rebuttal targets, deterministic claim ids, metrics, and the
termination policy with shadow mode). The implementation is wired into the five
debate nodes, `agents/state.py`, `graph/conditional_logic.py` and
`graph/propagation.py`, with the five `debate_*` configuration keys.

**Evidence.** Commit `a871245`; `tests/test_debate_opening.py` (5) and
`tests/test_structured_agents.py` (35); the owner's contribution report and
session record (`FANHAO/`, integrated into this report and the D5 document).

**Scope limits recorded by the owner.** The convergence check is deterministic
(no new claims, stable stances, no position change), not semantic; shadow mode
is the default so the baseline round limit is preserved until the policy is
enabled.

### 1.4 Contribution evidence map

| Area | Evidence in the dev tree | Owner |
|---|---|---|
| Structured debate | `tradingagents/debate/**`, graph/agent wiring, commit `a871245` | Fan Hao (60835652) |
| Context budget | `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `deepseek_context_adapter.py`, commits `f20c6c9`–`7de8935` | ZhuXuan (60377218) |
| Guardrail / trace / integration | `src/guardrail.py`, `src/trace_recorder.py`, `src/integration/**`, commits `b3d2e1c`–`a758f8f` | CUI Haoyu (60760270) |
| Termination discipline | `tradingagents/graph/termination.py`, `src/termination_controller.py`, analyst-loop wiring | Fan Hao (60835652) — requirement; CUI Haoyu (60760270) — integration |

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

1. **Structural** — imports, module boundaries, permissions, the element map,
   the pinned-baseline verifier, lint and the type checker. The root-layout
   verifier checks 213 pinned files and reports the 24 declared differences
   (5 project-owned files + 19 owned dev overrides, ADR-008) separately; the
   element-map fitness test is a real test, not a TODO (ADR-007); mypy checks
   the project-owned modules (ADR-009).
2. **Regression** — the deterministic offline suite, 9 full-graph end-to-end
   tests, and the upstream suite. The offline suite was 441 cases before this
   reconciliation round and grew with the gate/fitness tests; on dev the
   upstream run passed 1,498 tests with six skips.
3. **Behavioural** — the guardrail/trace invariants and the live prose
   faithfulness/relevancy target. The guardrail and trace layers have negative
   tests; the live test now measures a documented faithfulness/relevancy proxy
   (>= 0.6) and skips without a key instead of raising NotImplementedError. The
   live result still has to be produced with a key before the behavioural tier
   is fully evidenced.
4. **Gate-level** — the six D7 gates plus baseline integrity run as their own
   blocking jobs, and the gate logic itself has negative tests
   (`test/offline/test_gates.py`).

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

The process is still not finished, but the open list is shorter and honest: the
branch-protection *settings* must be applied on GitHub (the policy and the
workflow exist), the live prose run still needs a key, and the stateful
stall/budget termination trigger is not wired into every loop. Everything else
that this paragraph previously listed — the test-approval gate, the
semantic-evaluation gate, the module-boundary reconciliation and the baseline
declaration — is implemented and recorded (ADR-007/008/009).

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
recorded the audit-timing caveat. The outputs are the 441-test offline suite,
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

The AI-use log has thirteen entries spanning requirements, architecture,
guardrail, trace, verification, baseline integration, module integration, the
root-layout/CI changes, the structured-debate and context-budget implementations
(the two feature owners' entries) and this reconciliation round. That is a requirement-history record, but the team
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

The bug diary records twelve significant defects from the supervised build. They
cluster into four periods:

| Period | Defect class | Representative defect | Outcome |
|---|---|---|---|
| Guardrail/trace build | correctness and evidence integrity | non-dict state raised in the adapter; capture patches double-installed; capture faults were silently dropped; no-data markers matched prose; `build_trace` caught only `TraceError` | fixed with fail-closed normalization, idempotent capture, a capture-error journal, anchored placeholders and a broad trace-failure guard; regression tests added |
| CI and baseline integration | process/CI | `ModuleNotFoundError: src` from the pytest console script; AI-use-log gate blocked a style-only `src/` change | `pythonpath=.` and AI-use-log entry 008; CI passed |
| Dev integration | environment and drift | two Windows temp `PermissionError` cases; 19 altered pinned files | reran the two cases in a project-writable directory (both passed); baseline drift recorded as an open debt, not treated as a test failure |
| Submission reconciliation | contract, documentation and gate integrity | verifier could not express a *declared* difference; the element map pointed at two stubs; `.env.example` omitted the configuration keys it was said to document; the AI-use-log gate compared only `HEAD^..HEAD` | override manifest + strict verifier (ADR-008); facades + element map (ADR-007); the keys are documented; the gate compares the whole range (ADR-009) |

The trend is not a simple “fewer bugs every sprint” curve. The early bugs were
in the evidence and gate contracts; after those were fixed the failure surface
moved to integration and CI. The number of deterministic tests grew from the
initial guardrail/trace suite to 441 offline tests plus 9 full-graph end-to-end
tests; the dev upstream suite is 1,498 passing tests. The remaining gaps are
the live prose/semantic gate and the CI/branch-protection items, not
regressions in the implemented paths.

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
  the dev tree's 1,498 passing tests are the broadest current signal.
- **Structural** checks for the baseline layout, ruff and the module map. The
  module-map check is still a TODO; the dev/team-app mismatch is recorded.

The biggest testing lesson is that a test which only checks the happy path can
make a safety feature look finished while missing the failure that matters. The
fail-closed cases (missing cash, missing intent, config error, trace error) were
added because the human asked what happens when the input is absent or broken.
The live prose test is no longer a stub: it measures a documented
faithfulness/relevancy proxy (>= 0.6) and skips without a key, so the
behavioural layer has a real test and still owes a live result.

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
co-evolution now closes the two respects that were open:

1. the element map names the modules that run on dev, and the two former stubs
   are facades over those modules (ADR-007);
2. the 19 pinned differences are declared with an owner, a requirement, a commit
   and an ADR, and the verifier passes strictly because the differences are
   declared — not because the check was weakened (ADR-008).

An earlier version of this section described both as debt. They were closed by
decisions recorded in ADRs 007/008 and by the reconciliation work, not by
re-describing the tree as pristine.

### 4.4 Co-evolution controls and gaps

Controls that worked:

- the baseline verifier;
- the AI-use-log gate (it blocked a real style-only change until entry 008 was
  added);
- the trace matrix and invariant register when a new contract was added;
- the D5 transcripts as a record of why a change was accepted or rejected.

Controls that are still weak:

- branch protection *settings* are not applied on GitHub (the workflow and the
  policy document exist; the settings are a manual owner action);
- the live prose evaluation still needs a key before its result exists;
- the stateful stall/budget termination trigger is tested but not wired into
  every loop;
- the D5 records for two members are a reconstruction and a summary, not raw
  exports — the gap is declared in the D5 document and the debt register.

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
| Baseline verifier | “19 files differ, so dev fails” | A declared difference and an undeclared one are not the same fact; the verifier could express neither | Override manifest with owners and ADRs; `--strict` passes on declared drift and fails on undeclared or stale drift (ADR-008) |
| Element map | `src/context_assembler.py` and `src/structured_debater.py` were described as the owning modules | Both were stubs; the runtime lived in `tradingagents/` | Facades plus an element map that names the runtime modules, enforced by a fitness test (ADR-007) |
| Type check | Gate 2 was “partial: ruff and pip check” | A lint-only gate is not a type check | mypy scoped to `src/`, with the typing-only touch recorded and the guardrail untouched (ADR-009) |
| AI-use-log gate | Compared `HEAD^..HEAD` | A multi-commit push could change code without logging it | The gate compares the whole base..head range |

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

### 6.2 ZhuXuan (60377218) — REQ-CONTEXT-BUDGET

I owned REQ-CONTEXT-BUDGET, the input side of every model request. I started
with the News Analyst because its tool loop makes the growth visible: each round
can carry earlier messages, tool results and tool definitions into the next
request. Bounding one node first also gave a reviewable unit before the whole
graph changed.

The hardest part was deciding what to measure and where to enforce it.
Measuring only the prompt text would omit tool schemas and request framing, so
the implementation prepares the complete request, freezes its body and sends the
body it counted through a one-time permission. We also had to narrow the CityU
requirement to a reproducible local estimate in UTF-8 bytes. That changed how I
described the result: an enforced local budget is useful, while the provider's
token count stays a separate post-call observation. Claiming more would have been
dishonest.

Compression raised the second difficulty. Deleting a tool result on its own can
break the conversation, and deleting standing conditions can change a decision,
so the implementation pairs calls with results, protects the anchors and
constraints, filters explicitly future evidence, and blocks the send when the
remaining input still does not fit. In the paired synthetic test the complete
mock request fell from 17,155 to 10,266 byte-units while retaining two unique
facts and five standing constraints; the personal branch recorded 73 core and 18
integration passes. These support the local guard and the tested input fidelity;
they do not establish real model-output quality.

OpenCode supported the early pilot and Codex assisted the 0.7.1 migration,
review, tests and documentation. Human review changed the work directly: the
test plan was reviewed before implementation, scope started with one node, and
later reviews required a clear separation between Mock HTTP evidence and real API
evidence. The ADR stayed Proposed while only implementation had been authorised;
this submission round reconciled the module placement and recorded it as
Accepted under ADR-007. My lesson is to carry the measurement rule, the code
boundary, the test assertion and the remaining uncertainty in the same delivery
record, so the team can see which part is proven and which is still a claim.

*(Condensed from the member's own draft at `docs/context-budget-reflection.md`;
the member should confirm the condensation and the final wording.)*

### 6.3 Fan Hao (60835652) — REQ-STRUCTURED-DEBATE

I owned REQ-STRUCTURED-DEBATE. Before this work I treated a multi-agent debate as
a sequence of persuasive messages and assumed that a higher round count would
produce a better decision. Building it showed the opposite: long free-text
exchanges are hard to validate, compare or terminate reliably. A response can
sound analytical while repeating the same claim, citing a vague source, or
ignoring the opposing argument. The most important lesson was to separate fluent
reasoning from measurable reasoning. Explicit claims, evidence references,
rebuttal targets, concessions and confidence create a contract that persuasive
prose cannot satisfy by itself.

The second lesson was that termination must be independent of the debaters. A
dialogue agent naturally keeps talking, and it cannot be trusted to decide
objectively when its own work has stopped being useful. A deterministic policy
evaluated after complete cycles is not a perfect semantic judgement, but it is
inspectable and reproducible. Shadow mode was especially valuable: it records
what the policy would have done without changing token consumption or behaviour,
so the team can calibrate the threshold before it takes effect.

The third lesson was about compatibility. The original free-text history, report
tree, memory log and five-tier rating had to keep working, so the new state is
additive and the router only stops early on an *effective* termination decision.
That required care across the agent state, routing, managers, logging and
configuration, and it taught me to distinguish data that is useful to the UI from
data the graph needs to continue.

The main limitation is that convergence is deterministic rather than semantic: it
detects no new claims and stable positions, not whether both sides resolved the
same issue. A future version should add an independently validated debate judge,
keep a per-round termination history, and add token and elapsed-time budgets. I
would also align the implementation with the governance facades (`src/
structured_debater.py`, ADR-007) and add a comparison dashboard that records
tokens, time, evidence coverage and the final rating under identical inputs.

Overall I learned how much of agent quality lives in contracts and evidence
rather than in wording, and how to extend a mature pipeline without breaking the
behaviour its users depend on.

*(Condensed from the member's own contribution report at `FANHAO/report-FAN
Hao(1).md`; the member should confirm the condensation.)*

## 7. Verification evidence summary

| Evidence | Result | Where |
|---|---|---|
| Deterministic offline suite | 441 passed before this reconciliation round; the gate and fitness tests bring it to 475 | `pytest test/offline -m offline -q` |
| Full-graph end-to-end | 9 passed | `test/offline/test_integration_end_to_end.py` |
| Dev upstream suite | 1,498 passed, 6 skipped | dev workspace |
| Baseline, root layout | 213 pinned, 24 declared differences (5 project-owned + 19 dev), 0 undeclared, 0 stale; PASS | `scripts/verify_baseline.py --strict` |
| Baseline override consistency | every altered pinned file is declared and every declaration describes a real difference | `test/offline/test_gates.py`, `test_structural_fitness.py` |
| Type check | `python -m mypy` — no issues in 12 source files | project venv, ADR-009 |
| Static analysis | `ruff check src test scripts` PASS; `pip check` compatible | local venv |
| Safety-path checks | 21 checks, 0 failed (contract, purity, API surface, permissions, structure) | `scripts/check_safety_paths.py` |
| Schema gate | PASS (5 requirements validated) | `scripts/verify_schema.py` |
| Semantic-evaluation gate (deterministic) | prompt-constraint retention 1.00, decision replay 9/9, 0 escapes, model baseline unchanged | `scripts/gate_semantic_eval.py` |
| AI-use-log gate | base..head range; 13 entries | `scripts/gate_ai_use_log.py` |
| Test-approval gate | 7 approvals seeded over every current test file | `scripts/gate_test_approval.py`, `docs/test-approval.yaml` |
| Live guarded run | NVDA 2026-11-20, 14m28s, `Underweight`, guardrail PASS, 34 snapshots, 170/170 links, 0 findings, 0 capture errors | live artifacts |
| Live prose evaluation | implemented as a faithfulness/relevancy proxy (>= 0.6); needs `DEEPSEEK_API_KEY` to produce a result | `test/live/test_live_prose.py` |

Known unmet verification items: the live prose run needs a key before its
result exists; branch protection is a manual GitHub setting; the stateful
stall/budget termination trigger is tested but not wired into every loop; and
the D5 records for two members are not raw exports.

## 8. Formatting and pending team inputs

- **Formatting:** final report at 12-point font, single-line spacing, more than
  15 pages; maximum 10,000 words excluding diagrams. This draft is
  content-complete; typesetting and page expansion remain a team pass.
- **Team relative contributions:** recorded in §1 — three equal shares
  (1.00 each, mean = 1.0), agreed on 2026-11-25, with each member's story-point
  area and contribution evidence.
- **Member reflections:** §6.1–§6.3, one 300–500-word reflection per member with
  name and student ID. §6.2 and §6.3 are condensed from the members' own drafts
  and should be confirmed by them.
- **Point 12:** 12-point font size; there is no Section 12.
- **Remaining engineering gaps:** branch-protection settings on GitHub, the live
  prose result (needs a key), the per-loop stall/budget termination wiring, and
  the two D5 records that are not raw exports.

## Appendix A — Work phases and human gates

| Phase | Work | Artifacts / evidence | Human gate |
|---|---|---|---|
| 0. Baseline | Pin TradingAgents 0.7.1, establish the vendor/root layout and the five requirements | `PINNED_COMMIT.txt`, `BASELINE_MANIFEST.txt`, `docs/req/requirements.yaml` | Approve the baseline and scope |
| 1. Requirements | Classify functional, invariant, quality and performance requirements; define fit criteria | D1 registry + schema; transcript 01 | Approve the requirement set |
| 2. Architecture | Evaluate candidates, choose the layered/integration design, write ADRs and invariants | D2 blueprint, ADR-001–006, evaluation table, trace matrix | Approve the architecture and the rejected options |
| 3. Plan | Produce traceability, interface contracts, scope, test strategy and ordered steps | `Prompt.md` execution plan; transcript 03 | Stop before code |
| 4. Guardrail build | Build the deterministic gate, audit record, Hold fallback and negative tests | `src/guardrail.py`, offline suite | Approve each trigger and fail-closed behaviour |
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
| REQ-CONTEXT-BUDGET | performance / Must | `tradingagents/graph/context_budget.py`, `budgeted_model.py`, `deepseek_context_adapter.py`; facade `src/context_assembler.py` | `tests/test_context_budget_core.py` (40), `test_budget_agent_integration.py` (13), `test/offline/test_context_budget.py` (5) | Complete on the submission tree (ZhuXuan) |
| REQ-STRUCTURED-DEBATE | quality / Should | `tradingagents/debate/**` and graph/agent wiring; facade `src/structured_debater.py` | `tests/test_debate_opening.py` (5), `tests/test_structured_agents.py` (35) | Complete on the submission tree (Fan Hao) |
| REQ-TRACEABILITY | functional / Must | `src/trace_recorder.py`, `src/integration/trace_adapter.py` | `test/offline/test_traceability.py`, `test/offline/test_integration_trace.py`, E2E | Complete |
| REQ-HARD-GUARDRAIL | invariant / Must | `src/guardrail.py`, `src/integration/decision_adapter.py`, `gate_support.py`, `governed_graph.py` | `test/offline/test_guardrail.py`, decision/gate/E2E tests | Complete |
| REQ-TERMINATION-DISCIPLINE | performance / Should | `tradingagents/graph/termination.py` (`should_terminate`, `TerminationController`) + `src/termination_controller.py` facade; analyst loop wired | `test/offline/test_termination.py` (7 cases); debate termination tests | Complete for repeat/max + controller; stall/budget API tested, full per-loop wiring follow-up |

D1 itself validates: 5 requirements, schema PASS, all with fit criterion,
machine-checkable criterion, priority, source, statement and tradeoff. The
registry uses functional/invariant/quality/performance types; there is no
cost/governance/security-typed entry, which is a minor coverage note rather than
a schema failure.

Every row above is enforced on the submission tree (`dev`, ADR-007); none is
"implemented somewhere else". The 24 declared baseline differences that make the
call sites real are listed in `docs/architecture/baseline-overrides.md`.

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

**Single consolidated document:** `transcripts/D5-team-session-transcripts.md`
— Part A CUI Haoyu (60760270), Part B Fan Hao (60835652), Part C ZhuXuan
(60377218). The seven sessions below are Part A's raw records.

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
seven sessions are long (25,551 lines) because they include the raw tool and
model output, not a summary; the annotation is what makes the process auditable.

**Fidelity of the other two parts.** Part B is a retrospective reconstruction
(the file says so) and Part C is a supervision summary and evidence index; the
raw OpenCode exports for those two members are not in the repository. The D5
document states this in its integrity statement and the debt register carries
the action. That is the honest state: two of three records are not raw, and the
report does not imply otherwise.

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
| Bug-009 | baseline | dev could not pass `--strict` without undeclaring drift | The verifier had no way to express a declared difference | Override manifest + declared/stale reporting (ADR-008) | Baseline integrity |
| Bug-010 | documentation | `.env.example` omitted the `debate_*` / `context_input_*` keys it was said to document | Config map and example file drifted | Keys documented with the feature owners' defaults | Configuration honesty |
| Bug-011 | CI | AI-use-log gate compared only `HEAD^..HEAD` | One commit is not a change set | The gate compares base..head and resolves the base from the CI event | Gate integrity |
| Bug-012 | architecture | The element map named two stubs as owners | The feature-c overlay was never the runtime tree | Facades + element map + fitness test (ADR-007) | Structure |

The full symptom/reproduction/root-cause/fix text is in `docs/bug-diary.md`.
The trend is from gate/evidence defects toward integration/CI defects, not a
monotone decline; the remaining gaps are mostly unbuilt features and gates.

## Appendix F — Verification commands and results

| Command / evidence | Result |
|---|---|
| `pytest test/offline -m offline -q` | 475 passed (441 prior + 20 gate + 14 fitness) |
| `pytest test/offline/test_integration_end_to_end.py` | 9 passed |
| `pytest tests -q -m "not integration"` on dev | 1,498 passed, 6 skipped |
| `pytest tests --collect-only -q` on team-app | 1,414 tests collected |
| `scripts/verify_baseline.py --strict` | PASS: 213 pinned, 24 declared differences (5 project-owned + 19 dev), 0 undeclared, 0 stale |
| `python -m mypy` | Success: no issues found in 12 source files |
| `ruff check src test scripts` | PASS |
| `scripts/check_safety_paths.py --quiet` | 21 checks, 0 failed |
| `scripts/verify_schema.py` | schema-gate: PASS (5 requirements) |
| `scripts/gate_semantic_eval.py` | PASS (retention 1.00, 9/9 decisions, 0 escapes) |
| `scripts/gate_test_approval.py` | PASS (7 approvals over the current test files) |
| `scripts/gate_ai_use_log.py` | PASS when the log is updated in the same change set |
| Live run | NVDA 2026-11-20, 14m28s, Underweight, PASS, 34 snapshots, 170/170 links, 0 findings |
| Feature-c CI | success |
| Dev CI | success before this round; the new jobs run on the next push |

The live run is not a mock: it calls Yahoo, SEC EDGAR, news/macro/prediction
tools and DeepSeek, and writes the sidecar/report/memory chain. Its trace
records `fred (no-data)`, `reddit (no-data)` and `stocktwits (no-data)` as
explicit evidence of absence.

## Appendix G — Open gaps and suggested action

| Gap | Impact | Suggested action | Owner |
|---|---|---|---|
| Full per-loop stall/budget termination wiring | Controller implemented/tested; analyst loop wires repeat+max; debate engine wires convergence/schema | Wire the stateful stall/budget trigger into the remaining loops | CUI Haoyu (60760270) |
| Branch protection settings | The workflow and the policy exist; the GitHub settings are a manual step, so a merge could bypass the checks | Apply the required checks + code-owner review on `dev`/`main` per `docs/architecture/branch-protection.md` | team lead |
| Live prose result | The test now measures a faithfulness/relevancy proxy (>= 0.6) but skips without a key | Run it once with `DEEPSEEK_API_KEY` and record the result in the evidence table | CUI Haoyu |
| D5 raw exports for two members | Parts B and C are a reconstruction and a summary, not raw sessions | The two owners supply their raw session exports, or the submission declares them as summaries | Fan Hao / ZhuXuan |
| ~~Team relative weights~~ | Resolved 2026-11-25: three equal shares (1.00 each) | Recorded in §1; no action | — |

> **Ownership note:** the code-level gaps are closed or scoped; the remaining
> items are a manual GitHub setting, one live run, and the two D5 export gaps.

## Appendix H — D1–D9 deliverable map

| Deliverable | Status (submission tree = `dev`) | Evidence / remaining gap |
|---|---|---|
| D1 Requirements | Complete | 5 requirements with fit criteria, priorities, sources; schema PASS; AI-use log 13 entries. No cost/governance/security-typed entry (minor coverage note). |
| D2 Architecture | Complete | Blueprint, ADR-001–009, invariants, trace matrix, memory, permission, runtime catalog, evaluation table/logbook, risk list and option ledger. ADR-001/002 have named owners; ADR-007 fixes the element map; ADR-008 declares the baseline differences; ADR-009 adds the type-check gate. |
| D3 Governance | Complete | `AGENTS.md` (submission tree, contracts, ownership), structural constraints with an enforced element map, permission model, rules/covenant and the MCP manifest. The module-to-element fitness check is now a test, not a TODO. |
| D4 Verification | Complete for the implemented paths | Review memos, debt register, bug diary, test-to-requirement map, structural-fitness tests, gate tests, and a live prose proxy with documented thresholds. The live result still needs a key. |
| D5 Transcripts | Complete as a consolidated document | `transcripts/D5-team-session-transcripts.md` — three labelled parts; Part A raw, Parts B/C declared as reconstruction and summary. |
| D6 Report | This document | All three members' contributions and reflections recorded with names and student IDs; the numeric weight is the one field left to the team. Point 12 is 12-point font. |
| D7 GitHub/CI | Complete in-repo; settings pending | Nine blocking jobs (six gates + safety paths + baseline + summary), CODEOWNERS, PR template and the branch-protection policy. Applying the GitHub settings is a manual owner step. |
| D8 Source/tests | Complete on `dev` | All five elements implemented and enforced on the submission tree; the two former stubs are facades (ADR-007); the baseline differences are declared (ADR-008). |
| D9 Prompt | Complete | `Prompt.md` requires plan-first, human approval, staged build and gates. |

## Appendix I — Governance and verification checklist

| Check | How it is satisfied | Status |
|---|---|---|
| Requirements are machine-readable and schema-valid | YAML registry + JSON schema + CI schema gate | Pass |
| Every fit criterion has a test | Guardrail/trace/termination/context/debate rows mapped to named tests | Pass (live prose proxy included) |
| Every invariant has a negative test | guardrail trigger tests; trace completeness tests; gate tests | Pass |
| Every test references a requirement/invariant | Trace/guardrail test docstrings and names | Pass for owned modules |
| Full prior suite runs with zero regressions | 475 offline + 9 E2E + upstream 1,498 | Pass for implemented paths |
| New code/prompts update the AI-use log | Gate 6, whole base..head range | Pass (gate is real) |
| Review memo per integration unit | D4 review memos for the feature-c/dev units and this reconciliation | Pass for reviewed units |
| Debt and bug records are current | Debt register and bug diary updated with this round | Pass (ongoing) |
| Human approval before code | `Prompt.md`, D5 transcripts, merge/review gates | Pass |
| Semantic evaluation | Deterministic replay gate in CI; live proxy needs a key | Pass for the deterministic half; live pending |
| Branch protection | Policy + CODEOWNERS in repo; GitHub settings are a manual step | Partial (documented) |
| Type check | mypy scoped to `src/`, blocking in CI | Pass |

## Appendix J — Limitations and next actions

The report's strongest evidence is the actual live run and the deterministic
guardrail/trace tests; its weakest evidence is the semantic layer and the
team-process records. The following limitations are material:

1. **One tree, by decision.** `dev` is the submission tree (ADR-007); the
   `feature-c` overlay is history. The element map names the runtime modules and
   the two former stubs are facades. The report's earlier "two trees" limitation
   is closed by that decision, not by ignoring the difference.
2. **Baseline differences are declared, not removed.** The 19 dev overrides are
   listed with an owner, a requirement, a commit and an ADR, and the verifier
   passes strictly on the declared set (ADR-008). The honest limitation is that
   these *are* modifications to a pinned baseline; the reopen path is to port
   them into `src/` and restore the files.
3. **Termination is implemented for the repeat/max path.** The controller and
   analyst-loop wiring are tested; the stateful stall/budget trigger is tested
   at the controller but not yet wired into every loop. That is an integration
   follow-up, not a missing module.
4. **The semantic gate has two halves.** The deterministic replay (prompt
   constraints, guardrail decisions, model baseline) is blocking in CI; the live
   faithfulness/relevancy run is implemented but needs a key before its result
   exists.
5. **Branch protection is a settings step.** The workflow, CODEOWNERS and the
   policy document exist; the GitHub branch settings must be applied by the team
   lead. Until then the checks are real but a merge could bypass them.
6. **Two D5 records are not raw.** Parts B and C of the consolidated D5 document
   are a reconstruction and a summary; the D5 document says so in its integrity
   statement, and the debt register carries the action.
7. **The contribution weight is an equal split.** The team agreed three equal
   shares (1.00 each, mean = 1.0) on 2026-11-25, with each member's story-point
   area recorded in §1. It is a team decision, not a measured hour count; the
   evidence column is what it rests on.

The next actions are therefore concrete: apply the branch-protection settings;
run the live prose evaluation once with a key; wire the stateful stall/budget
trigger into the remaining loops; obtain the two missing raw D5 exports; agree
the effort measure and weights; and typeset the report at 12-point single
spacing. None of these should be hidden behind a claim that the project is
already complete.

> **CUI Haoyu note:** for my part, the guardrail/trace evidence, the D5
> transcripts and the baseline verifier are ready. The remaining items above
> are either other owners' modules or team-level decisions; I have marked them
> instead of inventing their outcomes.
