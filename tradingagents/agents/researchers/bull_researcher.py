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


def create_bull_researcher(llm):
    structured_llm = bind_debate_turn(llm, "Bull Researcher")

    def bull_node(state) -> dict:
        investment_debate_state = state["investment_debate_state"]
        history = investment_debate_state.get("history", "")
        bull_history = investment_debate_state.get("bull_history", "")
        previous_audits = debate_audits(investment_debate_state)
        evidence = build_evidence_registry(state)
        round_number = investment_debate_state["count"] // 2 + 1

        current_response = opponent_argument_or_opening(
            investment_debate_state.get("current_response", ""), "bear analyst"
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

        prompt = f"""You are a Bull Analyst advocating for investing in the {target_label}. Your task is to build a strong, evidence-based case emphasizing growth potential, competitive advantages, and positive market indicators. Leverage the provided research and data to address concerns and counter bearish arguments effectively.

Key points to focus on:
- Growth Potential: Highlight the company's market opportunities, revenue projections, and scalability.
- Competitive Advantages: Emphasize factors like unique products, strong branding, or dominant market positioning.
- Positive Indicators: Use financial health, industry trends, and recent positive news as evidence.
- Bear Counterpoints: Critically analyze the bear argument with specific data and sound reasoning, addressing concerns thoroughly and showing why the bull perspective holds stronger merit.
- Engagement: Present your argument in a conversational style, engaging directly with the bear analyst's points and debating effectively rather than just listing data.

Resources available:
{instrument_context}
Market research report: {market_research_report}
Social media sentiment report: {sentiment_report}
Latest world affairs news: {news_report}
{fundamentals_label}: {fundamentals_report}
Conversation history of the debate: {history}
Last bear argument: {current_response}

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

Use this information to deliver a compelling bull argument, refute the bear's concerns, and engage in a dynamic debate that demonstrates the strengths of the bull position.
""" + get_language_instruction()

        audit, rendered = run_debate_turn(
            structured_llm=structured_llm,
            plain_llm=llm,
            prompt=prompt,
            speaker="Bull Analyst",
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
        argument = f"Bull Analyst: {summary}"

        new_investment_debate_state = {
            "history": (history + "\n\n" + rendered).strip(),
            "bull_history": (bull_history + "\n\n" + rendered).strip(),
            "bear_history": investment_debate_state.get("bear_history", ""),
            "current_response": argument,
            "count": investment_debate_state["count"] + 1,
            "turns": [item.model_dump(mode="json") for item in next_audits],
            "metrics": termination.metrics,
            "termination": termination.model_dump(mode="json"),
        }

        return {"investment_debate_state": new_investment_debate_state}

    return bull_node
