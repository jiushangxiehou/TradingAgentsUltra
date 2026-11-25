"""Stable evidence identifiers derived from analyst reports."""

from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel, Field

REPORT_SOURCES = {
    "market_report": ("market", "Market Analysis"),
    "sentiment_report": ("sentiment", "Sentiment Analysis"),
    "news_report": ("news", "News Analysis"),
    "fundamentals_report": ("fundamentals", "Fundamentals Analysis"),
    "trader_investment_plan": ("trader", "Trader Proposal"),
}


class EvidenceItem(BaseModel):
    evidence_id: str
    source: str
    label: str
    text: str = Field(min_length=1)


def _blocks(text: str, max_chars: int = 700) -> list[str]:
    paragraphs = []
    for block in re.split(r"\n\s*\n", text.strip()):
        cleaned = re.sub(r"\s+", " ", block).strip()
        if not cleaned or re.fullmatch(r"[-|: ]+", cleaned):
            continue
        if re.fullmatch(r"#{1,6}\s+.+", cleaned):
            continue
        while len(cleaned) > max_chars:
            cut = cleaned.rfind(". ", 0, max_chars)
            cut = cut + 1 if cut > max_chars // 2 else max_chars
            paragraphs.append(cleaned[:cut].strip())
            cleaned = cleaned[cut:].strip()
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs


def build_evidence_registry(state: Mapping) -> list[EvidenceItem]:
    """Assign stable IDs to passages that debate participants can cite."""
    evidence: list[EvidenceItem] = []
    for field, (prefix, label) in REPORT_SOURCES.items():
        text = state.get(field)
        if not isinstance(text, str) or not text.strip():
            continue
        for index, passage in enumerate(_blocks(text), start=1):
            evidence.append(
                EvidenceItem(
                    evidence_id=f"{prefix}:{prefix[0]}{index}",
                    source=field,
                    label=label,
                    text=passage,
                )
            )
    return evidence


def render_evidence_catalog(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return "(No analyst evidence was available for this debate.)"
    return "\n".join(
        f"- [{item.evidence_id}] {item.label}: {item.text}"
        for item in evidence
    )


def evidence_ids(evidence: list[EvidenceItem]) -> set[str]:
    return {item.evidence_id for item in evidence}

