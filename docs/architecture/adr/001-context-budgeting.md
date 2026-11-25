# ADR-001: Context Budgeting and Compaction

- **Status:** Proposed
- **Decision owner:** (fill in)
- **Date:** (fill in)
- **Review:** implementation documented below; decision owner, approval and date await human confirmation.

## Context
The baseline TradingAgents agents re-send full research reports and the entire
debate history on every invocation, so context grows unbounded and token burn
is high.

## Decision
Install the opt-in model boundary at [Graph construction](../../../tradingagents/graph/trading_graph.py)
and [agent setup](../../../tradingagents/graph/setup.py). The implementation is
[BudgetedModel](../../../tradingagents/graph/budgeted_model.py) and
[budget_and_send](../../../tradingagents/graph/context_budget.py).
`ContextAssembler` was a design name; `src/context_assembler.py` remains a
placeholder on merged dev and is outside this runtime path.

### Context layers

| Layer | Runtime treatment |
|---|---|
| Identity, standing rules and current task | System/User turns stay verbatim as anchors in their original roles and order. Existing prompts retain instrument, ticker, asset type, trade date, portfolio presence and applicable rating/risk rules. Anchors are carried into the rebuilt request once. |
| Retrieved evidence | Existing tools and data sources retrieve the evidence. Full tool-call/result blocks are paired by ID and retain source and timing metadata. Where provenance is absent, the upstream as-of query remains the boundary. |
| Conversation and resumable state | Agent history stays scoped to the node; checkpoint compatibility includes the configured budget and counter identity. Memory retrieval continues to use the original historical as-of rules. |
| Request schema and protocol | Tool or structured-output schemas are in the adapter's final body. The existing wrap-up path projects the validated tool history into text when no tools are bound. |

### Assembly, compaction and sending

1. Validate tool calls and results by ID, including raw and normalized names and
   arguments. Reject missing, orphaned, duplicate or conflicting records.
   Validate explicit `available_at` before preparing a request. Resolve conflicting
   dates to the later instant. Filter future evidence, using a paired placeholder
   when keeping an available assistant message requires the tool result slot.
   Keep `event_date` separate from availability; UTC offsets are honored.
2. Count the prepared request. The hard cap and compaction threshold are
   independent positive integer settings, with threshold at most the cap.
   Both settings default to `None`; budgets of 8000/6000 are examples only.
   At or below the threshold, reuse the already counted request.
3. Above the threshold, perform one deterministic pass. Deduplicate equivalent
   complete exchanges within a user turn. Preserve anchors, meaningful assistant
   text and independent evidence. Trim only explicitly disposable blocks when
   needed, then extract verbatim, source-labelled facts from eligible
   low-priority results; unannotated prose is retained conservatively. Source,
   ticker, dates, amount and causality remain tied to the retained evidence.
4. Prepare and count the final payload again. An invalid count, an unavailable
   adapter, or a final count above the hard cap stops the model request.
   Over-cap mandatory content cannot be discarded to make the request fit.
5. Use the [CityU adapter](../../../tradingagents/llm_clients/deepseek_context_adapter.py)
   for the existing supported CityU model and endpoint. Its local estimate
   counts the UTF-8 bytes of the complete frozen JSON, including schemas and
   reasoning fields present in the request. It reports `local_token_estimate`
   with `counter_exact=false`. The one-time permission binds adapter, object
   and bytes; the SDK sends those bytes unchanged with transport retries
   disabled. Post-response `usage.prompt_tokens` is separate provider evidence.

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
The observed driver was repeated evidence and history on every model turn.
The implemented design uses explicit request guards and deterministic
compaction to keep exact prompt constraints and permit reproducible tests.
The alternatives above remain the reference trade-off. No additional decision
meeting or sign-off is asserted here.

## Verification evidence

Use the [trace matrix](../trace-matrix.md) and [acceptance report](../../req-context-budget-acceptance.md).
On merged dev `a8597af236bbedaa862d7a3a3c1a7d0d2a9984ae`, 73 core cases and
18 integration cases passed. The paired fixture retained 2/2 facts and 5/5
constraints. SDK Mock HTTP proves the local budget and transport boundary;
real CityU token parity and actual model-output quality remain unverified.