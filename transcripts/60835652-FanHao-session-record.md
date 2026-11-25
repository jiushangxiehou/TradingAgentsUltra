> **D5 record — Fan Hao (60835652).** This is the record the owner supplied
> for the REQ-STRUCTURED-DEBATE work. It is a retrospective reconstruction,
> not a verbatim OpenCode export (the record states this in its own header
> below); it is reproduced in Part B of `D5-team-session-transcripts.md`.
> The raw session export is still owed and is tracked in the debt register.

# Structured Debate and Termination: Key Session Records

> This document is a retrospective reconstruction of the development process.
> The user prompts are rephrased from the actual discussion, and the assistant
> responses are condensed. It is not a verbatim transcript.

## 1. Session Overview

| No. | Key topic | Main outcome |
|---:|---|---|
| 1 | Why the baseline debate is not sufficiently structured | Identified free-text turns, round caps, and missing termination reasons |
| 2 | Scope of a structured debate | Defined Turn, Claim, Evidence, and Rebuttal |
| 3 | Debate quality validation | Defined Schema, evidence, and rebuttal-target checks |
| 4 | Evidence-reference system | Created stable Evidence IDs |
| 5 | Termination design | Defined max-round, convergence, repetition, and Schema-failure codes |
| 6 | Convergence detection | Defined complete cycles, no new claims, and stable stances |
| 7 | Preserving baseline behavior | Introduced Shadow Mode |
| 8 | Graph integration | Updated five debaters, state, routing, and managers |
| 9 | Verification | Added focused tests and ran regressions |
| 10 | Visible effects | State JSON, structured reports, and actual round counts |

---

## Session 1: Is the baseline debate structured?

### User

> What structured debate and termination support does the original program
> actually have?

### Assistant

The baseline has structured debate **state**, but the debate content itself is
free text.

The Bull/Bear and risk analysts originally returned prose such as:

```text
Bull Analyst: ...
Bear Analyst: ...
```

That prose was appended to string fields such as `history`, `bull_history`,
and `bear_history`.

The original router depended on:

```text
count
current_response.startswith("Bull")
latest_speaker.startswith("Aggressive")
max_debate_rounds
max_risk_discuss_rounds
```

The baseline therefore had no:

- Claim IDs
- Evidence IDs
- Rebuttal target references
- Schema-validity rate
- Evidence coverage
- Convergence detection
- Content-driven early termination

Conclusion: the original system had structured state, but not a structured
debate protocol or a content-based termination mechanism.

---

## Session 2: What should each debate turn contain?

### User

> What should each agent output if I want to optimize the debate?

### Assistant

Define a `DebateTurn` protocol:

```text
round
speaker
stance
thesis
claims[]
rebuttals[]
concessions[]
open_questions[]
changed_position
confidence
```

Each Claim should contain:

```text
claim_id
statement
evidence_refs[]
confidence
```

Each Rebuttal should contain:

```text
target_claim_id
argument
evidence_refs[]
```

This preserves natural-language reasoning while allowing deterministic checks:

- Are claims duplicated?
- Do cited evidence IDs exist?
- Does a rebuttal target a real historical claim?
- Did a participant change position?
- Is the debate still producing new information?

---

## Session 3: How should debate quality be validated?

### User

> If the model says its output is structured, why should I trust it?

### Assistant

Never trust a model-generated `schema_valid` field. Validate the output in the
backend:

```text
1. Validate with the Pydantic schema.
2. Check whether every Evidence ID exists.
3. Check whether every rebuttal target exists in prior claims.
4. Reject duplicate Claim IDs.
5. Detect repeated claims.
6. Calculate Schema, evidence, and rebuttal coverage.
```

If the provider does not support structured output, the system may fall back
to free text, but it must record:

```text
schema_valid = false
```

Free text must never be silently labeled as a successful structured turn.

The resulting metrics are:

```text
schema_validity_rate
evidence_coverage
rebuttal_coverage
new_claim_count
claim_count
rebuttal_count
turn_count
```

---

## Session 4: How should evidence references work?

### User

> The debate says "according to the news" or "according to the financials."
> That is too vague. How can evidence become traceable?

### Assistant

Generate stable evidence IDs from the source material:

```text
market_report          → market:m1, market:m2, ...
sentiment_report       → sentiment:s1, ...
news_report            → news:n1, ...
fundamentals_report    → fundamentals:f1, ...
trader_investment_plan → trader:t1, ...
```

The debate prompt receives an evidence catalog. Claims and rebuttals may cite
only IDs from that catalog.

Example:

```json
{
  "claim_id": "bull-r1-c1",
  "statement": "The trend remains constructive.",
  "evidence_refs": ["market:m1"],
  "confidence": "medium"
}
```

The backend does not trust model-authored Claim IDs. It assigns deterministic
IDs:

```text
bull-r1-c1
bear-r2-c3
aggressive-r1-c2
```

Later rebuttals can then reference those claims precisely.

---

## Session 5: What conditions should terminate a debate?

### User

> The baseline only stops at a maximum round count. I want more meaningful
> termination conditions.

### Assistant

Implement at least these termination codes:

```text
MAX_ROUNDS_REACHED
CONSENSUS_REACHED
NO_NEW_CLAIMS
SCHEMA_FAILURE
CONTINUE
```

Evaluate termination only after a complete debate cycle:

- Research Debate: both Bull and Bear have spoken in the current round.
- Risk Debate: Aggressive, Conservative, and Neutral have all spoken.

Maximum rounds always terminate the loop so it cannot run indefinitely.

Every early termination should record:

- termination code
- human-readable reason
- completed rounds
- whether termination was recommended
- whether it was effective
- whether Shadow Mode was active
- a metrics snapshot

---

## Session 6: How do we know viewpoints have converged?

### User

> A model saying "I agree" does not necessarily mean the debate has converged.
> How should convergence be detected?

### Assistant

Do not rely on a model simply saying that it agrees. Use deterministic rules:

```text
a configurable number of complete cycles
+ no new claims
+ stable stance for every participant
+ no participant sets changed_position=true
+ minimum round count reached
```

The default evaluation window is two complete cycles.

When all conditions hold, record:

```text
CONSENSUS_REACHED
```

When there are no new claims but participant positions changed, record:

```text
NO_NEW_CLAIMS
```

This is more stable and testable than allowing a debate agent to declare
convergence by itself.

---

## Session 7: How can we avoid changing baseline behavior immediately?

### User

> Early termination could stop a useful debate too soon. How can we observe it
> before enabling it?

### Assistant

Introduce Shadow Mode:

```text
debate_early_termination = false
debate_shadow_mode = true
```

In Shadow Mode:

- the termination policy still evaluates every complete cycle;
- the system records when it would have stopped;
- the actual run continues to the original maximum round count.

After the recommendations have been evaluated, enable real termination:

```dotenv
TRADINGAGENTS_DEBATE_EARLY_TERMINATION=true
TRADINGAGENTS_DEBATE_SHADOW_MODE=false
```

This preserves baseline behavior by default while collecting evidence for
calibration.

---

## Session 8: How should the feature be integrated into the graph?

### User

> Do not rewrite the whole pipeline. Add structured debate and termination to
> the five existing debaters.

### Assistant

Use an incremental extension that preserves the original free-text history.

The modified debate nodes are:

```text
Bull Researcher
Bear Researcher
Aggressive Analyst
Conservative Analyst
Neutral Analyst
```

Each node now:

1. Builds the evidence registry.
2. Attempts structured output.
3. Validates claims, evidence, and rebuttal targets.
4. Appends a `TurnAudit`.
5. Calculates debate metrics.
6. Runs the termination policy.
7. Writes compatible Markdown history.

The debate state now contains:

```text
turns
metrics
termination
```

The router checks:

```python
termination.get("effective")
```

Only an effective termination can route early to the Research Manager or
Portfolio Manager.

---

## Session 9: How can we prove there are no regressions?

### User

> Could the new fields and routing break parallel analysts, reports, or the CLI?

### Assistant

Verification is divided into three groups.

### Focused tests

Cover:

- stable Evidence IDs
- normalized Claim IDs
- invalid Evidence detection
- invalid Rebuttal detection
- Shadow Mode
- effective early termination
- maximum-round termination
- structured-turn persistence

### Existing regression tests

Run at least:

```text
test_debate_opening.py
test_risk_router_path_map.py
test_graph_end_to_end.py
test_prompt_integrity.py
test_structured_agent_prompts.py
```

### Static checks

```cmd
.venv\Scripts\ruff.exe check --no-cache .
```

The implementation must preserve:

- existing prompt constraints
- maximum-round termination
- graceful free-text fallback
- parallel analyst execution
- Memory Log behavior
- report generation

---

## Session 10: Where can the optimization be observed after a run?

### User

> After one analysis, where can I clearly see that structured debate and
> termination produced an effect?

### Assistant

Inspect three places.

### 1. Structured debate reports

Open:

```text
2_research/bull.md
2_research/bear.md
4_risk/aggressive.md
4_risk/conservative.md
4_risk/neutral.md
```

They expose:

```text
Round
Stance
Thesis
Claim ID
Evidence ID
Rebuttal target
Concessions
Open Questions
Changed Position
Confidence
```

### 2. Final state JSON

Open:

```text
full_states_log_<date>.json
```

Read:

```text
investment_debate_state.turns
investment_debate_state.metrics
investment_debate_state.termination

risk_debate_state.turns
risk_debate_state.metrics
risk_debate_state.termination
```

Example:

```json
{
  "metrics": {
    "turn_count": 4,
    "schema_validity_rate": 1.0,
    "evidence_coverage": 0.85,
    "rebuttal_coverage": 0.75,
    "new_claim_count": 0
  },
  "termination": {
    "code": "CONSENSUS_REACHED",
    "effective": true,
    "shadow_mode": false,
    "after_round": 2
  }
}
```

### 3. Round-count comparison

With three configured Research Debate rounds, the maximum is:

```text
3 × 2 = 6 turns
```

Convergence after round two produces:

```text
2 × 2 = 4 turns
```

With three configured Risk Debate rounds, the maximum is:

```text
3 × 3 = 9 turns
```

Convergence after round two produces:

```text
2 × 3 = 6 turns
```

An actual count below the configured maximum, together with a termination code
other than `MAX_ROUNDS_REACHED`, is direct evidence that early termination
worked.

---

## Requirement-to-Implementation Map

| Feature | Main implementation | Verification evidence |
|---|---|---|
| Structured debate protocol | `tradingagents/debate/schemas.py` | Turn, Claim, and Rebuttal schemas |
| Evidence-reference system | `tradingagents/debate/evidence.py` | Stable Evidence IDs |
| Quality validator | `tradingagents/debate/engine.py` | Schema/Evidence/Rebuttal checks |
| Termination mechanism | `evaluate_termination()` and routing | TerminationDecision |
| Convergence detection | Complete cycles, no new claims, stable stances | CONSENSUS_REACHED |
| Compatibility | Existing history and five-tier rating retained | Regression tests |
| Observability | State JSON and structured reports | turns/metrics/termination |

## Related Files

```text
tradingagents/debate/__init__.py
tradingagents/debate/schemas.py
tradingagents/debate/evidence.py
tradingagents/debate/engine.py
tradingagents/agents/state.py
tradingagents/agents/researchers/bull_researcher.py
tradingagents/agents/researchers/bear_researcher.py
tradingagents/agents/risk_mgmt/aggressive_debator.py
tradingagents/agents/risk_mgmt/conservative_debator.py
tradingagents/agents/risk_mgmt/neutral_debator.py
tradingagents/agents/managers/research_manager.py
tradingagents/agents/managers/portfolio_manager.py
tradingagents/graph/conditional_logic.py
tradingagents/graph/propagation.py
tradingagents/graph/trading_graph.py
tradingagents/default_config.py
tests/test_debate_structured.py
docs/structured-debate.md
```
