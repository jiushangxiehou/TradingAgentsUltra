"""LIVE prose evaluation (D4 behavioural tier, D7 gate 4 live half).

Measures a real model answer against a fixed source on two documented proxies:

    faithfulness  fraction of the numbers in the answer that also appear in the
                  source. A fabricated figure lowers the score; a correct
                  figure keeps it.
    relevancy     fraction of the question's key terms that appear in the
                  answer.

Both must be >= 0.6, the threshold recorded in `docs/req/requirements.yaml`
and in the architectural decision. This is deliberately a *proxy*, not a
DeepEval faithfulness score: it needs no extra dependency, it is reproducible
and it cannot be satisfied by a fluent but ungrounded answer. The limitation
(numbers-only grounding, term overlap for relevancy) is recorded in the debt
register rather than hidden.

Requires `DEEPSEEK_API_KEY` (and optionally `DEEPSEEK_API_BASE_URL`,
`TRADINGAGENTS_QUICK_THINK_LLM`). Skips, rather than fails, when the key is
absent: the live tier is never part of the offline gate.
"""

from __future__ import annotations

import os
import re

import pytest

pytestmark = pytest.mark.live

SOURCE = """
Q3 FY27 results (reported 2026-11-19): revenue 57.0B, up 62% year over year;
data-centre revenue 51.2B; gross margin 73.4%; operating margin 61.0%;
operating cash flow 30.1B and free cash flow 22.2B; cash conversion (OCF/NI)
40%; GAAP EPS 1.30. Guidance for Q4: revenue 62.0B +/- 2%, gross margin
74.0% +/- 1 point. Risks: supply concentration, export-control changes, and a
customer concentration above 20% of revenue.
"""

QUESTION = (
    "Summarise the quarter in at most 120 words. State the revenue, the gross "
    "margin, the guidance and the three risks. Use only the figures above; do "
    "not invent numbers."
)

KEY_TERMS = ("revenue", "gross margin", "guidance", "risk")

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(text))


def _faithfulness(answer: str, source: str) -> float:
    claimed = _numbers(answer)
    if not claimed:
        return 1.0
    grounded = {n for n in claimed if n in _numbers(source)}
    return len(grounded) / len(claimed)


def _relevancy(answer: str) -> float:
    lowered = answer.lower()
    return sum(term in lowered for term in KEY_TERMS) / len(KEY_TERMS)


def _client():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        pytest.skip("DEEPSEEK_API_KEY is not set: the live tier is skipped, not failed")
    from openai import OpenAI

    return OpenAI(
        api_key=key,
        base_url=os.environ.get("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com"),
    )


def test_faithfulness_and_relevancy_thresholds():
    """Faithfulness >= 0.6 and relevancy >= 0.6 on one fixed source."""
    model = os.environ.get("TRADINGAGENTS_QUICK_THINK_LLM", "deepseek-v4-flash")
    client = _client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a careful financial analyst. Ground every number."},
            {"role": "user", "content": f"{QUESTION}\n\nSOURCE:\n{SOURCE}"},
        ],
        temperature=0.0,
        max_tokens=400,
    )
    answer = (response.choices[0].message.content or "").strip()

    faithfulness = _faithfulness(answer, SOURCE)
    relevancy = _relevancy(answer)

    print(f"model={model} faithfulness={faithfulness:.2f} relevancy={relevancy:.2f}")
    print(answer)
    assert answer, "the model returned an empty answer"
    assert faithfulness >= 0.6, f"faithfulness {faithfulness:.2f} < 0.6: {answer}"
    assert relevancy >= 0.6, f"relevancy {relevancy:.2f} < 0.6: {answer}"
