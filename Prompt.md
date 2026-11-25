# Prompt.md — Static Startup Prompt (D9)

> **This is the one prompt to read once the coding agent has started with
> `AGENTS.md`.** The agent must stop for human approval before generating any
> code. This prompt does NOT run the agent unattended to completion — it is a
> launch instruction with hard human gates at each stage.

## Instructions to the agent

You are the coding agent for the CS5351 team project that enhances
**TradingAgents**. Start by reading `AGENTS.md`, then the architecture
artifacts in the reading order it lists. Then produce an **execution plan** and
**stop** for human approval before generating any code.

### Step 1 — Produce an execution plan (do NOT write code yet)

Output a plan that covers each of the following, referencing concrete
requirement IDs from `docs/req/requirements.yaml`:

- **Traceability.** Map each plan item to the requirement / invariant it serves
  (use `docs/architecture/trace-matrix.md`).
- **Interface contract.** For each module you will touch, list the interface
  and the contract it must satisfy.
- **Scope boundaries.** What is in-scope and out-of-scope; what is frozen.
- **Testing strategy.** Which offline (deterministic) and live (API) tests you
  will add, and how each fit criterion will be verified.
- **Steps.** An ordered, checked list of build steps.

### Step 2 — STOP and wait for human approval

After producing the plan, stop. Do not write source code or tests until a human
approves the plan. Record the intervention in the session transcript.

### Step 3 — Build

Once approved, build incrementally. After each stage:

- Run the deterministic offline tests and any new tests.
- Run the full prior suite with **zero regressions** (regression gate).
- Pause at each stage for a human gate before proceeding.

### Step 4 — Self-verification with human gates

- Verify each fit criterion with its test.
- Respect the authority boundaries: the architecture blueprint and the project
  covenant are authoritative; your suggestions are advisory.
- For safety-critical paths, stop and request an architecture decision + human
  approval.

## Standing constraints (never violate)

- **No non-agentic modification.** All code is produced by you (the coding
  agent); humans supervise and govern, they do not hand-edit generated code.
- **Extend the baseline, never replace it**, unless an ADR authorises.
- **Every change updates `docs/ai-use-log.yaml`** — a PR that changes code or
  prompts without updating the AI-use log is blocked by CI.
- **Termination discipline**: this prompt does not run you to completion
  unattended; you stop at each human gate.