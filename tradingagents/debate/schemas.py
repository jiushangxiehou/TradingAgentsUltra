"""Typed contracts for structured debate turns and termination decisions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Confidence = Literal["low", "medium", "high"]


class DebateClaim(BaseModel):
    claim_id: str = Field(description="Stable identifier chosen by the speaker.")
    statement: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: Confidence = "medium"


class DebateRebuttal(BaseModel):
    target_claim_id: str = Field(min_length=1)
    argument: str = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)


class DebateTurn(BaseModel):
    """One structured contribution to a research or risk debate."""

    round: int = Field(ge=1)
    speaker: str = Field(min_length=1)
    stance: str = Field(min_length=1)
    thesis: str = Field(min_length=1)
    claims: list[DebateClaim] = Field(default_factory=list)
    rebuttals: list[DebateRebuttal] = Field(default_factory=list)
    concessions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    changed_position: bool = False
    confidence: Confidence = "medium"

    @field_validator("claims")
    @classmethod
    def unique_claim_ids(cls, claims: list[DebateClaim]) -> list[DebateClaim]:
        ids = [claim.claim_id for claim in claims]
        if len(ids) != len(set(ids)):
            raise ValueError("claim_id values must be unique within a turn")
        return claims


class TurnAudit(BaseModel):
    """Validation, novelty, and evidence record for one debate turn."""

    sequence: int = Field(ge=1)
    round: int = Field(ge=1)
    speaker: str
    turn: DebateTurn | None = None
    raw_output: str = ""
    schema_valid: bool
    evidence_valid: bool
    rebuttal_valid: bool
    new_claim_count: int = 0
    claims_with_evidence: int = 0
    valid_evidence_claim_count: int = 0
    rebuttal_count: int = 0
    valid_rebuttal_count: int = 0
    valid_claim_ids: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class TerminationDecision(BaseModel):
    """The termination recommendation produced after a complete debate cycle."""

    code: str = "CONTINUE"
    reason: str = "The debate has not met a termination condition."
    recommended: bool = False
    effective: bool = False
    shadow_mode: bool = True
    after_round: int = 0
    metrics: dict[str, float | int] = Field(default_factory=dict)

    @property
    def should_stop(self) -> bool:
        return self.recommended and self.effective

