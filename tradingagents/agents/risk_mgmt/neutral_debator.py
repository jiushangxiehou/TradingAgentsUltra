from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
    get_portfolio_context_from_state,
    opponent_argument_or_opening,
    report_or_absent,
)
from tradingagents.dataflows.config import get_config
from tradingagents.debate.engine import (
    bind_debate_turn,
    debate_audits,
    evaluate_termination,
    render_prior_turns,
    run_debate_turn,
)
from tradingagents.debate.evidence import build_evidence_registry, render_evidence_catalog


def create_neutral_debator(llm):
    structured_llm = bind_debate_turn(llm, "Neutral Risk Analyst")

    def neutral_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        neutral_history = risk_debate_state.get("neutral_history", "")
        previous_audits = debate_audits(risk_debate_state)
        evidence = build_evidence_registry(state)
        round_number = risk_debate_state["count"] // 3 + 1

        current_aggressive_response = opponent_argument_or_opening(
            risk_debate_state.get("current_aggressive_response", ""), "aggressive analyst"
        )
        current_conservative_response = opponent_argument_or_opening(
            risk_debate_state.get("current_conservative_response", ""), "conservative analyst"
        )

        market_research_report = report_or_absent(state["market_report"], "market")
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment")
        news_report = report_or_absent(state["news_report"], "news")
        fundamentals_report = report_or_absent(state["fundamentals_report"], "fundamentals")
        instrument_context = get_instrument_context_from_state(state)
        portfolio_context = get_portfolio_context_from_state(state)

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Neutral Risk Analyst, your role is to provide a balanced perspective, weighing both the potential benefits and risks of the trader's decision or plan. You prioritize a well-rounded approach, evaluating the upsides and downsides while factoring in broader market trends, potential economic shifts, and diversification strategies.Here is the trader's decision:

{trader_decision}

Your task is to challenge both the Aggressive and Conservative Analysts, pointing out where each perspective may be overly optimistic or overly cautious. Use insights from the following data sources to support a moderate, sustainable strategy to adjust the trader's decision:

{instrument_context}
{portfolio_context}
Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the conservative analyst: {current_conservative_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

## Evidence catalog
Use only these evidence IDs in claim and rebuttal `evidence_refs`.
{render_evidence_catalog(evidence)}

## Structured turn requirement
Return one DebateTurn with round, speaker, stance, thesis, claims, rebuttals,
concessions, open_questions, changed_position, and confidence.
Rebuttal targets must refer only to claim IDs in the recent validated turns.
Do not invent claim or evidence IDs.

## Recent validated turns
{render_prior_turns(previous_audits)}

Engage actively by analyzing both sides critically, addressing weaknesses in the aggressive and conservative arguments to advocate for a more balanced approach. Challenge each of their points to illustrate why a moderate risk strategy might offer the best of both worlds, providing growth potential while safeguarding against extreme volatility. Focus on debating rather than simply presenting data, aiming to show that a balanced view can lead to the most reliable outcomes. Output conversationally as if you are speaking without any special formatting.""" + get_language_instruction()

        audit, rendered = run_debate_turn(
            structured_llm=structured_llm,
            plain_llm=llm,
            prompt=prompt,
            speaker="Neutral Analyst",
            round_number=round_number,
            sequence=risk_debate_state["count"] + 1,
            debate_state=risk_debate_state,
            evidence=evidence,
        )
        next_audits = previous_audits + [audit]
        config = get_config()
        termination = evaluate_termination(
            debate_type="risk",
            audits=next_audits,
            participants=3,
            max_rounds=max(1, int(config["max_risk_discuss_rounds"])),
            config=config,
        )
        summary = audit.turn.thesis if audit.turn is not None else audit.raw_output[:500]
        argument = f"Neutral Analyst: {summary}"

        new_risk_debate_state = {
            "history": (history + "\n\n" + rendered).strip(),
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": risk_debate_state.get("conservative_history", ""),
            "neutral_history": (neutral_history + "\n\n" + rendered).strip(),
            "latest_speaker": "Neutral",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": risk_debate_state.get("current_conservative_response", ""),
            "current_neutral_response": argument,
            "count": risk_debate_state["count"] + 1,
            "turns": [item.model_dump(mode="json") for item in next_audits],
            "metrics": termination.metrics,
            "termination": termination.model_dump(mode="json"),
        }

        return {"risk_debate_state": new_risk_debate_state}

    return neutral_node
