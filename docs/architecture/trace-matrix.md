# Trace Matrix

> Requirement → enforcing component → test/evidence → runtime monitor.

| Requirement | Enforcing component | Test / evidence | Runtime monitor |
|-------------|---------------------|-----------------|-----------------|
| REQ-CONTEXT-BUDGET | `ContextAssembler` | offline test: tokens ≤ budget | per-call token instrumentation |
| REQ-STRUCTURED-DEBATE | `StructuredDebater` | offline test: schema validation 100% | turn schema validator |
| REQ-TRACEABILITY | `TraceRecorder` + `src/integration/trace_adapter.py` | offline tests: link auditor resolves all; `test_integration_trace.py`; `test_integration_end_to_end.py` (real scripted graph) | `guardrail_trace_<date>.json` sidecar; `traceable`/`checked_links`/`findings` |
| REQ-HARD-GUARDRAIL | `Guardrail` + `src/integration/governed_graph.py` | offline tests: zero adversarial escapes; `test_integration_graph.py`; `test_integration_end_to_end.py` (pass, oversize, missing intent) | `guardrail` audit payload; audit record; memory-log rating |
| REQ-TERMINATION-DISCIPLINE | `TerminationController` | offline test: repeats ≥ τ terminates | termination trigger log |

(TODO: map every requirement from docs/req/requirements.yaml here. This table is a seed.)