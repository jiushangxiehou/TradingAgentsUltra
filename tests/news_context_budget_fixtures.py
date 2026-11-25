"""Synthetic news facts, tool schemas and histories for budget-core tests."""

import dataclasses
from typing import Any

TICKER = "ACME"
OTHER_TICKER = "BETA"
TRADE_DATE = "2026-01-15"
AS_OF_DATE = "2025-06-30"


def base_state(messages=None, *, trade_date=TRADE_DATE):
    return {"messages": [] if messages is None else messages, "trade_date": trade_date}


@dataclasses.dataclass(frozen=True)
class NewsFact:
    """One annotated synthetic news fact for fidelity assertions."""

    fact_id: str
    subject: str
    event_date: str
    pub_date: str
    amount: str  # includes currency/unit, e.g. "1.2M USD", "1.2M EUR"
    source: str
    causality: str  # "confirmed" | "correlated_only" | "speculative"
    headline: str
    body: str

    def as_tuple(self) -> tuple[str, str, str, str, str, str]:
        """The five fidelity dimensions plus id, in stable comparison order."""
        return (
            self.fact_id,
            self.subject,
            self.event_date,
            self.amount,
            self.source,
            self.causality,
        )

    def render_news_block(self) -> str:
        """Render as the vendor-style news markup the analyst actually sees."""
        return (
            f"### {self.headline} (source: {self.source})\n"
            f"{self.body}\n"
            f"Link: https://example.invalid/{self.fact_id}\n"
            f"event_date: {self.event_date}\n"
            f"pub_date: {self.pub_date}\n"
            f"amount: {self.amount}\n"
            f"subject: {self.subject}\n"
            f"causality: {self.causality}\n"
        )



def news_facts() -> list[NewsFact]:
    """The synthetic news set, engineered to stress the pilot's policies.

    Covers: same-source similar headlines that differ by subject (ACME vs BETA),
    two amounts in different currencies (USD vs EUR), different event dates,
    a correlation-only report that must not become causal, a speculative one, and
    an exact duplicate plus a near-duplicate that must NOT be merged.
    """
    return [
        # --- same-subject, distinct event date, distinct currency/unit ---
        NewsFact(
            fact_id="F-USD",
            subject=TICKER,
            event_date="2026-01-10",
            pub_date="2026-01-11",
            amount="1.2M USD",
            source="WireDaily",
            causality="confirmed",
            headline=f"{TICKER} signs 1.2M USD supply deal",
            body=f"{TICKER} confirmed a 1.2M USD supply agreement on 2026-01-10.",
        ),
        NewsFact(
            fact_id="F-EUR",
            subject=TICKER,
            event_date="2026-01-12",
            pub_date="2026-01-13",
            amount="1.2M EUR",
            source="WireDaily",
            causality="confirmed",
            headline=f"{TICKER} signs 1.2M EUR supply deal",
            body=f"{TICKER} confirmed a second deal worth 1.2M EUR on 2026-01-12.",
        ),
        # --- different subject, same source, near-identical headline ---
        NewsFact(
            fact_id="F-OTHER",
            subject=OTHER_TICKER,
            event_date="2026-01-10",
            pub_date="2026-01-11",
            amount="1.2M USD",
            source="WireDaily",
            causality="confirmed",
            headline=f"{OTHER_TICKER} signs 1.2M USD supply deal",
            body=f"{OTHER_TICKER} (not {TICKER}) confirmed a 1.2M USD deal.",
        ),
        # --- correlation-only: must not be rewritten as causal ---
        NewsFact(
            fact_id="F-CORR",
            subject=TICKER,
            event_date="2026-01-14",
            pub_date="2026-01-14",
            amount="n/a",
            source="MarketBlog",
            causality="correlated_only",
            headline=f"{TICKER} shares moved alongside sector peers",
            body=(
                f"{TICKER} shares moved with the sector; no confirmed causal link "
                "was reported."
            ),
        ),
        # --- speculative ---
        NewsFact(
            fact_id="F-SPEC",
            subject=TICKER,
            event_date="2026-01-15",
            pub_date="2026-01-15",
            amount="n/a",
            source="RumorDesk",
            causality="speculative",
            headline=f"Analysts speculate on {TICKER} buyback",
            body=f"Unconfirmed chatter suggests {TICKER} may announce a buyback.",
        ),
        # --- "uncertain" causality, deliberately explicit-negative ---
        # NOTE: the branch's `_clean_identity_value` treats "uncertain" as
        # placeholder-ish ONLY for identity lookups; here it is plain news text,
        # so it is kept verbatim. Listed to ensure it is not dropped silently.
        NewsFact(
            fact_id="F-UNCERTAIN",
            subject=TICKER,
            event_date="2026-01-09",
            pub_date="2026-01-09",
            amount="n/a",
            source="WireDaily",
            causality="correlated_only",
            headline=f"{TICKER} supply agreement still unconfirmed",
            body=f"{TICKER} supply talks remain uncertain as of 2026-01-09.",
        ),
    ]



def near_duplicate_distinct_fact() -> NewsFact:
    """Near-duplicate TEXT but a distinct fact: must NOT be merged (NA-13/19)."""
    base = news_facts()[0]
    return dataclasses.replace(
        base,
        fact_id="F-USD-NEAR",
        amount="2.4M USD",  # different amount: a genuinely different fact
        headline=f"{TICKER} signs 2.4M USD supply deal",
        body=f"{TICKER} confirmed a separate 2.4M USD supply agreement on 2026-01-10.",
    )



def memory_log_entries() -> dict[str, list[dict]]:
    """Resolved and pending memory entries straddling the as-of boundary.

    Keys mirror TradingMemoryLog's parsed entry shape (see memory.py). Entries
    with ``resolved`` on/before AS_OF_DATE are in-window; later ones are future
    and must be excluded when ``as_of`` filtering runs (memory.py:87).
    """
    return {
        "in_window_same": [
            {
                "date": "2025-06-20",
                "ticker": TICKER,
                "rating": "Buy",
                "pending": False,
                "raw": "+4.0%",
                "alpha": "+1.0%",
                "holding": "5d",
                "resolved": "2025-06-27",
                "decision": f"Past decision BEFORE as-of for {TICKER}.",
                "reflection": "Lesson known before the cutoff.",
            },
        ],
        "future_same": [
            {
                "date": "2025-07-10",
                "ticker": TICKER,
                "rating": "Sell",
                "pending": False,
                "raw": "-3.0%",
                "alpha": "-0.5%",
                "holding": "5d",
                "resolved": "2025-07-17",  # AFTER AS_OF_DATE
                "decision": f"FUTURE lesson for {TICKER} that must not leak.",
                "reflection": "Known only after the cutoff.",
            },
        ],
        "in_window_cross": [
            {
                "date": "2025-06-18",
                "ticker": OTHER_TICKER,
                "rating": "Hold",
                "pending": False,
                "raw": "+0.5%",
                "alpha": "n/a",
                "holding": "5d",
                "resolved": "2025-06-25",
                "decision": f"Cross-ticker lesson for {OTHER_TICKER}.",
                "reflection": "Cross-ticker reflection before cutoff.",
            },
        ],
        "pending_same": [
            {
                "date": "2025-06-29",
                "ticker": TICKER,
                "rating": "Buy",
                "pending": True,
                "raw": None,
                "alpha": None,
                "holding": None,
                "resolved": None,
                "decision": "Pending decision, never surfaced as past context.",
                "reflection": "",
            },
        ],
    }



def empty_history() -> list:
    """NA-01: no prior messages beyond the run's seeded human turn."""
    return []



def long_multiturn_history(turns: int = 12) -> list:
    """NA-09: long multi-turn history of AI/tool/user messages.

    Each iteration emits a well-formed tool-call AI message followed by its
    matching ToolMessage (so tool pairing is valid), then a human follow-up. An
    extra *exact duplicate* tool-call/result pair is injected at i==0 to exercise
    deduplication at scale; it is a complete, valid pair (its own call id), so
    grouping stays well-formed.
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    facts = news_facts()
    msgs: list = []
    for i in range(turns):
        fact = facts[i % len(facts)]
        call_id = f"call_{i}"
        params = _news_tool_args(fact)
        msgs.append(
            AIMessage(
                content="",
                tool_calls=[{"name": "get_news", "args": params, "id": call_id}],
            )
        )
        msgs.append(
            ToolMessage(content=fact.render_news_block(), tool_call_id=call_id)
        )
        # Exact duplicate as a COMPLETE pair (own AI call + its result) so the
        # block is identical to the first and dedup can collapse it without ever
        # creating an orphan tool_call_id (NA-13 at scale).
        if i == 0:
            dup_id = f"dup_{i}"
            msgs.append(
                AIMessage(
                    content="",
                    tool_calls=[{"name": "get_news", "args": params, "id": dup_id}],
                )
            )
            msgs.append(
                ToolMessage(content=fact.render_news_block(), tool_call_id=dup_id)
            )
        msgs.append(HumanMessage(content=f"Follow-up {i}: what changed for {TICKER}?"))
    return msgs



def _news_tool_args(fact: NewsFact) -> dict:
    return {
        "ticker": fact.subject or TICKER,
        "start_date": "2026-01-01",
        "end_date": TRADE_DATE,
    }



class MockTool:
    """Minimal stand-in for a LangChain tool with finite, deterministic output.

    Provides ``name``, ``args`` and ``invoke`` so a real ``bind_tools`` accepts it
    and the pilot can measure tool-schema overhead (NA-01..08).
    """

    def __init__(self, name: str, args: dict, output: str) -> None:
        self.name = name
        self.args = args
        self.description = f"Mock {name} for the news pilot fixtures."
        self._output = output

    def invoke(self, _args: Any) -> str:
        return self._output



def mock_news_tools(facts: list[NewsFact] | None = None) -> list[MockTool]:
    """Four mock tools mirroring the real news analyst's tool surface."""
    facts = facts or news_facts()
    joined = "\n".join(f.render_news_block() for f in facts)
    return [
        MockTool(
            "get_news",
            {"ticker": "str", "start_date": "str", "end_date": "str"},
            joined,
        ),
        MockTool(
            "get_global_news",
            {"curr_date": "str", "look_back_days": "int?", "limit": "int?"},
            f"## Global news, {TICKER} window:\n{joined}",
        ),
        MockTool(
            "get_macro_indicators",
            {"indicator": "str", "curr_date": "str", "look_back_days": "int?"},
            "## CPI: 3.1% y/y; Fed funds: 4.25%.",
        ),
        MockTool(
            "get_prediction_markets",
            {"topic": "str", "limit": "int?"},
            "## Fed rate cut by March: 0.62 implied probability.",
        ),
    ]
