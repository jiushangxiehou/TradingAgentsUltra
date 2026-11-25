# Architecture Blueprint — Master Constraint Document (D2.1)

> **This is the master constraint document the Plan agent reads.** It is
> authoritative over the coding agent's scope, boundaries, components,
> authority, permissions, verification, observability, and change policy. If
> any other artifact conflicts with this, this blueprint — and the project
> covenant (`.agent/rules.md`) — wins, and the agent must stop and surface the
> conflict.

## 1. Scope

- **System:** TradingAgents, a LangGraph multi-agent LLM financial trading
  framework, enhanced per the five requirements in `docs/req/requirements.yaml`.
- **In-scope:** the agent pipeline (analysts → researchers → trader → risk
  debators → portfolio manager), the context assembly, the decision guardrail,
  trace recording, and termination discipline.
- **Out-of-scope:** the upstream baseline's unaffected modules, the live data
  providers' internal detail, and anything an ADR marks out of scope.
- **Not to be extended:** the VHIS reference implementation (pattern only).

## 2. Architectural drivers

1. Token cost is high (baseline agents re-send full reports + full history on
   every invocation) → require context budgeting and compaction.
2. Agent debate is unstructured and bounded only by round count → require a
   structured, convergible debate.
3. Decisions are not auditable to their evidence → require an evidence chain.
4. AI decisions are not hard-checked before execution → require a
   deterministic safety boundary (zero tolerance).
5. Agent loops can stall or repeat without bound → require self-termination.

## 3. System boundaries

- **Boundary outside:** LLM providers, data vendors (yfinance, FRED, SEC EDGAR,
  Polymarket), the simulated exchange. These are reached through `tools.py`.
- **Boundary inside (our code):** `src/` modules, the process orchestrator
  (LangGraph), the guardrail, the trace recorder, the context assembler.
- **Human boundary:** humans supervise, approve plans, review PRs, and enforce
  the project covenant. They do NOT hand-edit generated code.

## 4. Components

| Component | Responsibility | Satisfies |
|-----------|----------------|-----------|
| `ContextAssembler` | budget + compact context per agent call | REQ-CONTEXT-BUDGET |
| `StructuredDebater` | schema-validated, convergible bull/bear turns | REQ-STRUCTURED-DEBATE |
| `TraceRecorder` | assertion → evidence snapshot links | REQ-TRACEABILITY |
| `Guardrail` | deterministic decision hard-check | REQ-HARD-GUARDRAIL |
| `TerminationController` | self-stop on stall/repeat/budget | REQ-TERMINATION-DISCIPLINE |

See `docs/architecture/trace-matrix.md` for the requirement → component mapping
and `docs/code-governance/structural-constraints.md` for module rules.

## 5. Authority boundaries (advisory vs authoritative)

- **Advisory:** the coding agent's suggestions, the agents' free-form prose,
  config defaults the team has not decided.
- **Authoritative:** `architecture-blueprint.md`, `AGENTS.md`, `.agent/rules.md`
  (project covenant), `docs/code-governance/*`, the invariants, and ADRs.
- When advisory conflicts with authoritative, the authoritative artifact wins
  and the agent must **stop and surface** the conflict rather than proceed.
- Changing safety-critical paths requires an architecture decision + human
  approval.

## 6. Agent workflow

1. Analysts (market / social / news / fundamentals) run in parallel, each on
   its own graph with a bounded tool-call round budget.
2. Bull & Bear researchers debate under `StructuredDebater`; the debate
   converges or hits the round cap.
3. Trader composes a plan.
4. Aggressive / Conservative / Neutral risk debators discuss; Portfolio
   Manager gives the final 5-tier decision.
5. `Guardrail` hard-checks the decision before it can reach execution.
6. `TraceRecorder` records the evidence chain.
7. The run's decision is logged to the memory log.

## 7. Permissions

- Each AI coding agent role has file-level read/write rights; the default is
  **no read, no write**; every path is explicitly whitelisted. See
  `docs/architecture/permission-model.md` and `.opencode/permissions.jsonc`.

## 8. Verification strategy

- **Structural:** imports, module boundaries, permissions, architectural
  fitness functions.
- **Regression:** all prior suites pass with zero regressions.
- **Behavioral:** quality thresholds (faithfulness / relevancy ≥ 0.6 for the
  AI-generated explanation layer; zero safety escapes past the guardrail).
- See `docs/code-governance/verification-constraints.md` and the CI gates in
  `.github/workflows/ci.yml`.

## 9. Observability

- Every run records `run_settings`, the report tree, the final state JSON, and
  the memory-log entry.
- The trace recorder exposes the evidence chain for auditability.
- A live run that fails to settle past decisions is still recorded, and the
  report says so (the run does not fail on a settle failure).

## 10. Change policy

- Non-safety-relevant changes: PR + review + CI gates.
- Safety-relevant changes (guardrail, invariants, the trust boundary): require
  an architecture decision (ADR) and human approval, plus a blocking test that
  fails if the invariant is violated.
- Requirements change: update `.agent/rules.md` (context freshness) within one
  sprint, plus the trace matrix and any affected ADR.
- Fixing a produced defect: log a `docs/bug-diary.md` entry; if it exposes an
  invariant gap, update the invariant register and add a regression test.