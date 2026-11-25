# TradingAgents Enhancement — CS5351 Team Project

> **Team-app root — the submission tree is `dev`** (ADR-007). All deliverables
> (D1–D9) live here and were produced by an AI coding agent (OpenCode) under
> auditable human supervision.
>
> | Student | Student ID | Story points / owned requirement(s) | Weight |
> |---|---|---|---|
> | CUI Haoyu | 60760270 | Safety boundary + evidence-chain traceability (REQ-HARD-GUARDRAIL, REQ-TRACEABILITY); ADR-006 integration, D7/D8 governance | 1.00 |
> | ZhuXuan | 60377218 | Context retrieval and budget (REQ-CONTEXT-BUDGET, ADR-001) | 1.00 |
> | Fan Hao | 60835652 | Structured debate + termination (REQ-STRUCTURED-DEBATE, REQ-TERMINATION-DISCIPLINE; integration wiring by CUI Haoyu) | 1.00 |
>
> Contribution evidence and reflections: `Report.md` §1 and §6. Session
> transcripts: `transcripts/D5-team-session-transcripts.md`.

## 1. Purpose and architecture (a few paragraphs)

This project enhances the [TradingAgents](https://github.com/tauricresearch/tradingagents)
multi-agent LLM financial trading framework. The baseline is a LangGraph
orchestration of specialised LLM agents (market / social / news / fundamentals
analysts, bull & bear researchers, a trader, risk debators, and a portfolio
manager) that collaborate to produce a 5-tier trade rating.

Our enhancement adds five requirements focused on making the agent system more
efficient, more auditable, and safer:

- **REQ-CONTEXT-BUDGET** — bound and compact each agent's context to cut tokens
  (`tradingagents/graph/context_budget.py`, `budgeted_model.py`,
  `llm_clients/deepseek_context_adapter.py`; facade `src/context_assembler.py`).
- **REQ-STRUCTURED-DEBATE** — turn the free-form bull/bear debate into a
  structured, schema-validated, convergible dialogue (`tradingagents/debate/**`;
  facade `src/structured_debater.py`).
- **REQ-TRACEABILITY** — record an evidence chain from each assertion to the
  data snapshot it cited (`src/trace_recorder.py` + `src/integration/trace_adapter.py`).
- **REQ-HARD-GUARDRAIL** — a deterministic safety boundary that hard-checks
  every AI decision (position size, cash, legal rating) with zero tolerance
  (`src/guardrail.py` + `src/integration/**`).
- **REQ-TERMINATION-DISCIPLINE** — give each agent loop self-termination on
  stall / repeat / budget exhaustion (`tradingagents/graph/termination.py`;
  facade `src/termination_controller.py`).

The element map is enforced by `test/offline/test_structural_fitness.py`
(ADR-007). The 24 declared differences from the pinned 0.7.1 baseline — 5
project-owned files and 19 owned dev overrides — are listed in
[`docs/architecture/baseline-overrides.md`](docs/architecture/baseline-overrides.md)
and enforced by `scripts/verify_baseline.py` (ADR-008).

## 2. Project file organisation

```text
<repo-root>/
├── README.md / AGENTS.md / architecture-blueprint.md / Prompt.md / Report.md
├── docs/
│   ├── req/           machine-readable PRD + CI validation schema (D1)
│   ├── architecture/  11 artifact types + ADR-001..009 + baseline-overrides.md (D2)
│   ├── code-governance/ coding + verification governance (D3, D4)
│   ├── eval/          fixed evaluation set for the semantic gate
│   ├── ai-use-log.yaml / review-memo.md / debt-register.md / bug-diary.md
│   ├── d4-verification-plan.md
│   └── test-approval.yaml
├── .opencode/         project-level permissions + always-on rules (D3)
├── .agent/            project covenant (D3)
├── .github/           workflows + CODEOWNERS + PR template (D4/D7)
├── scripts/           gates: schema, baseline, test approval, semantic,
│                      AI-use log, safety paths, element map
├── prompts/           versioned runtime prompts
├── src/               guardrail, trace recorder, integration, facades (D8)
├── test/offline/      deterministic tests (D4/D8)
├── test/live/         API-dependent tests
└── transcripts/       consolidated + per-session agent transcripts (D5)
```

## 3. How to run the tests and the gates

### One-time setup (project-local `.venv`, CPython 3.12)

The submission tree is the **root layout**: the pinned 0.7.1 baseline *is* the
repository root; there is no `vendor/` copy.

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -e . --no-deps
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
uv pip check --python .venv/Scripts/python.exe
```

Reproduce the exact environment instead of resolving fresh:

```bash
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
uv pip install --python .venv/Scripts/python.exe -e . --no-deps
```

`.venv/` is local-only and never part of the submission (see `.gitignore`).
Do not use the global interpreter.

### Offline (deterministic) tests — ours

```bash
.venv/Scripts/python.exe -m pytest test/offline -m offline -q
```

No API keys; this is the suite CI runs. It includes the integration suite
(`test/offline/test_integration_*`), the context-budget configuration contract,
the termination controller, the structural fitness checks and the gate tests.

### Upstream baseline unit tests

```bash
CI=1 TRADINGAGENTS_NO_UPDATE_CHECK=1 .venv/Scripts/python.exe -m pytest tests -q -m "not integration"
```

Never run our suite and the upstream suite in one pytest invocation: they use
different marker sets and different autouse fixtures.

### Live (API-dependent) tests

```bash
.venv/Scripts/python.exe -m pytest test/live -m live
```

These call the configured LLM / data providers and require keys in `agent.env`
(or `.env`). `test/live/test_live_prose.py` measures a documented
faithfulness/relevancy proxy (>= 0.6) and **skips** without a key.

### The blocking gates (D7)

```bash
.venv/Scripts/python.exe scripts/verify_schema.py            # gate 3
.venv/Scripts/python.exe -m ruff check src test scripts       # gate 2 (lint)
.venv/Scripts/python.exe -m mypy                              # gate 2 (types)
.venv/Scripts/python.exe scripts/check_safety_paths.py        # gate 2 (contract/security/API/permission)
.venv/Scripts/python.exe scripts/verify_baseline.py --strict  # ADR-008
.venv/Scripts/python.exe scripts/gate_test_approval.py --list # gate 1
.venv/Scripts/python.exe scripts/gate_semantic_eval.py        # gate 4
.venv/Scripts/python.exe scripts/gate_ai_use_log.py --list    # gate 6
```

### CLI smoke test

```bash
CI=1 TRADINGAGENTS_NO_UPDATE_CHECK=1 .venv/Scripts/python.exe -m cli.main --help
```

### Guarded pipeline (Guardrail + TraceRecorder integration)

The upstream CLI is unguarded by default. To run the same CLI with the
deterministic gate and the evidence chain, use the integration entry point and
declare the order you intend to execute:

```bash
.venv/Scripts/python.exe -m src.integration --ticker NVDA --date 2026-11-24 \
    --portfolio book.json \
    --guardrail-position-fraction 0.05 --guardrail-short-amount 0
```

- `--guardrail-position-fraction` is a fraction of portfolio value (`0.05` = 5%).
- `--guardrail-short-amount` is an absolute notional in the book's currency.
- Both, plus `--portfolio` (cash + positions), are required for a decision to
  pass. Omitting any of them fails closed to `Hold`; there is no default size
  and no rating-only pass.
- The verdict, audit record and trace table are returned in the final state and
  written beside the state log as
  `results/<ticker>/TradingAgentsStrategy_logs/guardrail_trace_<date>.json`.
- `python -m src.integration --help` prints the two guarded options on stderr
  and the upstream help on stdout.

The integration is specified in
`docs/architecture/adr/006-guardrail-trace-integration.md`; the full-graph
tests are `test/offline/test_integration_end_to_end.py`.

## 4. The real GitHub project

- Team repository: https://github.com/jiushangxiehou/TradingAgentsUltra
- Integration branch: `dev` (the submission tree)
- Reference upstream: https://github.com/tauricresearch/tradingagents

The repository holds the pinned 0.7.1 baseline at the root, the project
additions in `src/`, `test/`, `docs/`, `scripts/`, `prompts/` and
`transcripts/`, and the feature branches used for the structured-debate and
context-budget work.

## 5. Blocking-gate design and current status

The CI workflow is `.github/workflows/ci.yml`: nine jobs — the six D7 gates,
safety-path checks, baseline integrity and an aggregate job. Branch protection
is a repository setting; the policy is in
`docs/architecture/branch-protection.md`.

| Gate | Design | Current status |
|---|---|---|
| 1. Test approval | Every changed test must be approved in the manifest at the base revision (`docs/test-approval.yaml`); a bootstrap fallback requires a named approver and is covered by CODEOWNERS review. | **Implemented** (`scripts/gate_test_approval.py`, 7 seeded approvals, negative tests). |
| 2. Static analysis | `ruff`, `mypy` (scoped to `src/`, ADR-009), `pip check`, plus the safety-path checks (contract, security, API surface, permissions, structure). | **Implemented**; mypy is clean on 12 files and `check_safety_paths` is 21/21. |
| 3. Schema | Validate `docs/req/requirements.yaml` against `docs/req/req-schema.json`. | **Implemented** in CI and locally. |
| 4. Semantic evaluation | Replay a fixed evaluation set (`docs/eval/fixed-set.json`): prompt-constraint retention >= 0.6, 9 labelled guardrail decisions at 100%, model baseline unchanged. The live faithfulness/relevancy proxy (>= 0.6) is `test/live/test_live_prose.py`. | **Implemented** for the deterministic half; live run needs a key. |
| 5. Regression | Offline suite + full upstream suite on every change; any regression blocks. | **Implemented**. |
| 6. AI-use log | A code/prompt change must update `docs/ai-use-log.yaml`; the comparison covers the whole base..head range. | **Implemented** (`scripts/gate_ai_use_log.py`, 14 entries). |
| Baseline integrity (ADR-008) | `--strict` passes on 213 pinned files with 24 **declared** differences; undeclared or stale drift fails. | **Implemented**; passes on `dev`. |

**Branch protection:** the workflow, `CODEOWNERS`, the PR template and the
policy document are in the repository. Applying the GitHub settings (required
checks + one approval + code-owner review on safety paths) is a manual owner
step, recorded in `docs/architecture/branch-protection.md` and the debt
register.