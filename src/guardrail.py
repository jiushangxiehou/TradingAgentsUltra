"""Deterministic guardrail (REQ-HARD-GUARDRAIL, ADR-004).

ADR-004 / REQ-HARD-GUARDRAIL / INV-GUARDRAIL-ZERO-ESCAPE / INV-RATING-VALIDITY

A pure, deterministic, signed decision check that runs BEFORE any AI-produced
trade decision can reach execution. No LLM, no network, no clock, no mutable
module state: the same (decision, limits) always produces a byte-identical
result.

Pinned semantics (requirements session + architecture session)
--------------------------------------------------------------
Position   reject iff ``size_pct > max_position_pct`` (default 0.10).
           Exactly 10.0% is ACCEPTED; 10.0% + epsilon is rejected.
Short      reject iff ``short_amount > available_cash * max_short_pct_of_cash``
           (default 1.0). ``short == cash`` is ACCEPTED. The constant is a
           MULTIPLIER on available cash, not a literal percentage: 1.0 means
           "short may equal cash". Zero cash: ``short == cash == 0`` is
           accepted by this literal rule; any positive short against zero
           cash is rejected. The product is computed through ``_short_limit``
           so a non-finite multiplier cannot turn ``0 * inf -> nan`` into a
           fail-open: the boundary floors at 0 when cash is 0 (zero escape).
Rating     exact, case-sensitive membership in ``VALID_RATINGS``. No trimming,
           no case folding, no aliases, no coercion.
Fallback   rating ``"Hold"`` (a legal tier) carried with audit action
           ``"REVIEW/HOLD"``. "REVIEW" is NEVER a rating -- that would violate
           INV-RATING-VALIDITY, which the documented fallback must satisfy.
Audit      exactly ONE ``AuditRecord`` per rejection, naming the trigger, the
           observed value and the configured limit. None on pass.
Malformed  fail closed: a decision that cannot be evaluated is REJECTED with
           trigger ``MALFORMED_DECISION``. ``evaluate_decision`` never raises
           for a bad decision. A bad *configuration* is a different fault: it
           raises ``GuardrailError``.
Precedence multiple simultaneous violations resolve to one record named by
           ``TRIGGER_PRECEDENCE`` (a frozen, total order over ``Trigger``).

Declared scope limit (ADR-004): this is a library call, not a structural
choke point. "No escape" means every caller that invokes the guardrail obeys
it; forcing all execution through it is deferred until an execution module
exists.

Duplicate records
-----------------
``record_id`` is derived from content, so identical content always yields an
identical id -- that is required for determinism and is NOT a collision. The
pinned "reject on collision, never overwrite" rule is therefore enforced at
the only place where a collision can actually be observed: aggregation via the
OPTIONAL ``AuditLog``. ``evaluate_decision`` does not require an ``AuditLog``;
guarding is stateless, and logging is a separate, optional concern.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

# INV-GUARDRAIL-ZERO-ESCAPE: no guarded decision may reach execution.
# These two constants predate the guardrail implementation and are retained
# verbatim (extend the baseline, never replace it).
GUARDRAIL_LIMITS = {"max_position_pct": 0.10, "max_short_pct_of_cash": 1.0}
VALID_RATINGS = {"Buy", "Overweight", "Hold", "Underweight", "Sell"}

# REQ-HARD-GUARDRAIL: the documented fallback. "Hold" is a legal tier, so the
# fallback itself satisfies INV-RATING-VALIDITY; "REVIEW" would not.
FALLBACK_RATING: Final[str] = "Hold"
AUDIT_ACTION_REVIEW_HOLD: Final[str] = "REVIEW/HOLD"

# Numeric types a decision field may carry. bool is a subclass of int and is
# deliberately excluded: True/False is not a position size.
_NUMBER_TYPES = (int, float)


class Trigger(str, Enum):
    """Frozen audit vocabulary. Every rejection names exactly one of these."""

    MALFORMED_DECISION = "MALFORMED_DECISION"
    ILLEGAL_RATING = "ILLEGAL_RATING"
    POSITION_LIMIT = "POSITION_LIMIT"
    SHORT_EXCEEDS_CASH = "SHORT_EXCEEDS_CASH"


# Pinned resolution order when several limits are crossed at once. Frozen and
# total over Trigger so the emitted record is deterministic.
TRIGGER_PRECEDENCE: Final[tuple[Trigger, ...]] = (
    Trigger.MALFORMED_DECISION,
    Trigger.ILLEGAL_RATING,
    Trigger.POSITION_LIMIT,
    Trigger.SHORT_EXCEEDS_CASH,
)


class GuardrailError(ValueError):
    """A guardrail *configuration* or *aggregation* fault, never a decision."""


@dataclass(frozen=True, slots=True)
class GuardrailLimits:
    """The configurable boundary. Defaults mirror ``GUARDRAIL_LIMITS``."""

    max_position_pct: float = 0.10
    max_short_pct_of_cash: float = 1.0

    def as_dict(self) -> dict[str, float]:
        """Stable, ordered serialisation for audit and diffing."""
        return {
            "max_position_pct": self.max_position_pct,
            "max_short_pct_of_cash": self.max_short_pct_of_cash,
        }


@dataclass(frozen=True, slots=True)
class Decision:
    """The AI-produced trade decision. Carries no timestamp: a clock field
    would break determinism and replay."""

    rating: str
    size_pct: float
    short_amount: float
    available_cash: float
    instrument_id: str | None = None


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Exactly one per rejection: trigger, observed value, configured limit."""

    record_id: str
    trigger: Trigger
    observed_value: object
    configured_limit: object
    action: str = AUDIT_ACTION_REVIEW_HOLD

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "trigger": self.trigger.value if isinstance(self.trigger, Trigger) else self.trigger,
            "observed_value": self.observed_value,
            "configured_limit": self.configured_limit,
            "action": self.action,
        }


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    """Never both, never neither: ``passed`` iff ``audit is None``."""

    decision: Decision
    passed: bool
    audit: AuditRecord | None

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "decision": {
                "rating": self.decision.rating
                if isinstance(self.decision.rating, str)
                else repr(self.decision.rating),
                "size_pct": _canon(self.decision.size_pct),
                "short_amount": _canon(self.decision.short_amount),
                "available_cash": _canon(self.decision.available_cash),
                "instrument_id": self.decision.instrument_id,
            },
            "audit": self.audit.to_dict() if self.audit is not None else None,
        }


# ---------------------------------------------------------------------------
# Content-derived identity
# ---------------------------------------------------------------------------

def _canon(value: object) -> object:
    """Injective, JSON-safe canonical form of an audit value.

    Floats use ``float.hex`` so 0.1 vs 0.10000000000000001 cannot collapse and
    NaN/inf remain representable in JSON.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return {"__float__": value.hex()}
    if isinstance(value, int):
        return {"__int__": str(value)}
    if isinstance(value, str):
        return {"__str__": value}
    if isinstance(value, (set, frozenset)):
        return {"__set__": sorted(_canon_sort_key(v) for v in value)}
    if isinstance(value, (list, tuple)):
        return {"__seq__": [_canon(v) for v in value]}
    return {"__repr__": repr(value)}


def _canon_sort_key(value: object) -> str:
    return json.dumps(_canon(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _record_id(trigger: Trigger, observed: object, limit: object, action: str) -> str:
    """``record_id`` is a pure function of the record's content.

    No counter, no UUID, no clock -- so two identical rejections produce the
    same id, which is exactly the determinism G6 asserts.
    """
    payload = json.dumps(
        {
            "trigger": trigger.value,
            "observed": _canon(observed),
            "limit": _canon(limit),
            "action": action,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"gr-{digest[:16]}"


def _make_record(
    trigger: Trigger, observed: object, limit: object, action: str = AUDIT_ACTION_REVIEW_HOLD
) -> AuditRecord:
    return AuditRecord(
        record_id=_record_id(trigger, observed, limit, action),
        trigger=trigger,
        observed_value=observed,
        configured_limit=limit,
        action=action,
    )


# ---------------------------------------------------------------------------
# Optional aggregation: the only place a collision can be observed
# ---------------------------------------------------------------------------

class AuditLog:
    """Optional append-only collector enforcing the reject-on-collision rule.

    ``evaluate_decision`` does not need one. A caller that keeps a log gets the
    pinned guarantee: a ``record_id`` already present is REJECTED with
    ``GuardrailError`` and never overwritten.
    """

    def __init__(self) -> None:
        self._records: list[AuditRecord] = []
        self._by_id: dict[str, AuditRecord] = {}

    def add(self, record: AuditRecord) -> None:
        existing = self._by_id.get(record.record_id)
        if existing is not None:
            if existing == record:
                raise GuardrailError(
                    f"duplicate audit record: {record.record_id} (already logged)"
                )
            raise GuardrailError(
                f"record_id collision: {record.record_id} names two different records"
            )
        self._by_id[record.record_id] = record
        self._records.append(record)

    def records(self) -> tuple[AuditRecord, ...]:
        return tuple(self._records)

    def __len__(self) -> int:
        return len(self._records)


def _short_limit(available_cash: float, multiplier: float) -> float:
    """The short boundary ``available_cash * multiplier``, made NaN-proof.

    Python evaluates ``0.0 * inf`` as ``nan``, and ``short > nan`` is False for
    every short -- so computing the product naively turns ANY short against zero
    cash into a pass the moment the multiplier is non-finite. That is a fail-open
    at exactly the boundary R8 pins. The product is clamped on its floor:

    * ``available_cash == 0``            -> ``0.0``, so any positive short is
      rejected and ``short == cash == 0`` is still accepted (pinned R8).
    * ``available_cash > 0, multiplier`` non-finite -> the product is legitimately
      unbounded, so ``inf``.
    * ``available_cash == inf`` with a zero multiplier -> ``0.0`` (unreachable
      through ``evaluate_decision``, which rejects non-finite cash as malformed;
      kept so the helper is total on its own).
    """
    if available_cash == 0:
        return 0.0
    product = available_cash * multiplier
    if isinstance(product, float) and math.isnan(product):
        return math.inf
    return product


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_limits(limits: object) -> GuardrailLimits:
    """A broken configuration is a fault, not a decision: raise."""
    if not isinstance(limits, GuardrailLimits):
        raise GuardrailError(f"limits must be GuardrailLimits, got {type(limits).__name__}")
    for name, value in limits.as_dict().items():
        if isinstance(value, bool) or not isinstance(value, _NUMBER_TYPES):
            raise GuardrailError(f"{name} must be a number, got {type(value).__name__}")
        if isinstance(value, float) and math.isnan(value):
            raise GuardrailError(f"{name} must not be NaN")
        if value < 0:
            raise GuardrailError(f"{name} must not be negative, got {value!r}")
    return limits


def _is_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, _NUMBER_TYPES):
        return False
    return not (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))


def _malformation(decision: object) -> tuple[str, object] | None:
    """Return (reason_code, observed) if the decision cannot be evaluated."""
    if not isinstance(decision, Decision):
        return "not-a-decision", type(decision).__name__

    if not isinstance(decision.rating, str):
        return "rating-not-a-string", type(decision.rating).__name__

    for field in ("size_pct", "short_amount", "available_cash"):
        value = getattr(decision, field)
        if isinstance(value, bool) or not isinstance(value, _NUMBER_TYPES):
            return f"{field}-not-a-number", type(value).__name__
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return f"{field}-not-finite", value
        if value < 0:
            return f"{field}-negative", value

    instrument = decision.instrument_id
    if instrument is not None and not isinstance(instrument, str):
        return "instrument-not-a-string", type(instrument).__name__

    return None


# ---------------------------------------------------------------------------
# The guardrail
# ---------------------------------------------------------------------------

def evaluate_decision(
    decision: Decision, limits: GuardrailLimits = GuardrailLimits()
) -> GuardrailResult:
    """Hard-check one decision against the guardrail limits.

    Returns the input decision unchanged when it passes, or the REVIEW/HOLD
    fallback plus exactly one ``AuditRecord`` when it does not. Never raises
    for a bad decision (fail closed); raises ``GuardrailError`` for a bad
    configuration.
    """
    checked = _validate_limits(limits)

    malformation = _malformation(decision)
    if malformation is not None:
        reason, observed = malformation
        audit = _make_record(Trigger.MALFORMED_DECISION, reason, observed)
        return GuardrailResult(decision=_fallback(decision), passed=False, audit=audit)

    # Past this point the decision is structurally sound, so every remaining
    # violation is an ordinary limit crossing.
    rating = decision.rating
    size_pct = decision.size_pct
    short_amount = decision.short_amount
    available_cash = decision.available_cash

    violations: dict[Trigger, tuple[object, object]] = {}

    if rating not in VALID_RATINGS:
        violations[Trigger.ILLEGAL_RATING] = (rating, VALID_RATINGS)
    if size_pct > checked.max_position_pct:
        violations[Trigger.POSITION_LIMIT] = (size_pct, checked.max_position_pct)
    short_limit = _short_limit(available_cash, checked.max_short_pct_of_cash)
    if short_amount > short_limit:
        violations[Trigger.SHORT_EXCEEDS_CASH] = (short_amount, short_limit)

    if not violations:
        return GuardrailResult(decision=decision, passed=True, audit=None)

    for trigger in TRIGGER_PRECEDENCE:
        if trigger in violations:
            observed, limit = violations[trigger]
            audit = _make_record(trigger, observed, limit)
            return GuardrailResult(decision=_fallback(decision), passed=False, audit=audit)

    # Unreachable: TRIGGER_PRECEDENCE is total over Trigger, and violations is
    # non-empty. Fail closed rather than silently pass if that ever changes.
    audit = _make_record(
        Trigger.MALFORMED_DECISION,
        "unclassified-violation",
        tuple(sorted(t.value for t in violations)),
    )
    return GuardrailResult(decision=_fallback(decision), passed=False, audit=audit)


def _fallback(decision: object) -> Decision:
    """The documented REVIEW/HOLD decision: rating Hold, never "REVIEW"."""
    if isinstance(decision, Decision):
        return Decision(
            rating=FALLBACK_RATING,
            size_pct=decision.size_pct if _is_number(decision.size_pct) else 0.0,
            short_amount=decision.short_amount if _is_number(decision.short_amount) else 0.0,
            available_cash=decision.available_cash if _is_number(decision.available_cash) else 0.0,
            instrument_id=decision.instrument_id
            if isinstance(decision.instrument_id, str)
            else None,
        )
    return Decision(
        rating=FALLBACK_RATING,
        size_pct=0.0,
        short_amount=0.0,
        available_cash=0.0,
        instrument_id=None,
    )
