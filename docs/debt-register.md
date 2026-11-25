# Debt Register (D4)

> Technical debt tracked across AI-era categories: prompt rot, hallucinated
> dependencies, untouchable code, hidden dependencies, agent-induced bloat,
> evaluation debt, guardrail debt, and human/cognitive debt.

| Category | Debt | Where | Severity | Mentor | Mitigation |
|----------|------|-------|----------|--------|------------|
| Prompt rot | (e.g. prompt no longer matched by updated schema) | prompts/ | M/L | — | semantic eval gate; bump version |
| Hallucinated deps | (a dep the agent assumed but doesn't exist) | — | M/L | — | lint + dependency check gate |
| Untouchable code | (code nobody dares change) | — | H | — | ADR + regression coverage |
| Hidden dependencies | (implicit coupling) | — | M | — | structural fitness check |
| Agent-induced bloat | (duplicated / over-abstracted code) | — | M | — | review memo; simplify |
| Evaluation debt | (missing tests / stale eval set) | test/ | H | — | verification-constraints.md |
| Guardrail debt | (guardrail gap / weak limit) | src/guardrail.py | H | — | invariant zero-escape test |
| Human/cognitive debt | (process knowledge not written down) | — | M | — | ADRs, review memos, transcripts |

(TODO: populate as debts are discovered. New rows as they arise.)