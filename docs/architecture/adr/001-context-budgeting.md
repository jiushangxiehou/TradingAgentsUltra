# ADR-001: Context Budgeting and Compaction

- **Status:** Accepted
- **Decision owner:** feature-z owner (to confirm)
- **Date:** 2026-11-25

## Context
The baseline TradingAgents agents re-send full research reports and the entire
debate history on every invocation, so context grows unbounded and token burn
is high.

## Decision
Adopt a `ContextAssembler` that enforces a per-agent token budget and compacts
context (deduplicate → prioritise → budget → compact) above a compaction
threshold before injection. Defaults: budget 8000 tokens, compaction threshold
6000.

### Layered context and assembly pipeline (implementation view)

The dev implementation in `tradingagents/graph/context_budget.py` and
`budgeted_model.py` materialises the context as paired blocks rather than a flat
string:

| Layer | Representation in the implementation | Treatment |
|---|---|---|
| Identity / role | system messages; `group_into_blocks` marks system/human blocks `anchor=True` | Never disposable; retained through compaction |
| Long-term constraints | system prompt and instrument context | Anchored; not summarized away |
| Retrieved knowledge | tool-call/result blocks, including provenance and `relevance` metadata | Deduplicated, future-filtered, summarized and trimmed only when disposable |
| Conversation history | assistant text blocks; blocks with assistant text are non-disposable | Kept unless the cap forces a disposable-evidence cut |
| Recoverable state | tool results and compacted summaries | `_summarize_blocks` replaces large results; the original state is still in the graph/history |
| Current task | latest human message | Anchored; retained |

The assembly pipeline is:

```text
group_into_blocks
  → _dedup_blocks            (equivalent exchanges collapse)
  → _filter_explicit_future  (point-in-time filter)
  → _summarize_blocks        (large tool results become summaries)
  → _trim_to_cap             (remove disposable evidence only)
  → budget_and_send          (authorize the send; block if over/unknown)
```

The configured caps are `context_input_hard_cap_tokens` and
`context_input_compaction_threshold_tokens`; when unset, budgeting is disabled.
The ADR's reference defaults are 8,000/6,000 tokens. Compaction retains anchored
blocks and the current task; the runtime policy catalog records compaction and
re-injection warnings rather than silently dropping a constraint. The
implementation does not re-create a separate “constraint” message; it preserves
the anchored block, which is the safer form of re-injection.

> **CUI Haoyu note:** this section is reconstructed from the dev code; the
> feature-z owner should confirm the final module placement and defaults.

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

The ADD iteration started from the token-cost driver and the baseline's habit of
re-sending full reports and debate history. Candidates were no budgeting (cheap
but unbounded), hard truncation (cheap but loses constraints), and a layered
assembly with dedup/priority/compaction (selected). The dev implementation adds
point-in-time filtering, paired tool blocks, a disposable-evidence budget cut,
and a provider-adapter check so an unsupported count blocks the call instead of
sending an unverified request. The consequence is bounded cost with an explicit
quality risk; the reopen condition is a measured faithfulness drop or a budget
that blocks legitimate calls.