# TradingAgents Enhancement — CS5351 Team Project

> **Team-app root.** This is the repository root (`<team-app>/`) for the
> CS5351 Agentic Software Engineering project. All deliverables (D1–D9) live
> under here and are produced and governed by an AI coding agent (OpenCode)
> under auditable human supervision.

## 1. Purpose and architecture (a few paragraphs)

> TODO: Replace this section with your team's real summary once the design is
> settled. Keep it to a few paragraphs.

This project enhances the [TradingAgents](https://github.com/tauricresearch/tradingagents)
multi-agent LLM financial trading framework. The baseline is a LangGraph
orchestration of specialised LLM agents (market / social / news / fundamentals
analysts, bull & bear researchers, a trader, risk debators, and a portfolio
manager) that collaborate to produce a 5-tier trade rating.

Our enhancement adds five requirements focused on making the agent system more
efficient, more auditable, and safer:

- **REQ-CONTEXT-BUDGET** — bound and compact each agent's context to cut tokens.
- **REQ-STRUCTURED-DEBATE** — turn the free-form bull/bear debate into a
  structured, schema-validated, convergible dialogue.
- **REQ-TRACEABILITY** — record an evidence chain from each assertion to the
  data snapshot it cited.
- **REQ-HARD-GUARDRAIL** — a deterministic safety boundary that hard-checks
  every AI decision (position size, cash, legal rating) with zero tolerance.
- **REQ-TERMINATION-DISCIPLINE** — give each agent loop self-termination on
  stall / repeat / budget exhaustion.

The architecture is documented under `docs/architecture/` (blueprint, ADRs,
invariants, trace matrix, memory design, permission model, runtime policy).
The coding agent is governed by `AGENTS.md`, `.opencode/`, and `.agent/`.

## 2. Project file organisation

```
<repo-root>/
├── README.md / AGENTS.md / architecture-blueprint.md / Prompt.md / Report.md
├── docs/
│   ├── req/           machine-readable PRD + CI validation schema (D1)
│   ├── architecture/  8+3 architecture artifact types (D2)
│   ├── code-governance/ coding + verification governance (D3, D4)
│   ├── ai-use-log.yaml / review-memo.md / debt-register.md / bug-diary.md
├── .opencode/         project-level permissions + always-on rules (D3)
├── .agent/            project covenant (D3)
├── .github/workflows/ CI blocking gates (D4/D7)
├── prompts/           versioned runtime prompts
├── src/               full source (D8)
├── test/offline/      deterministic tests (D4/D8)
├── test/live/         API-dependent tests
└── transcripts/       student-annotated agent session transcripts (D5)
```

## 3. How to run the tests

### One-time setup (project-local `.venv`, CPython 3.12)

The project supports two equivalent layouts:

- **vendor layout** (this local working copy): the pinned baseline is under
  `vendor/tradingagents-0.7.x/`.
- **root layout** (`feature-c` in the clean repository): the repository root
  *is* the pinned 0.7.1 baseline; there is no `vendor/` copy.

```bash
uv venv --python 3.12 .venv

# vendor layout:
uv pip install --python .venv/Scripts/python.exe -e vendor/tradingagents-0.7.x
# root layout:
# uv pip install --python .venv/Scripts/python.exe -e . --no-deps

uv pip install --python .venv/Scripts/python.exe -r requirements.txt
uv pip check --python .venv/Scripts/python.exe
```

Reproduce the exact environment instead of resolving fresh:

```bash
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
# vendor layout:
uv pip install --python .venv/Scripts/python.exe -e vendor/tradingagents-0.7.x --no-deps
# root layout:
# uv pip install --python .venv/Scripts/python.exe -e . --no-deps
```

`.venv/` is local-only and is never part of the submission (see `.gitignore`).
Do not use the global interpreter.

### Baseline pin

The pinned baseline is TradingAgents 0.7.1 at commit
`9fa1196fffbcfd9de5146d2dd2869df84ab99838` (tree
`21197e6c24b0d5fa01076530a3f0c37863b5c555`). It lives either in
`vendor/tradingagents-0.7.x/` (vendor layout) or at the repository root (root
layout); `PINNED_COMMIT.txt` and `BASELINE_MANIFEST.txt` are in that baseline
directory. Never edit the pinned files; all enhancement work lives in `src/`
and `test/`.

To confirm the baseline has not drifted (the script auto-detects the layout):

```bash
python scripts/verify_baseline.py --strict
```

- Vendor layout: 213/213 pinned files, any extra file fails.
- Root layout: 208 pinned files verified plus 5 declared project-owned
  overrides (`README.md`, `.gitignore`, `.env.example`, `requirements.txt`,
  `.github/workflows/ci.yml`); project additions are allowed.

### Offline (deterministic) tests — ours

```bash
.venv/Scripts/python.exe -m pytest test/offline -m offline -q
```

These require no API keys and must pass in CI. The two unmarked stub tests
(`test_context_budget.py`, `test_termination.py`) are deselected by `-m offline`
until they are implemented; a bare `pytest` run shows them as the known failures.

### Upstream baseline unit tests

Vendor layout — run from inside the vendored directory so upstream's own pytest
config applies (`testpaths=["tests"]`, `-m "not integration"`):

```bash
cd vendor/tradingagents-0.7.x
CI=1 TRADINGAGENTS_NO_UPDATE_CHECK=1 ../../.venv/Scripts/python.exe -m pytest tests -q -m "not integration"
```

Root layout — the upstream `tests/` directory is at the repository root; select
the upstream marker explicitly (the root `pytest.ini` keeps our `offline`/`live`
markers and also declares `unit`/`integration`/`smoke`):

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
(or `.env`).

### Full suite (ours)

```bash
.venv/Scripts/python.exe -m pytest -m "offline or live"
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

> `scripts/verify_baseline.py --strict` is a clean-tree gate. The upstream
> suite creates ignored `pytest-of-*`, `tmp*` and cache droppings; run with
> `PYTHONDONTWRITEBYTECODE=1`, remove only those run droppings, then run
> `--strict`. The pinned files are never touched. In root layout the five
> declared project-owned overrides above are reported separately; the other
> 208 pinned files must match.

## 4. The real GitHub project

> TODO: Paste the URL of your actual GitHub repository when it is created.
>
> Reference upstream: https://github.com/tauricresearch/tradingagents