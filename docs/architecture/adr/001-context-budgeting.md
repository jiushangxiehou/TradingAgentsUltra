# ADR-001: Context Budgeting and Compaction

- **Status:** Proposed
- **Decision owner:** (fill in)
- **Date:** (fill in)

## Context
The baseline TradingAgents agents re-send full research reports and the entire
debate history on every invocation, so context grows unbounded and token burn
is high.

## Decision
Adopt a `ContextAssembler` that enforces a per-agent token budget and compacts
context (deduplicate → prioritise → budget → compact) above a compaction
threshold before injection. Defaults: budget 8000 tokens, compaction threshold
6000.

## Alternatives considered
- No budgeting (baseline) — simplest but unbounded token growth.
- Hard truncation of history — cheap but loses constraints.

## Consequences
- Lower token consumption; supports REQ-CONTEXT-BUDGET.
- Risk of losing detail; mitigated by a re-injection test and a quality
  acceptability bound.

## Reopen conditions
A measured quality drop (faithfulness) above the bound suggests the compaction
is too aggressive; revisit thresholds or the pipeline.

## Architectural design process
(Describe the ADD iteration that led here: drivers → candidate → selection →
consequence.) — TODO.