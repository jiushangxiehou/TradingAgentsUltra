# Runtime Policy Catalog

> What the system does when each degraded / failure path is triggered.

| Trigger | System behaviour |
|---------|------------------|
| Guardrail rejects a decision | Route to REVIEW/HOLD, log audit record, do not execute |
| Past decisions cannot be settled this run | Run continues; report states what stayed pending |
| Memory log cannot be read | Run continues; past_context empty; report notes it |
| Compaction threshold exceeded | Compact context, re-inject, log re-injection warning |
| Debate repeats ≥ τ | Terminate loop, log trigger, use last valid turn |
| Analyst exceeds max tool rounds | Asked for its report (wrap_up), run continues |
| LLM provider throttled | Retry budget (`llm_max_retries`); abort only at cap |
| Live API test fails on data vendor | Test reports; point-in-time guard against look-ahead |