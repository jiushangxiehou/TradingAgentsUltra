# Baseline Overrides — Declared Differences on `dev`

> **Policy:** a pinned file may differ from TradingAgents 0.7.1 only if it is
> declared here and in `scripts/baseline-overrides.json` (ADR-008). The verifier
> reports declared differences and fails on undeclared ones or on stale
> declarations. Machine-readable source of truth:
> [`scripts/baseline-overrides.json`](../../scripts/baseline-overrides.json).

Pinned baseline: TradingAgents 0.7.1, commit
`9fa1196fffbcfd9de5146d2dd2869df84ab99838` (213 blobs,
[`PINNED_COMMIT.txt`](../../PINNED_COMMIT.txt)).

## Project-owned files (5)

These five differ on every layout by design; they are the project's own files
that happen to have baseline names.

## Declared dev overrides (19)

Every entry below changes a pinned file so that a requirement is actually
enforced at the call site the runtime uses. The owner is a person, not a
branch: the feature branch is history, the responsibility is not.

| Pinned file | Owner | Requirement | Why it differs | Commit |
|---|---|---|---|---|
| `README.md` | CUI Haoyu (60760270) | project-owned | Deliverable instructions and gate status | `ADR-008` |
| `.gitignore` | CUI Haoyu (60760270) | project-owned | Local environment/artifacts ignored | `ADR-008` |
| `.env.example` | CUI Haoyu (60760270) | project-owned | CS5351 defaults block (debate_*, context_input_*) | `ADR-008` |
| `requirements.txt` | CUI Haoyu (60760270) | project-owned | Flattened deps + gate tooling (mypy) | `ADR-008` |
| `.github/workflows/ci.yml` | CUI Haoyu (60760270) | project-owned | Six blocking gates | `ADR-008` |
| `tradingagents/agents/researchers/bull_researcher.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Structured debate turn | `a871245` |
| `tradingagents/agents/researchers/bear_researcher.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Structured debate turn | `a871245` |
| `tradingagents/agents/risk_mgmt/aggressive_debator.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Risk debate turn | `a871245` |
| `tradingagents/agents/risk_mgmt/conservative_debator.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Risk debate turn | `a871245` |
| `tradingagents/agents/risk_mgmt/neutral_debator.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Risk debate turn | `a871245` |
| `tradingagents/agents/managers/research_manager.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Reads debate record | `a871245` |
| `tradingagents/agents/managers/portfolio_manager.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Preserves debate state | `a871245` |
| `tradingagents/agents/state.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Additive debate fields | `a871245` |
| `tradingagents/graph/conditional_logic.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Content-based early routing | `a871245` |
| `tradingagents/graph/propagation.py` | Fan Hao (60835652) | REQ-STRUCTURED-DEBATE | Debate state into run state | `a871245` |
| `tradingagents/agents/analysts/turn.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | Budgeted analyst turn | `3313ad0` |
| `tradingagents/agents/analysts/sentiment_analyst.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | Budgeted structured path | `3313ad0` |
| `tradingagents/agents/post_screen.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | Skip optional pre-screen when budgeting | `3313ad0` |
| `tradingagents/agents/structured.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | Structured output through the boundary | `3313ad0` |
| `tradingagents/memory/reflection.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | Budgeted reflection request | `3313ad0` |
| `tradingagents/llm_clients/factory.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | CityU adapter installation | `7de8935` |
| `tradingagents/graph/trading_graph.py` | ZhuXuan (60377218) | REQ-CONTEXT-BUDGET | Budgeted model boundary | `a9d23ec` |
| `tradingagents/default_config.py` | ZhuXuan (60377218) + Fan Hao (60835652) | CONTEXT-BUDGET / STRUCTURED-DEBATE | Config keys for both features | `a9d23ec` |
| `tradingagents/graph/setup.py` | CUI Haoyu (60760270) | REQ-TERMINATION-DISCIPLINE | Termination wiring | `3f727bb` |

## What this declaration does not claim

- It does not claim the modified files are small, ideal or final. It claims each
  difference is intentional, owned and reviewable.
- It does not freeze the set: restoring a file means deleting its declaration;
  `--strict` fails on a declaration that no longer describes a difference.
- It does not replace `pytest`: the offline suite and the full-graph end-to-end
  tests are what show the modified call sites still behave.

## Verify

```bash
python scripts/verify_baseline.py --strict
# layout       : root
# pinned files : 213
# project-owned: 5 declared
# dev overrides: 19 declared, 0 unused
# undeclared   : 0
# baseline-verify: PASS (pinned baseline matches; declared differences only)
```
