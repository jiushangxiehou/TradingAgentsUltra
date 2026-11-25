from tradingagents.agents.context import (
    get_instrument_context_from_state,
    get_language_instruction,
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


def create_bear_researcher(llm):
    structured_llm = bind_debate_turn(llm, "Bear Researcher")

    def bear_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bear_history = investment_debate_state.get("bear_history", "")
        previous_audits = debate_audits(investment_debate_state)
        evidence = build_evidence_registry(state)
        round_number = investment_debate_state["count"] // 2 + 1

        current_response = opponent_argument_or_opening(
            investment_debate_state.get("current_response", ""), "bull analyst"
        )
        market_research_report = report_or_absent(state["market_report"], "market")
        sentiment_report = report_or_absent(state["sentiment_report"], "sentiment")
        news_report = report_or_absent(state["news_report"], "news")
        fundamentals_report = report_or_absent(state["fundamentals_report"], "fundamentals")
        instrument_context = get_instrument_context_from_state(state)
        asset_type = state.get("asset_type", "stock")
        target_label = "stock" if asset_type == "stock" else "asset"
        fundamentals_label = (
            "Company fundamentals report"
            if asset_type == "stock"
            else "Asset fundamentals report (may be unavailable for crypto)"
        )

        prompt = f"""You are a Bear Analyst making the case against investing in the {target_label}. Your goal is to present a well-reasoned argument emphasizing risks, challenges, and negative indicators. Leverage the provided research and data to highlight potential downsides and counter bullish arguments effectively.

Key points to focus on:

- Risks and Challenges: Highlight factors like market saturation, financial instability, or macroeconomic threats that could hinder the stock's performance.
- Competitive Weaknesses: Emphasize vulnerabilities such as weaker market positioning, declining innovation, or threats from competitors.
- Negative Indicators: Use evidence from financial data, market trends, or recent adverse news to support your position.
- Bull Counterpoints: Critically analyze the bull argument with specific data and sound reasoning, exposing weaknesses or over-optimistic assumptions.
- Engagement: Present your argument in a conversational style, directly engaging with the bull analyst's points and debating effectively rather than simply listing facts.

Resources available:

{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {history}
Last bull argument: {current_response}

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

Use this information to deliver a compelling bear argument, refute the bull's claims, and engage in a dynamic debate that demonstrates the risks and weaknesses of investing in the {target_label}.
""" + get_language_instruction()

        audit, rendered = run_debate_turn(
            structured_llm=structured_llm,
            plain_llm=llm,
            prompt=prompt,
            speaker="Bear Analyst",
            round_number=round_number,
            sequence=investment_debate_state["count"] + 1,
            debate_state=investment_debate_state,
            evidence=evidence,
        )
        next_audits = previous_audits + [audit]
        config = get_config()
        termination = evaluate_termination(
            debate_type="research",
            audits=next_audits,
            participants=2,
            max_rounds=max(1, int(config["max_debate_rounds"])),
            config=config,
        )
        summary = audit.turn.thesis if audit.turn is not None else audit.raw_output[:500]
        argument = f"Bear Analyst: {summary}"

        new_investment_debate_state = {
            "history": (history + "\n\n" + rendered).strip(),
            "bear_history": (bear_history + "\n\n" + rendered).strip(),
            "bull_history": investment_debate_state.get("bull_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
            "turns": [item.model_dump(mode="json") for item in next_audits],
            "metrics": termination.metrics,
            "termination": termination.model_dump(mode="json"),
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bear_node
