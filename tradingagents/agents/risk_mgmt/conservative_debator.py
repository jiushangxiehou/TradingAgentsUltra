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


def create_conservative_debator(llm):
    structured_llm = bind_debate_turn(llm, "Conservative Risk Analyst")

    def conservative_node(state) -> dict:
        risk_debate_state = state["risk_debate_state"]
        history = risk_debate_state.get("history", "")
        conservative_history = risk_debate_state.get("conservative_history", "")
        previous_audits = debate_audits(risk_debate_state)
        evidence = build_evidence_registry(state)
        round_number = risk_debate_state["count"] // 3 + 1

        current_aggressive_response = opponent_argument_or_opening(
            risk_debate_state.get("current_aggressive_response", ""), "aggressive analyst"
        )
        current_neutral_response = opponent_argument_or_opening(
            risk_debate_state.get("current_neutral_response", ""), "neutral analyst"
        )

        market_research_report = report_or_absent(state["market_report"], "market")
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment")
        news_report = report_or_absent(state["news_report"], "news")
        fundamentals_report = report_or_absent(state["fundamentals_report"], "fundamentals")
        instrument_context = get_instrument_context_from_state(state)
        portfolio_context = get_portfolio_context_from_state(state)

        trader_decision = state["trader_investment_plan"]

        prompt = f"""As the Conservative Risk Analyst, your primary objective is to protect assets, minimize volatility, and ensure steady, reliable growth. You prioritize stability, security, and risk mitigation, carefully assessing potential losses, economic downturns, and market volatility. When evaluating the trader's decision or plan, critically examine high-risk elements, pointing out where the decision may expose the firm to undue risk and where more cautious alternatives could secure long-term gains. Here is the trader's decision:

{trader_decision}

Your task is to actively counter the arguments of the Aggressive and Neutral Analysts, highlighting where their views may overlook potential threats or fail to prioritize sustainability. Respond directly to their points, drawing from the following data sources to build a convincing case for a low-risk approach adjustment to the trader's decision:

{instrument_context}
{portfolio_context}
Market Research Report: {market_research_report}
Social Media Sentiment Report: {sentiment_report}
Latest World Affairs Report: {news_report}
Company Fundamentals Report: {fundamentals_report}
Here is the current conversation history: {history} Here is the last response from the aggressive analyst: {current_aggressive_response} Here is the last response from the neutral analyst: {current_neutral_response}. If there are no responses from the other viewpoints yet, present your own argument based on the available data.

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

Engage by questioning their optimism and emphasizing the potential downsides they may have overlooked. Address each of their counterpoints to showcase why a conservative stance is ultimately the safest path for the firm's assets. Focus on debating and critiquing their arguments to demonstrate the strength of a low-risk strategy over their approaches. Output conversationally as if you are speaking without any special formatting.""" + get_language_instruction()

        audit, rendered = run_debate_turn(
            structured_llm=structured_llm,
            plain_llm=llm,
            prompt=prompt,
            speaker="Conservative Analyst",
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
        argument = f"Conservative Analyst: {summary}"

        new_risk_debate_state = {
            "history": (history + "\n\n" + rendered).strip(),
            "aggressive_history": risk_debate_state.get("aggressive_history", ""),
            "conservative_history": (
                conservative_history + "\n\n" + rendered
            ).strip(),
            "neutral_history": risk_debate_state.get("neutral_history", ""),
            "latest_speaker": "Conservative",
            "current_aggressive_response": risk_debate_state.get(
                "current_aggressive_response", ""
            ),
            "current_conservative_response": argument,
            "current_neutral_response": risk_debate_state.get(
                "current_neutral_response", ""
            ),
            "count": risk_debate_state["count"] + 1,
            "turns": [item.model_dump(mode="json") for item in next_audits],
            "metrics": termination.metrics,
            "termination": termination.model_dump(mode="json"),
        }

        return {"risk_debate_state": new_risk_debate_state}

    return conservative_node
