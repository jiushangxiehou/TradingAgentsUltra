"""OFFLINE deterministic guardrail tests (REQ-HARD-GUARDRAIL, ADR-004).

Requires no API, no network, no clock.

Invariants under test
---------------------
INV-GUARDRAIL-ZERO-ESCAPE : no decision that oversteps a guardrail limit may
                            reach execution (invariants.md:8)
INV-RATING-VALIDITY       : the final rating is always a member of the legal
                            5-tier set (invariants.md:11)

Acceptance conditions G1-G9 are the requirements-session conditions
(transcripts/60760270-CUIHaoyu-01-requirements-classification.md:1326-1334);
the G-* conditions below are the build-session pinned decisions
(transcripts/60760270-CUIHaoyu-02-architecture-evaluation.md:1075-1085).

Negative tests (`.agent/rules.md` covenant 3): G9 proves the zero-escape gate
is a real gate, G-EDGE-NO-APE proves it is not an "same object back" tautology.
"""

from __future__ import annotations

import ast
import pathlib
from decimal import Decimal

import pytest

from src import guardrail
from src.guardrail import (
    AUDIT_ACTION_REVIEW_HOLD,
    FALLBACK_RATING,
    GUARDRAIL_LIMITS,
    TRIGGER_PRECEDENCE,
    VALID_RATINGS,
    AuditLog,
    AuditRecord,
    Decision,
    GuardrailError,
    GuardrailLimits,
    GuardrailResult,
    Trigger,
    evaluate_decision,
)

pytestmark = pytest.mark.offline

MODULE_PATH = pathlib.Path(guardrail.__file__)
LEGAL_RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")


# ---------------------------------------------------------------------------
# Fixtures and the shared zero-escape expression (used by BOTH G3 and G9)
# ---------------------------------------------------------------------------

def make_decision(
    rating: object = "Buy",
    size_pct: object = 0.05,
    short_amount: object = 0.0,
    available_cash: object = 1000.0,
    instrument_id: str | None = "AAPL",
) -> Decision:
    """A fully legal decision; each test overrides exactly the field it probes."""
    return Decision(
        rating=rating,  # type: ignore[arg-type]
        size_pct=size_pct,  # type: ignore[arg-type]
        short_amount=short_amount,  # type: ignore[arg-type]
        available_cash=available_cash,  # type: ignore[arg-type]
        instrument_id=instrument_id,
    )


# (label, decision, must_be_rejected)
CROSSING_CASES: tuple[tuple[str, Decision, bool], ...] = (
    # position boundary (default max_position_pct == 0.10)
    ("position-below", make_decision(size_pct=0.0999), False),
    ("position-exact-10pct", make_decision(size_pct=0.10), False),
    ("position-just-above", make_decision(size_pct=0.1000001), True),
    ("position-11pct", make_decision(size_pct=0.11), True),
    ("position-full-book", make_decision(size_pct=1.0), True),
    ("position-above-book", make_decision(size_pct=4.0), True),
    # short boundary (cash == 1000.0, non-zero fixture)
    ("short-zero", make_decision(short_amount=0.0), False),
    ("short-below-cash", make_decision(short_amount=999.99), False),
    ("short-exactly-cash", make_decision(short_amount=1000.0), False),
    ("short-just-above-cash", make_decision(short_amount=1000.0001), True),
    ("short-twice-cash", make_decision(short_amount=2000.0), True),
    # rating membership (exact, case-sensitive)
    ("rating-buy", make_decision(rating="Buy"), False),
    ("rating-overweight", make_decision(rating="Overweight"), False),
    ("rating-hold", make_decision(rating="Hold"), False),
    ("rating-underweight", make_decision(rating="Underweight"), False),
    ("rating-sell", make_decision(rating="Sell"), False),
    ("rating-lowercase", make_decision(rating="buy"), True),
    ("rating-uppercase", make_decision(rating="BUY"), True),
    ("rating-trailing-space", make_decision(rating="HOLD "), True),
    ("rating-leading-space", make_decision(rating=" Hold"), True),
    ("rating-review", make_decision(rating="Review"), True),
    ("rating-empty", make_decision(rating=""), True),
    # Non-string ratings are MALFORMED_DECISION (ruled: the later, more
    # specific pin wins); they are asserted in the malformed suite, not here.
    # combined crossings (one record, highest precedence)
    ("all-three-violations", make_decision(rating="buy", size_pct=0.5, short_amount=5000.0), True),
    ("position-and-short", make_decision(size_pct=0.5, short_amount=5000.0), True),
)


def zero_escapes(
    evaluator, cases: tuple[tuple[str, Decision, bool], ...] = CROSSING_CASES
) -> int:
    """Count decisions that overstep a limit but are still returned executable.

    This single expression is shared by G3 (real evaluator) and G9 (patched-to-
    always-pass evaluator), so G9 measures THIS gate, not a private copy.
    """
    escapes = 0
    for _, decision, must_reject in cases:
        result = evaluator(decision)
        if must_reject and result.passed:
            escapes += 1
    return escapes


def _verdict_violations(decision: Decision, limits: GuardrailLimits) -> list[Trigger]:
    """Independent, test-side reference judgement (never calls the module).

    Used to cross-check the module in both directions: a decision this helper
    calls violative must be rejected, and a passing decision must have no
    violation. Written without any module arithmetic so it cannot inherit a bug.
    """
    found: list[Trigger] = []
    rating = decision.rating
    if not (isinstance(rating, str) and rating in LEGAL_RATINGS):
        found.append(Trigger.ILLEGAL_RATING)
    if isinstance(decision.size_pct, (int, float)) and not isinstance(
        decision.size_pct, bool
    ) and decision.size_pct > limits.max_position_pct:
        found.append(Trigger.POSITION_LIMIT)
    if (
        isinstance(decision.short_amount, (int, float))
        and isinstance(decision.available_cash, (int, float))
        and decision.short_amount > decision.available_cash * limits.max_short_pct_of_cash
    ):
        found.append(Trigger.SHORT_EXCEEDS_CASH)
    return found


def _expected_trigger(violations: list[Trigger]) -> Trigger | None:
    for trigger in TRIGGER_PRECEDENCE:
        if trigger in violations:
            return trigger
    return None


# ---------------------------------------------------------------------------
# G0 -- offline marker + retained baseline constants (extend, not replace)
# ---------------------------------------------------------------------------

def test_file_is_marked_offline():
    """REQ-HARD-GUARDRAIL / pinned R1: the offline gate must not be vacuous."""
    assert pytestmark == pytest.mark.offline


def test_baseline_constants_are_retained():
    """`extend, do not replace`: the pre-existing constants keep their values."""
    assert GUARDRAIL_LIMITS == {"max_position_pct": 0.10, "max_short_pct_of_cash": 1.0}
    assert VALID_RATINGS == {"Buy", "Overweight", "Hold", "Underweight", "Sell"}
    assert isinstance(VALID_RATINGS, (set, frozenset))
    assert FALLBACK_RATING in VALID_RATINGS
    assert AUDIT_ACTION_REVIEW_HOLD == "REVIEW/HOLD"


# ---------------------------------------------------------------------------
# G1 -- boundary matrix: accept at the boundary, reject strictly above
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "size_pct, must_pass",
    [
        (0.0, True),
        (0.05, True),
        (0.0999, True),
        (0.09999999, True),
        (0.10, True),        # exactly 10.0% is accepted (pinned)
        (0.1000001, False),  # strictly greater is rejected
        (0.10 + 1e-9, False),
        (0.11, False),
        (1.0, False),
    ],
)
def test_position_boundary(size_pct, must_pass):
    """G1: accept size_pct <= 10%, reject size_pct > 10%."""
    result = evaluate_decision(make_decision(size_pct=size_pct))
    assert result.passed is must_pass
    if not must_pass:
        assert result.audit is not None
        assert result.audit.trigger is Trigger.POSITION_LIMIT


@pytest.mark.parametrize(
    "short_amount, available_cash, must_pass",
    [
        (0.0, 1000.0, True),
        (999.99, 1000.0, True),
        (1000.0, 1000.0, True),        # short == cash is accepted (pinned)
        (1000.0001, 1000.0, False),    # strictly greater is rejected
        (1001.0, 1000.0, False),
        (2500.0, 1000.0, False),
    ],
)
def test_short_boundary(short_amount, available_cash, must_pass):
    """G1 / pinned R4: reject iff short > cash * max_short_pct_of_cash (1.0)."""
    result = evaluate_decision(
        make_decision(short_amount=short_amount, available_cash=available_cash)
    )
    assert result.passed is must_pass
    if not must_pass:
        assert result.audit is not None
        assert result.audit.trigger is Trigger.SHORT_EXCEEDS_CASH


def test_zero_cash_semantics_are_explicit():
    """Pinned R8: short == cash == 0 is accepted by the literal pin."""
    result = evaluate_decision(make_decision(short_amount=0.0, available_cash=0.0))
    assert result.passed is True
    assert result.audit is None

    # ...but any positive short against zero cash is an outright escape attempt.
    rejected = evaluate_decision(make_decision(short_amount=0.01, available_cash=0.0))
    assert rejected.passed is False
    assert rejected.audit is not None
    assert rejected.audit.trigger is Trigger.SHORT_EXCEEDS_CASH


# ---------------------------------------------------------------------------
# G2 -- rating matrix: exact case-sensitive membership only
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rating", LEGAL_RATINGS)
def test_each_legal_rating_passes(rating):
    """G2: each of the five exact strings is accepted."""
    decision = make_decision(rating=rating)
    result = evaluate_decision(decision)
    assert result.passed is True
    assert result.audit is None
    assert result.decision is decision, "pass-through must return the input unchanged"


@pytest.mark.parametrize(
    "rating",
    ["buy", "BUY", "Buy ", " Buy", "HOLD ", "Review", "review", "", " ", "Hold\n"],
)
def test_illegal_rating_string_is_rejected(rating):
    """G2: illegal *strings* only -- no trimming, no case folding, no aliases.

    Non-string ratings are MALFORMED_DECISION (ruled in the build session) and
    are asserted by ``test_malformed_input_fails_closed`` instead.
    """
    result = evaluate_decision(make_decision(rating=rating))
    assert result.passed is False
    assert result.audit is not None
    assert result.audit.trigger is Trigger.ILLEGAL_RATING


# ---------------------------------------------------------------------------
# G3 -- zero escapes, asserted arithmetically over the adversarial matrix
# ---------------------------------------------------------------------------

def test_zero_escapes_over_adversarial_matrix():
    """G3 / INV-GUARDRAIL-ZERO-ESCAPE: escapes == 0, counted, not inferred."""
    errors: list[str] = []
    checked = 0

    for label, decision, must_reject in CROSSING_CASES:
        checked += 1
        result = evaluate_decision(decision)
        violations = _verdict_violations(decision, GuardrailLimits())
        if must_reject and result.passed:
            errors.append(f"{label}: crossed a limit but was returned executable")
        if not must_reject and not result.passed:
            errors.append(f"{label}: legal decision was rejected")
        if must_reject and _expected_trigger(violations) is not result.audit.trigger:  # type: ignore[union-attr]
            errors.append(f"{label}: wrong trigger {result.audit.trigger}")  # type: ignore[union-attr]

    assert checked == len(CROSSING_CASES) and checked >= 20
    assert zero_escapes(evaluate_decision) == 0
    assert errors == []


# ---------------------------------------------------------------------------
# G4 -- rejection always yields the legal REVIEW/HOLD fallback
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "decision",
    [
        make_decision(rating="buy"),
        make_decision(size_pct=0.5),
        make_decision(short_amount=5000.0),
        make_decision(rating="Review", size_pct=0.9, short_amount=9000.0),
    ],
    ids=["illegal-rating", "position", "short", "all-three"],
)
def test_rejection_returns_legal_fallback(decision):
    """G4 / INV-RATING-VALIDITY: rating is Hold, never the literal REVIEW."""
    result = evaluate_decision(decision)

    assert result.passed is False
    assert result.decision.rating == "Hold"
    assert result.decision.rating == FALLBACK_RATING
    assert result.decision.rating in VALID_RATINGS
    assert result.decision.rating != "REVIEW"
    assert result.audit is not None
    assert result.audit.action == "REVIEW/HOLD"
    assert result.decision is not decision


# ---------------------------------------------------------------------------
# G5 -- exactly one audit record per rejection, none on pass
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "decision, trigger",
    [
        (make_decision(size_pct=0.1000001), Trigger.POSITION_LIMIT),
        (make_decision(short_amount=1000.5), Trigger.SHORT_EXCEEDS_CASH),
        (make_decision(rating="buy"), Trigger.ILLEGAL_RATING),
    ],
    ids=["position", "short", "rating"],
)
def test_rejection_emits_exactly_one_named_audit_record(decision, trigger):
    """G5: one record naming (a) trigger, (b) observed value, (c) limit."""
    result = evaluate_decision(decision)
    audit = result.audit

    assert audit is not None
    assert isinstance(audit, AuditRecord)
    assert audit.trigger is trigger

    if trigger is Trigger.POSITION_LIMIT:
        assert audit.observed_value == decision.size_pct
        assert audit.configured_limit == GuardrailLimits().max_position_pct
    elif trigger is Trigger.SHORT_EXCEEDS_CASH:
        assert audit.observed_value == decision.short_amount
        assert audit.configured_limit == decision.available_cash * (
            GuardrailLimits().max_short_pct_of_cash
        )
    else:
        assert audit.observed_value == decision.rating
        assert audit.configured_limit == VALID_RATINGS

    for field_name in ("record_id", "action"):
        value = getattr(audit, field_name)
        assert isinstance(value, str) and value.strip()
    assert audit.action == "REVIEW/HOLD"


def test_pass_through_emits_no_audit_record():
    """G5: zero records on pass; the result carries the input unchanged."""
    decision = make_decision()
    result = evaluate_decision(decision)

    assert result.audit is None
    assert result.passed is True
    assert result.decision is decision


# ---------------------------------------------------------------------------
# G6 -- determinism: byte-identical decision and audit record
# ---------------------------------------------------------------------------

def test_two_calls_are_byte_identical():
    """G6: pure function of (decision, limits)."""
    first = evaluate_decision(make_decision(rating="buy", size_pct=0.4))
    second = evaluate_decision(make_decision(rating="buy", size_pct=0.4))

    assert first.audit is not None and second.audit is not None
    assert first.to_dict() == second.to_dict()
    assert first.audit.to_dict() == second.audit.to_dict()
    assert first.audit.record_id == second.audit.record_id
    assert first.decision == second.decision


def test_record_id_is_content_derived():
    """G6 / pinned R5: record_id is a stable hash of the record's content."""
    a = evaluate_decision(make_decision(short_amount=5000.0, available_cash=1000.0))
    b = evaluate_decision(make_decision(short_amount=5000.0, available_cash=1000.0))
    c = evaluate_decision(make_decision(short_amount=6000.0, available_cash=1000.0))

    assert a.audit is not None and b.audit is not None and c.audit is not None
    assert a.audit.record_id == b.audit.record_id
    assert a.audit.record_id != c.audit.record_id  # content changed -> id moved
    assert not a.audit.record_id.isdigit()


# ---------------------------------------------------------------------------
# G7 -- source hygiene (AST allowlist) and module purity
# ---------------------------------------------------------------------------

ALLOWED_IMPORTS = {"dataclasses", "enum", "typing", "hashlib", "json", "math", "__future__"}

FORBIDDEN_IMPORTS = {
    "time",
    "datetime",
    "uuid",
    "random",
    "secrets",
    "os",
    "sys",
    "socket",
    "requests",
    "httpx",
    "urllib",
    "http",
    "ssl",
    "openai",
    "anthropic",
    "langchain",
    "langchain_core",
    "langgraph",
}

FORBIDDEN_CALLS = {
    "datetime.now",
    "datetime.today",
    "datetime.utcnow",
    "time.time",
    "time.monotonic",
    "uuid.uuid4",
    "uuid.uuid1",
    "uuid4",
    "uuid1",
    "random.random",
}


def _ast_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _ast_called_attributes(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            found.add(func.id)
        elif isinstance(func, ast.Attribute):
            parts = [func.attr]
            base = func.value
            while isinstance(base, ast.Attribute):
                parts.append(base.attr)
                base = base.value
            if isinstance(base, ast.Name):
                parts.append(base.id)
            found.add(".".join(reversed(parts)))
    return found


def test_import_hygiene_ast():
    """G7: no network / LLM / clock module reaches the guardrail."""
    assert MODULE_PATH.exists()
    imported = _ast_imports(MODULE_PATH)

    forbidden = imported & FORBIDDEN_IMPORTS
    assert forbidden == set(), f"forbidden imports reached the guardrail: {forbidden}"
    outside = imported - ALLOWED_IMPORTS
    assert outside == set(), f"imports outside the allowlist: {outside}"

    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    function_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "evaluate_decision" in function_names


def test_no_clock_or_uuid_calls():
    """G7: no clock or UUID call anywhere in the guardrail."""
    hits = _ast_called_attributes(MODULE_PATH) & FORBIDDEN_CALLS
    assert hits == set(), f"clock/uuid calls reached the guardrail: {hits}"


def test_no_module_level_mutable_state_is_written():
    """G7: module constants (incl. VALID_RATINGS) are unchanged by evaluation."""
    snapshot = dict(GUARDRAIL_LIMITS)
    ratings = set(VALID_RATINGS)
    precedence = tuple(TRIGGER_PRECEDENCE)

    for _, decision, _ in CROSSING_CASES:
        evaluate_decision(decision)

    assert dict(GUARDRAIL_LIMITS) == snapshot
    assert set(VALID_RATINGS) == ratings
    assert tuple(TRIGGER_PRECEDENCE) == precedence


# ---------------------------------------------------------------------------
# G8 -- configurability shifts the boundary
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "limit, at_limit_passes, above_fails",
    [
        (0.20, 0.20, 0.2000001),
        (0.05, 0.05, 0.0500001),
        (0.0, 0.0, 0.0000001),
    ],
)
def test_configurable_position_limit_shifts_boundary(limit, at_limit_passes, above_fails):
    """G8: the limit is a parameter, not a hard-coded constant."""
    limits = GuardrailLimits(max_position_pct=limit)

    at = evaluate_decision(make_decision(size_pct=at_limit_passes), limits)
    above = evaluate_decision(make_decision(size_pct=above_fails), limits)

    assert at.passed is True
    assert above.passed is False
    assert above.audit is not None
    assert above.audit.configured_limit == limit


def test_default_limits_are_unchanged_by_configuration():
    """G8: construction of other limits must not mutate the default."""
    GuardrailLimits(max_position_pct=0.5)
    assert GuardrailLimits() == GuardrailLimits(max_position_pct=0.10)
    assert evaluate_decision(make_decision(size_pct=0.2)).passed is False


# ---------------------------------------------------------------------------
# G9 -- NEGATIVE test: a guardrail patched to always pass fails the gate
# ---------------------------------------------------------------------------

def test_patched_always_pass_guardrail_fails_zero_escape_gate(monkeypatch):
    """G9: proves G3 is a real gate (`.agent/rules.md` covenant 3)."""
    def always_pass(decision: Decision, limits: GuardrailLimits | None = None) -> GuardrailResult:
        return GuardrailResult(decision=decision, passed=True, audit=None)

    # The patched evaluator routes every crossing straight through.
    assert zero_escapes(always_pass) == sum(1 for _, _, r in CROSSING_CASES if r)
    assert zero_escapes(always_pass) > 0, "the gate would not notice an always-pass guardrail"

    # Through the module reference, exactly as G3 calls it, monkeypatching
    # evaluate_decision must break the gate -- if it does not, G3 is a tautology.
    monkeypatch.setattr(guardrail, "evaluate_decision", always_pass)
    assert zero_escapes(guardrail.evaluate_decision) > 0


# ---------------------------------------------------------------------------
# G-NEW -- multi-violation precedence (pinned R3)
# ---------------------------------------------------------------------------

def test_trigger_precedence_is_total_and_ordered():
    """Pinned R3: one record, named by the highest-precedence trigger."""
    assert tuple(TRIGGER_PRECEDENCE) == (
        Trigger.MALFORMED_DECISION,
        Trigger.ILLEGAL_RATING,
        Trigger.POSITION_LIMIT,
        Trigger.SHORT_EXCEEDS_CASH,
    )
    assert len(set(TRIGGER_PRECEDENCE)) == len(TRIGGER_PRECEDENCE)
    assert set(TRIGGER_PRECEDENCE) == set(Trigger)


@pytest.mark.parametrize(
    "decision, expected",
    [
        (make_decision(rating="buy", size_pct=0.5, short_amount=5000.0), Trigger.ILLEGAL_RATING),
        (make_decision(size_pct=0.5, short_amount=5000.0), Trigger.POSITION_LIMIT),
        (make_decision(rating="buy"), Trigger.ILLEGAL_RATING),
        (make_decision(short_amount=5000.0), Trigger.SHORT_EXCEEDS_CASH),
    ],
    ids=["rating+position+short", "position+short", "rating", "short"],
)
def test_multi_violation_yields_exactly_one_record_with_top_trigger(decision, expected):
    """Pinned R3: multiple violations -> exactly ONE audit record."""
    result = evaluate_decision(decision)

    assert result.passed is False
    assert result.audit is not None
    assert result.audit.trigger is expected
    # Exactly one record: the result carries a single AuditRecord, not a list.
    assert isinstance(result.audit, AuditRecord)


# ---------------------------------------------------------------------------
# G-NEW -- malformed input fails closed (pinned R2)
# ---------------------------------------------------------------------------

MALFORMED_CASES = [
    ("not-a-decision", None),
    ("not-a-decision-dict", {"rating": "Buy"}),
    ("not-a-decision-str", "Buy 0.05"),
    ("size-nan", make_decision(size_pct=float("nan"))),
    ("size-inf", make_decision(size_pct=float("inf"))),
    ("size-negative", make_decision(size_pct=-0.01)),
    ("size-string", make_decision(size_pct="0.05")),
    ("size-bool", make_decision(size_pct=True)),
    ("size-decimal", make_decision(size_pct=Decimal("0.05"))),
    ("short-nan", make_decision(short_amount=float("nan"))),
    ("short-negative", make_decision(short_amount=-1.0)),
    ("short-string", make_decision(short_amount="10")),
    ("cash-nan", make_decision(available_cash=float("nan"))),
    ("cash-negative", make_decision(available_cash=-100.0)),
    ("cash-none", make_decision(available_cash=None)),
    ("rating-list", make_decision(rating=["Buy"])),
    ("rating-bytes", make_decision(rating=b"Buy")),
    # Non-string ratings were ruled MALFORMED_DECISION (later, more specific
    # pin wins over the rating matrix): they are not illegal *strings*.
    ("rating-none", make_decision(rating=None)),
    ("rating-int-zero", make_decision(rating=0)),
    ("rating-float", make_decision(rating=3.5)),
]


@pytest.mark.parametrize(
    "decision", [c[1] for c in MALFORMED_CASES], ids=[c[0] for c in MALFORMED_CASES]
)
def test_malformed_input_fails_closed(decision):
    """Pinned R2: malformed input is rejected, never raises, never passes."""
    result = evaluate_decision(decision)  # type: ignore[arg-type]

    assert result.passed is False
    assert result.audit is not None
    assert result.audit.trigger is Trigger.MALFORMED_DECISION
    assert result.decision.rating == "Hold"
    assert result.decision.rating in VALID_RATINGS
    assert result.audit.action == "REVIEW/HOLD"


def test_malformed_trigger_outranks_every_other_violation():
    """Pinned R2/R3: MALFORMED_DECISION has the highest precedence."""
    result = evaluate_decision(make_decision(rating="buy", size_pct=float("nan")))  # type: ignore[arg-type]
    assert result.audit is not None
    assert result.audit.trigger is Trigger.MALFORMED_DECISION


# ---------------------------------------------------------------------------
# G-NEW -- duplicate/repeated audit record rejection (pinned R5)
# ---------------------------------------------------------------------------

def test_duplicate_record_in_audit_log_is_rejected():
    """Pinned R5: a record_id collision is rejected, never overwritten."""
    log = AuditLog()
    first = evaluate_decision(make_decision(size_pct=0.5)).audit
    assert first is not None

    log.add(first)
    with pytest.raises(GuardrailError):
        log.add(first)

    assert log.records() == (first,)


def test_audit_log_rejects_colliding_ids_from_different_content():
    """Pinned R5: same record_id + different content is a hard failure."""
    log = AuditLog()
    first = evaluate_decision(make_decision(size_pct=0.5)).audit
    second = evaluate_decision(make_decision(size_pct=0.9)).audit
    assert first is not None and second is not None
    assert first.record_id != second.record_id

    forged = AuditRecord(
        record_id=first.record_id,
        trigger=second.trigger,
        observed_value=second.observed_value,
        configured_limit=second.configured_limit,
        action=second.action,
    )
    log.add(first)
    with pytest.raises(GuardrailError):
        log.add(forged)
    assert log.records() == (first,)


# ---------------------------------------------------------------------------
# G-NEW -- limits validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "limits",
    [
        GuardrailLimits(max_position_pct=-0.1),
        GuardrailLimits(max_position_pct=float("nan")),
        GuardrailLimits(max_short_pct_of_cash=-1.0),
        GuardrailLimits(max_short_pct_of_cash=float("nan")),
    ],
)
def test_invalid_limits_raise(limits):
    """A broken configuration is a fault, not a decision: raise, do not reject."""
    with pytest.raises(GuardrailError):
        evaluate_decision(make_decision(), limits)


def test_unbounded_position_limit_is_configurable_not_an_error():
    """`inf` is a legitimate (if unwise) configuration; it must be honoured."""
    limits = GuardrailLimits(max_position_pct=float("inf"))
    assert evaluate_decision(make_decision(size_pct=0.9), limits).passed is True


# ---------------------------------------------------------------------------
# G-ADV -- adversarial compliance block (verification-compliance session)
#
# Every test here pins a condition that the G1-G9 matrix above does NOT exercise:
# degenerate numeric configurations, non-bool flags, malformed instrument ids,
# and the non-finite interaction in `available_cash * max_short_pct_of_cash`.
# The block is additive: no condition above is relaxed.
# ---------------------------------------------------------------------------

_NON_FINITE = (float("inf"), float("-inf"), float("nan"))


@pytest.mark.parametrize("multiplier", _NON_FINITE, ids=[repr(v) for v in _NON_FINITE])
def test_zero_cash_with_non_finite_short_multiplier_never_escapes(multiplier):
    """G-ADV / INV-GUARDRAIL-ZERO-ESCAPE: `0 * inf` is NaN, not a licence.

    The short rule is `reject iff short > cash * multiplier`. With cash == 0 and
    a non-finite multiplier the product is NaN (Python renders `0 * inf` as nan),
    and `short > nan` is False for every short -- so a naive implementation turns
    ANY short against zero cash into a PASS. That is a fail-open at exactly the
    boundary R8 pins (short == cash == 0 accepted, any positive short rejected),
    and it must not depend on the multiplier being finite. A non-finite
    multiplier is also an unusable configuration, so raising GuardrailError is
    equally compliant; silently passing is not.
    """
    limits = GuardrailLimits(max_short_pct_of_cash=multiplier)
    decision = make_decision(short_amount=5000.0, available_cash=0.0)

    try:
        result = evaluate_decision(decision, limits)
    except GuardrailError:
        return  # configuration refused: fail closed, acceptable

    assert result.passed is False, (
        f"zero cash + short multiplier {multiplier!r} let a 5000.0 short escape"
    )
    assert result.audit is not None
    assert result.audit.trigger is Trigger.SHORT_EXCEEDS_CASH
    assert result.decision.rating in VALID_RATINGS


@pytest.mark.parametrize("multiplier", _NON_FINITE, ids=[repr(v) for v in _NON_FINITE])
def test_zero_cash_zero_short_with_non_finite_multiplier_is_not_a_crash(multiplier):
    """G-ADV / pinned R8: the accepted case stays accepted (or is refused cleanly).

    `short == cash == 0` is accepted by the literal pin. With a non-finite
    multiplier the implementation may keep accepting it or refuse the
    configuration, but it must never raise an *unhandled* exception (e.g. a bare
    `ValueError` escaping from an arithmetic comparison) and must never emit an
    audit record on a pass.
    """
    limits = GuardrailLimits(max_short_pct_of_cash=multiplier)
    try:
        result = evaluate_decision(
            make_decision(short_amount=0.0, available_cash=0.0), limits
        )
    except GuardrailError:
        return

    assert result.passed is True
    assert result.audit is None


@pytest.mark.parametrize(
    "field, limits",
    [
        ("max_position_pct", GuardrailLimits(max_position_pct=True)),
        ("max_position_pct", GuardrailLimits(max_position_pct=False)),
        ("max_short_pct_of_cash", GuardrailLimits(max_short_pct_of_cash=True)),
        ("max_short_pct_of_cash", GuardrailLimits(max_short_pct_of_cash=False)),
        ("max_position_pct", GuardrailLimits(max_position_pct="0.10")),
        ("max_short_pct_of_cash", GuardrailLimits(max_short_pct_of_cash=None)),
        ("max_position_pct", GuardrailLimits(max_position_pct=Decimal("0.10"))),
    ],
    ids=[
        "pos-true",
        "pos-false",
        "short-true",
        "short-false",
        "pos-str",
        "short-none",
        "pos-decimal",
    ],
)
def test_bool_and_non_numeric_limits_are_configuration_faults(field, limits):
    """G-ADV: bool is not a number; guards the `isinstance(value, bool)` branch.

    `True`/`False` are `int` subclasses, so without the explicit exclusion
    `max_position_pct=False` would silently mean "reject any position at all"
    and `True` would silently mean 100%. Non-numeric types would fail later
    inside the comparison (a TypeError, not a GuardrailError). All of them are
    configuration faults and must raise GuardrailError naming the field.
    """
    with pytest.raises(GuardrailError) as excinfo:
        evaluate_decision(make_decision(), limits)
    assert field in str(excinfo.value)


@pytest.mark.parametrize("field", ["max_position_pct", "max_short_pct_of_cash"])
@pytest.mark.parametrize("value", [float("nan"), -0.1, -1000.0, -float("inf")])
def test_nan_and_negative_limits_are_configuration_faults(field, value):
    """G-ADV: NaN and negative limits raise for BOTH fields (not just short)."""
    limits = GuardrailLimits(**{field: value})
    with pytest.raises(GuardrailError) as excinfo:
        evaluate_decision(make_decision(), limits)
    assert field in str(excinfo.value)


def test_limits_must_be_a_guardrail_limits_instance():
    """G-ADV: a plain dict of "limits" is a fault, not a silently-defaulted run."""
    for bogus in ({"max_position_pct": 0.10}, None, 0.10, ("0.10", "1.0")):
        with pytest.raises(GuardrailError):
            evaluate_decision(make_decision(), bogus)  # type: ignore[arg-type]


@pytest.mark.parametrize("cash", [0.0, 0.0, 1.5, 1000.0])  # noqa: PT014 -- the repeated 0.0 is deliberate
def test_short_product_is_computed_from_available_cash(cash):
    """G-ADV: the boundary really is `available_cash * max_short_pct_of_cash`.

    Positioned just below / exactly at / just above the product, for several
    cascading cash values (0.0 twice, to catch any stateful leak between
    calls). Only the product may decide the verdict.
    """
    multiplier = 0.5  # non-default, finite: the product is exercised, not 1.0
    limits = GuardrailLimits(max_short_pct_of_cash=multiplier)
    product = cash * multiplier

    at = evaluate_decision(make_decision(short_amount=product, available_cash=cash), limits)
    above = evaluate_decision(
        make_decision(short_amount=product + 0.01, available_cash=cash), limits
    )

    assert at.passed is True
    assert above.passed is False
    assert above.audit is not None
    assert above.audit.trigger is Trigger.SHORT_EXCEEDS_CASH
    assert above.audit.configured_limit == product
    # And the product agrees with the vendored default constant being a multiplier.
    assert (
        evaluate_decision(
            make_decision(short_amount=cash * GUARDRAIL_LIMITS["max_short_pct_of_cash"] + 0.01,
                          available_cash=cash)
        ).passed
        is False
    )


def test_zero_cash_with_default_limits_rejects_any_positive_short():
    """G-ADV / pinned R8: zero cash is not a wildcard, under the default limits."""
    for short_amount in (1e-12, 0.01, 1.0, 1e12):
        result = evaluate_decision(
            make_decision(short_amount=short_amount, available_cash=0.0)
        )
        assert result.passed is False, f"short {short_amount} escaped against zero cash"
        assert result.audit is not None
        assert result.audit.trigger is Trigger.SHORT_EXCEEDS_CASH


@pytest.mark.parametrize(
    "instrument_id",
    [b"AAPL", 123, 1.5, True, ["AAPL"], ("AAPL",), {"ticker": "AAPL"}, object],
)
def test_malformed_instrument_id_fails_closed(instrument_id):
    """G-ADV / pinned R2: a non-string instrument_id is MALFORMED_DECISION.

    An instrument id is how execution addresses a book; a truthy container or
    an `object` class is not a ticker, so it must be rejected, never passed
    through, and the fallback must not carry the bad id forward.
    """
    result = evaluate_decision(make_decision(instrument_id=instrument_id))  # type: ignore[arg-type]

    assert result.passed is False
    assert result.audit is not None
    assert result.audit.trigger is Trigger.MALFORMED_DECISION
    assert result.audit.observed_value == "instrument-not-a-string"
    assert result.decision.rating in VALID_RATINGS
    assert result.decision.instrument_id is None


@pytest.mark.parametrize(
    "instrument_id", [None, "AAPL", "", "  ", "BRK.B", "6758.T", "AAPL\n"]
)
def test_stringly_typed_instrument_id_is_accepted_unchanged(instrument_id):
    """G-ADV boundary: type is the only requirement; content is not re-judged.

    Pinned scope: the guardrail validates the *type* of instrument_id. It does
    not own ticker syntax, so `""` and `"  "` pass this check and remain the
    downstream execution module's concern (recorded as a scope limit below).
    """
    result = evaluate_decision(make_decision(instrument_id=instrument_id))
    assert result.passed is True
    assert result.decision.instrument_id == instrument_id


def test_malformed_instrument_outranks_a_rating_violation():
    """G-ADV / pinned R3: instrument malformation is MALFORMED, so it wins."""
    result = evaluate_decision(make_decision(rating="buy", instrument_id=123))  # type: ignore[arg-type]
    assert result.audit is not None
    assert result.audit.trigger is Trigger.MALFORMED_DECISION


def test_malformed_decision_observation_is_json_serialisable():
    """G-ADV / G6: a malformed observation must not poison record identity."""
    import json

    bad = make_decision(instrument_id={"ticker": "AAPL"})  # type: ignore[arg-type]
    first = evaluate_decision(bad)
    second = evaluate_decision(bad)

    assert first.audit is not None and second.audit is not None
    json.dumps(first.to_dict(), allow_nan=False)
    assert first.to_dict() == second.to_dict()
    assert first.audit.record_id == second.audit.record_id


# ---------------------------------------------------------------------------
# G-EDGE -- no "same object handed back" tautology
# ---------------------------------------------------------------------------

def test_result_is_a_typed_result_object():
    """Pinned R6: passed <-> audit is None, and decisions are wrapped."""
    passed = evaluate_decision(make_decision())
    rejected = evaluate_decision(make_decision(rating="buy"))

    assert isinstance(passed, GuardrailResult)
    assert isinstance(rejected, GuardrailResult)
    assert passed.passed is True and passed.audit is None
    assert rejected.passed is False and rejected.audit is not None
    assert rejected.audit.trigger in set(Trigger)
    assert rejected.decision.rating in VALID_RATINGS

