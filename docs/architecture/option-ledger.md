# Option Ledger (optional)

> Rejected architectural options and the conditions to reconsider them.

| Rejected option | Why rejected | Reconsider when |
|-----------------|--------------|-----------------|
| Hard truncate context | Loses standing constraints | Compaction too complex |
| Soft prompt-based boundary | Not deterministically enforced | Guardrail rejected too many legit decisions |
| No termination discipline | Deadlock-prone | Loops shown to converge reliably |
| Per-token full provenance | Too heavy | Audit demands exceed chain granularity |