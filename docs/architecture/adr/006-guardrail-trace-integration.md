# ADR-006: Guardrail and Trace-Recorder Integration into the TradingAgents Pipeline

- **Status:** Accepted
- **Decision owner:** CUI Haoyu (60760270)
- **Date:** 2026-11-25
- **Amends:** ADR-003 (evidence-chain traceability), ADR-004 (deterministic guardrail)

## Context

`src/guardrail.py` (G-A) and `src/trace_recorder.py` (T-A) are implemented and
tested, but the pinned TradingAgents 0.7.x baseline never calls them. The
baseline ends every run in `TradingAgentsGraph.record_decision`, which writes
the state log and the memory log for both the programmatic `propagate()` path
and the CLI streaming path. The vendored tree is pinned at commit
`9fa1196fffbcfd9de5146d2dd2869df84ab99838` and must stay byte-identical
(`scripts/verify_baseline.py`, 213 blobs).

Three facts constrain the integration:

- The governance modules are pure and their import allowlists are pinned by
  AST tests; they cannot import the framework. Any code that touches the
  baseline is composition and lives in `src/integration/`.
- The baseline produces a 5-tier rating but no structured order intent.
  `TraderProposal.position_sizing` is optional free text (`schemas.py`), the
  Portfolio Manager publishes a rating with no numeric size, and
  `PortfolioContext` has cash and signed positions but no current price.
- Upstream reserves the string `"REVIEW"` for an unreadable decision
  (`agents/rating.py`, `#1170`). It is not a legal tier and must never be
  written as a rating.

## Decision

### 1. Gate point

`GuardedTradingAgentsGraph(TradingAgentsGraph)` overrides `record_decision`:
it builds the decision, evaluates it with the frozen guardrail, applies the
verdict to the caller's state **in place**, then delegates to
`super().record_decision`. `create_run_state` opens the per-run evidence
capture; `stream_run` and `propagate` close it on every exit path. The guarded
CLI (`python -m src.integration`) patches the module-level name
`cli.run.TradingAgentsGraph` for the duration of the run. No file under
`vendor/` is edited.

The order inside the gate is a safety property: finish capture, read the
agents' rating with `run_rating` **before** mutation, evaluate, apply, write
the memory log, then attest the trace. Evidence can never cost a decision its
memory-log entry.

### 2. Execution intent (policy A+B-strict)

The guardrail judges an **explicitly declared execution intent**, not an
inference from the current book:

- `size_pct` — a fraction of portfolio value (`0.05` = 5%), compared with the
  frozen 0.10 limit;
- `short_amount` — absolute notional, compared with available cash;
- `available_cash` — from `PortfolioContext.cash`;
- `rating` — the graph's `run_rating(final_state)`.

There is **no default size and no default short**. A missing size, short, cash,
or rating becomes `None` in the frozen `Decision` and the real
`evaluate_decision` returns `MALFORMED_DECISION`; the gate writes `Hold`. The
adapter never substitutes zero, never labels a check `NOT_EVALUATED` and lets
the decision pass, and never raises for a malformed state.

The Trader's free-text `Position Sizing` is parsed only as **corroboration**:
one `X%`/`X %` token, compared with the declared fraction. A disagreement
larger than 0.005 is recorded as `SIZE_DISAGREEMENT`; it never changes the
verdict, because prose is not authority.

The guarded CLI exposes
`--guardrail-position-fraction FLOAT` and `--guardrail-short-amount FLOAT`,
stripped before typer sees them. Both, plus `--portfolio`, are required for a
passing decision. Programmatic callers pass `ExecutionIntent` to the
constructor or set `EXECUTION_INTENT`.

**Why not current-book sizing (the rejected policy C).** Computing
`size_pct` from the existing position and a current price measures the book,
not the proposed decision. A ticker with no position yields `size_pct = 0`, so
a new oversized Buy passes — exactly the escape REQ-HARD-GUARDRAIL names. A
Sell that reduces an already-oversized position would be rejected even though
it is risk-reducing. The baseline has no current price in state, so the
computation also requires an extra vendor call. It is the wrong quantity.

**Why not parse-only (A).** The sizing field is optional prose; most runs
would be rejected for a parsing reason rather than a safety reason, and the
gate's verdict would vary with model wording on identical inputs.

**Why not rating-only with NOT_EVALUATED (B-lax).** An unchecked size is the
fail-open shape `INV-GUARDRAIL-ZERO-ESCAPE` forbids. A label in a log does not
make an unguarded decision safe.

*Declared scope limit:* the gate checks the intent the caller declares. The AI
cannot change that declaration; the execution layer must execute the declared
order. Structural enforcement of that final hand-off is deferred until an
execution module exists (the same scope limit recorded in ADR-004).

### 3. Evidence chain (G1, run-level)

The integration captures five live data paths for the duration of a run:

- `tradingagents.dataflows.router.route_to_vendor` and the name bound in
  `tradingagents.agents.tools`;
- `tradingagents.agents.tools.build_verified_market_snapshot`;
- `tradingagents.agents.analysts.sentiment_analyst.fetch_stocktwits_messages`;
- `...fetch_reddit_posts`.

Each call becomes one content-addressed snapshot,
`snap-{trade_date}-{method}-{digest12}`; identical calls collapse. A vendor
sentinel or fetcher placeholder is recorded as evidence of absence with a
`(no-data)` source, not dropped. `fetch_timestamp` is one injected UTC instant
per run, taken in `create_run_state`; the as-of date lives in the id. No clock
is read inside the recorder adapters.

One critical assertion is recorded per non-empty report and one for the final
decision, `decision:{ticker}:{trade_date}:{guarded_rating}`. Every assertion
links to the run's whole deduplicated evidence set, in sorted id order, and
the final decision cites the same set. The audit and a renderable table are
written to
`<results_dir>/<ticker>/TradingAgentsStrategy_logs/guardrail_trace_<date>.json`
beside the state log; the guardrail payload also carries them in the returned
state.

**This is deliberately coarse.** There is no per-analyst or per-method runtime
attribution claim: the analysts run in parallel, and a call observed while
three are mid-flight cannot be pinned to one reliably. A false attribution is
worse than a coarse one because it invites a reader to verify a citation
against the wrong source. The assertion means "this artifact exists and the
run's evidence must resolve", not "every sentence rests on these snapshots".
That boundary is ADR-003's not-yet-called interface and a reopen condition
below.

### 4. Fallback vocabulary

A rejection writes `final_rating = "Hold"` and audit action `"REVIEW/HOLD"`,
never `"REVIEW"`. The original decision text is preserved verbatim below a
deterministic banner. The composed text therefore has two rating labels that
disagree by construction; `extract_rating` returns `None` for it (fail-closed,
`REVIEW` if passed to `parse_rating`). The baseline stays correct because every
consumer calls `run_rating`, which prefers the explicit `final_rating = "Hold"`
we set over the text. This is a reason, not label agreement: no downstream
code may parse the composed text directly for the executed rating.

A rejected run is still written to the memory log as `Hold`; a rejection is a
decision that was taken, not "no decision".

### 5. Failure posture

- A broken guardrail *configuration* (`GuardrailError`) fails closed to `Hold`
  with a `GUARDRAIL_CONFIG_ERROR` note. A gate that cannot run is a rejection.
- A trace failure is recorded as `traceable: false` with a `trace_error`; it
  never changes the rating and never prevents the memory-log write. The
  guardrail is the gate; the trace is evidence.
- A capture fault is journalled in `capture_errors` and never breaks the run.
  Observability may not break the programme it observes.
- A failed run restores every patched function through `finally`.

### 6. Observability surfaces

- `final_state["guardrail"]`: verdict, audit record, decision, limits,
  original rating, load report, trace, sidecar path.
- `run_settings()`: upstream settings plus `guardrail_limits` and
  `trace_enabled`, so the state log records what the run was judged against.
- Sidecar JSON: the durable audit record beside the state log.
- Report decision section: the fallback banner is visible in the report the
  CLI displays and saves.
- `--help`: the two guarded options are printed to stderr; upstream help on
  stdout is unchanged.

## Alternatives considered

- **Current-book sizing (C)** — rejected for the quantity error above.
- **Parse-only (A)** — rejected: optional LLM prose is not a stable order.
- **Rating-only with NOT_EVALUATED (B-lax)** — rejected: fail-open.
- **Per-analyst/per-method trace attribution (G2-lite)** — rejected: parallel
  analysts make runtime attribution unreliable; a false citation is worse than
  a coarse one.
- **Call-level or field-level provenance (G2-full/G3)** — rejected: storage,
  nondeterminism, and an LLM fact-extractor would manufacture assertions.
- **Editing `cli/run.py` or the agents to emit structured sizing** — rejected:
  the vendor tree is pinned; extend, never replace.

## Consequences

- REQ-HARD-GUARDRAIL and REQ-TRACEABILITY are enforced on every run started
  through the guarded entry point, with evidence in the returned state, the
  memory log and the sidecar.
- A guarded run without an intent or a portfolio book is recorded as `Hold`.
  That is the fail-closed default; the normal `tradingagents` CLI remains
  unguarded unless the operator opts into `python -m src.integration`.
- Trace links are run-level, not sentence-level. Reports are backed by the
  run's evidence set, not by a proof of which sentence used which snapshot.
- `verify_baseline.py --strict` is a clean-tree gate: upstream tests create
  ignored `pytest-of-*`/`tmp*`/cache droppings under `vendor/`. Run the suite
  with `PYTHONDONTWRITEBYTECODE=1`, remove only those run droppings, then run
  `--strict`; the pinned set is never touched.

## Reopen conditions

- **R-1** Measured false-rejection rate is too high -> revisit the limits
  (ADR-004) or the intent source.
- **R-2** A caller is found relying on `propagate()` returning an unguarded
  decision -> make the gate structural rather than a subclass.
- **R-3** Sentence-level provenance becomes a requirement -> the producing
  agents must declare their critical assertions and their evidence up front;
  the run-level boundary is then replaced.
- **R-4** The baseline gains a numeric size/budget field -> re-evaluate policy
  A as a first-class input and retire the declared-intent requirement.
- **R-5** The vendor tree is upgraded -> re-verify the five capture seams, the
  `record_decision` call sites and this ADR.
- **R-6** Per-analyst tool-call provenance becomes available from the
  framework -> replace G1 with the finer granularity; keep the audit shape.

## Verification

Independent final gate on 2026-11-25 (project `.venv`, CPython 3.12.13):

| Gate | Result |
|---|---|
| Offline suite (`pytest test/offline -m offline -q`) | **429 passed, 2 deselected** |
| Full-graph E2E (`test_integration_end_to_end.py`) | **9 passed** (scripted model, offline vendors) |
| Upstream baseline (`vendor/.../pytest tests -q`) | **1407 passed, 6 skipped, 0 failed** |
| Ruff (`ruff check src test`) | **All checks passed** |
| Schema gate (`scripts/verify_schema.py`) | **PASS (5 requirements validated)** |
| Baseline integrity (`scripts/verify_baseline.py --strict`) | **213/213 PASS** on a clean tree |
| Guarded CLI (`python -m src.integration --help`) | **exit 0**, guarded options on stderr |

**Root-layout note.** In the clean `feature-c` repository the pinned 0.7.1
baseline is the repository root, not `vendor/tradingagents-0.7.x/`.
`scripts/verify_baseline.py` auto-detects that layout and verifies the 208
pinned files not owned by the project; five pinned files are declared
project-owned overrides (`README.md`, `.gitignore`, `.env.example`,
`requirements.txt`, `.github/workflows/ci.yml`) and are reported as
`overridden`, never silently skipped. Project additions under `src/`, `test/`,
`docs/`, `transcripts/`, `scripts/` and `prompts/` are expected. The vendor
layout keeps the original 213/213 strict rule.

The E2E tests exercise both the programmatic `propagate()` path and the CLI
streaming path on the real LangGraph with scripted models: a compliant order
passes, an oversized order is held, a missing order is malformed, the sidecar
is written, the memory log records the guarded rating, and a replay produces
the same evidence chain.
