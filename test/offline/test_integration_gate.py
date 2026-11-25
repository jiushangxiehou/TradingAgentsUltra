"""OFFLINE gate-support tests (ADR-006, REQ-HARD-GUARDRAIL, INV-RATING-VALIDITY).

Requires no API, no network, no clock. Every verdict is produced by the real
frozen ``evaluate_decision``; the gate only applies it to a state.

Invariants under test
---------------------
INV-RATING-VALIDITY       : a rejection's rating is a legal tier (exactly "Hold");
                            "REVIEW" is never written as a rating.
INV-GUARDRAIL-ZERO-ESCAPE : a rejected decision's text can no longer present
                            itself as the executed call.

Acceptance conditions B1-B8 are the integration memo's fallback-banner and
mutation-table pins.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from src.guardrail import (
    AUDIT_ACTION_REVIEW_HOLD,
    FALLBACK_RATING,
    VALID_RATINGS,
    Decision,
    GuardrailLimits,
    Trigger,
    evaluate_decision,
)
from src.integration import gate_support
from src.integration.gate_support import GATE_KEYS, apply_guardrail, fallback_text

pytestmark = pytest.mark.offline

MODULE_PATH = pathlib.Path(gate_support.__file__)

ORIGINAL_DECISION = "**Rating**: Buy\n\n**Executive Summary**: add to the position."

# The keys the gate publishes. Nothing else in the state may change.
ALL_STATE_KEYS = (
    "company_of_interest", "trade_date", "market_report", "sentiment_report",
    "news_report", "fundamentals_report", "investment_debate_state",
    "investment_plan", "trader_investment_plan", "risk_debate_state",
    "final_trade_decision", "final_rating",
)

# Evidence the gate must never touch: reports, plans and debate histories.
EVIDENCE_KEYS = tuple(
    key for key in ALL_STATE_KEYS
    if key not in ("final_trade_decision", "final_rating")
)


def make_state(**overrides) -> dict:
    state = {
        "company_of_interest": "NVDA",
        "trade_date": "2026-11-24",
        "market_report": "Market report.",
        "sentiment_report": "Sentiment report.",
        "news_report": "News report.",
        "fundamentals_report": "Fundamentals report.",
        "investment_debate_state": {"bull_history": "b", "bear_history": "s", "history": "h",
                                    "current_response": "c"},
        "investment_plan": "**Recommendation**: Overweight",
        "trader_investment_plan": "**Action**: Buy\n\n**Position Sizing**: 5% of portfolio",
        "risk_debate_state": {"aggressive_history": "a", "conservative_history": "c",
                              "neutral_history": "n", "history": "h"},
        "final_trade_decision": ORIGINAL_DECISION,
        "final_rating": "Buy",
    }
    state.update(overrides)
    return state


def reject(size_pct=0.5, short_amount=0.0, cash=10_000.0, rating="Buy"):
    return evaluate_decision(
        Decision(rating=rating, size_pct=size_pct, short_amount=short_amount,
                 available_cash=cash, instrument_id="NVDA")
    )


def accept(size_pct=0.05, short_amount=0.0, cash=10_000.0, rating="Buy"):
    return evaluate_decision(
        Decision(rating=rating, size_pct=size_pct, short_amount=short_amount,
                 available_cash=cash, instrument_id="NVDA")
    )


# ---------------------------------------------------------------------------
# B0 -- offline marker
# ---------------------------------------------------------------------------

def test_file_is_marked_offline():
    """Pinned R1: every test in this file is offline-marked."""
    assert gate_support.apply_guardrail
    assert pytestmark == pytest.mark.offline


# ---------------------------------------------------------------------------
# B1 -- a pass changes nothing but the payload
# ---------------------------------------------------------------------------

def test_pass_leaves_the_rating_alone():
    """Pinned: on a pass, ``final_rating`` is NOT rewritten."""
    state = make_state(final_rating="Overweight")
    out, payload = apply_guardrail(accept(rating="Overweight"), state)
    assert out["final_rating"] == "Overweight"
    assert out["final_trade_decision"] == ORIGINAL_DECISION
    assert payload["passed"] is True
    assert payload["action"] is None
    assert payload["audit"] is None
    assert out["guardrail"] == payload


def test_pass_touches_no_evidence_key():
    state = make_state()
    out, _ = apply_guardrail(accept(), state)
    for key in EVIDENCE_KEYS:
        assert out[key] is state[key] or out[key] == state[key], key
    assert set(out) - set(state) == set(GATE_KEYS)


def test_apply_never_mutates_the_callers_mapping():
    """The agents' own state stays readable after the gate has run."""
    state = make_state()
    before = dict(state)
    apply_guardrail(reject(), state)
    assert state == before


# ---------------------------------------------------------------------------
# B2 -- a rejection writes exactly the fallback
# ---------------------------------------------------------------------------

def test_rejection_writes_hold_and_a_review_hold_action():
    """INV-RATING-VALIDITY: the fallback rating is a legal tier, exactly Hold;
    the review signal lives in the audit action, never in the rating."""
    out, payload = apply_guardrail(reject(), make_state())
    assert out["final_rating"] == FALLBACK_RATING == "Hold"
    assert out["final_rating"] in VALID_RATINGS
    assert payload["action"] == AUDIT_ACTION_REVIEW_HOLD == "REVIEW/HOLD"
    assert payload["passed"] is False
    assert payload["audit"]["action"] == AUDIT_ACTION_REVIEW_HOLD


def test_rejection_carries_exactly_one_named_audit_record():
    _state, payload = apply_guardrail(reject(), make_state())
    audit = payload["audit"]
    assert audit["trigger"] == Trigger.POSITION_LIMIT.value
    assert audit["record_id"].startswith("gr-")
    assert audit["observed_value"] == "0.5"
    assert audit["configured_limit"] == f"{GuardrailLimits().max_position_pct!r}"


def test_review_is_never_written_as_a_rating():
    """Pinned: upstream reserves "REVIEW" for an unreadable decision; writing it
    as our rating would make its CLI announce a parsing failure instead of ours,
    and would violate INV-RATING-VALIDITY."""
    out, _ = apply_guardrail(reject(), make_state(final_rating="REVIEW"))
    assert out["final_rating"] != "REVIEW"
    assert out["final_rating"] == "Hold"


def test_illegal_rating_rejection_is_held():
    out, payload = apply_guardrail(reject(rating="REVIEW"), make_state(final_rating="REVIEW"))
    assert payload["audit"]["trigger"] == Trigger.ILLEGAL_RATING.value
    assert out["final_rating"] == "Hold"


def test_rejection_touches_no_evidence_key():
    state = make_state()
    out, _ = apply_guardrail(reject(), state)
    for key in EVIDENCE_KEYS:
        assert out[key] == state[key], key
    assert set(out) - set(state) == set(GATE_KEYS)


# ---------------------------------------------------------------------------
# B3 -- the original decision is preserved verbatim
# ---------------------------------------------------------------------------

def test_original_decision_survives_as_a_verbatim_substring():
    """Pinned: the evidence is not edited; only a banner is prepended."""
    original = make_state()["final_trade_decision"]
    out, _ = apply_guardrail(reject(), make_state())
    assert original in out["final_trade_decision"]
    assert out["final_trade_decision"].endswith(original)


def test_banner_states_every_field_deterministically():
    out, payload = apply_guardrail(reject(), make_state())
    text = out["final_trade_decision"]
    audit = payload["audit"]
    lines = text.splitlines()
    assert lines[0] == "**Rating**: Hold"
    assert lines[2] == "> **Guardrail: REVIEW/HOLD \u2014 rejected before execution.**"
    assert f"> trigger: {audit['trigger']}" in lines
    assert f"> record: {audit['record_id']}" in lines
    assert "> observed: 0.5" in lines
    assert "> limit: 0.1" in lines
    assert "> The original decision is preserved below for audit; it is not the executed rating." in lines
    assert "---" in lines


def test_banner_id_is_deterministic_and_follows_the_record():
    first = fallback_text(reject(), original=ORIGINAL_DECISION)
    second = fallback_text(reject(), original=ORIGINAL_DECISION)
    assert first == second
    assert reject().audit.record_id in first


def test_two_gated_states_of_equal_inputs_are_byte_identical():
    """Pinned: equal inputs, byte-identical state and payload."""
    import json

    first, first_payload = apply_guardrail(reject(), make_state())
    second, second_payload = apply_guardrail(reject(), make_state())
    assert first == second
    assert json.dumps(first_payload, sort_keys=True) == json.dumps(second_payload, sort_keys=True)


def test_empty_or_missing_original_yields_the_banner_alone():
    """A malformed state must not crash the gate that is protecting it."""
    for original in (None, "", {}):
        out, _ = apply_guardrail(reject(), make_state(final_trade_decision=original))
        assert out["final_trade_decision"].startswith("**Rating**: Hold")
        assert "---" not in out["final_trade_decision"]


# ---------------------------------------------------------------------------
# B4 -- set-valued limits render deterministically
# ---------------------------------------------------------------------------

def test_set_valued_limit_is_sorted_not_raw_str():
    """Pinned: ``str(set)`` orders by hash seed; the banner must not."""
    out, _ = apply_guardrail(reject(rating="REVIEW"), make_state())
    text = out["final_trade_decision"]
    assert "> limit: {Buy, Hold, Overweight, Sell, Underweight}" in text.splitlines()
    assert "frozenset(" not in text


def test_set_valued_audit_field_is_rendered_not_raw():
    """The state log is JSON: a set-valued limit is written as a sorted list."""
    _, payload = apply_guardrail(reject(rating="REVIEW"), make_state())
    # Rendered, not raw: an AuditRecord keeps the legal-rating set as a set,
    # which is unordered and would make an identical rejection log differently.
    assert payload["audit"]["configured_limit"] == "{Buy, Hold, Overweight, Sell, Underweight}"
    assert payload["audit"]["observed_value"] == "REVIEW"


def test_set_rendering_is_stable_across_calls():
    seen = {fallback_text(reject(rating="REVIEW"), original="x") for _ in range(5)}
    assert len(seen) == 1


@pytest.mark.parametrize(
    "value,expected",
    [
        (0.1001, "0.1001"),
        (0.1, "0.1"),
        (0.0, "0.0"),
        ("text", "text"),
        (7, "7"),
        (True, "true"),
        (["b", "a"], "[b, a]"),
        ((1, 2), "[1, 2]"),
        ({"b", "a"}, "{a, b}"),
        (frozenset({"c", "a", "b"}), "{a, b, c}"),
    ],
)
def test_value_rendering(value, expected):
    """The banner's observed/limit fields, in their deterministic form."""
    assert gate_support._render_value(value) == expected


# ---------------------------------------------------------------------------
# B5 -- the mutation table, key by key
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict,expected_rating", [(accept, "Buy"), (reject, "Hold")])
def test_mutation_table_keys(verdict, expected_rating):
    state = make_state()
    out, _ = apply_guardrail(verdict(), state)
    assert set(out) == set(state) | {"guardrail"}
    assert out["final_rating"] == expected_rating
    for key in EVIDENCE_KEYS:
        assert out[key] == state[key], key


MUTATION_TABLE = (
    # (verdict, key, expected value)
    (accept, "final_rating", "unchanged"),
    (accept, "final_trade_decision", "unchanged"),
    (reject, "final_rating", "Hold"),
    (reject, "final_trade_decision", "banner+original"),
)


@pytest.mark.parametrize(
    "verdict,key,expected",
    MUTATION_TABLE,
    ids=[f"{v.__name__}-{k}" for v, k, _ in MUTATION_TABLE],
)
def test_mutation_table_cell(verdict, key, expected):
    """The pinned mutation table, cell by cell: which key changes, and how."""
    state = make_state()
    out, _ = apply_guardrail(verdict(), state)
    if expected == "unchanged":
        assert out[key] == state[key]
    elif expected == "Hold":
        assert out[key] == FALLBACK_RATING
    else:
        assert out[key] != state[key]
        assert out[key].startswith("**Rating**: Hold")
        assert out[key].endswith(state[key])


def test_payload_shape_is_stable():
    _, payload = apply_guardrail(reject(), make_state())
    assert set(payload) == {"passed", "action", "audit", "decision", "notes"}
    assert payload["decision"]["rating"] == "Hold"
    assert payload["decision"]["size_pct"] == {"__float__": (0.5).hex()}
    assert payload["notes"] == []


def test_notes_are_passed_through_in_order():
    _, payload = apply_guardrail(reject(), make_state(), notes=("GUARDRAIL_ERROR", "SIZE_DISAGREEMENT"))
    assert payload["notes"] == ["GUARDRAIL_ERROR", "SIZE_DISAGREEMENT"]


def test_payload_is_json_serialisable():
    import json

    for verdict in (accept(), reject(rating="REVIEW")):
        _, payload = apply_guardrail(verdict, make_state())
        json.dumps(payload)


# ---------------------------------------------------------------------------
# B6 -- the negative test that keeps B2 honest
# ---------------------------------------------------------------------------

def test_patched_always_pass_guardrail_would_be_caught(monkeypatch):
    """INV-GUARDRAIL-ZERO-ESCAPE: if the gate ignored the verdict, no state would
    ever be held -- so the assertions above would be vacuous."""
    from src.guardrail import GuardrailResult

    def always_pass(decision, limits=None):
        return GuardrailResult(decision=decision, passed=True, audit=None)

    out, payload = apply_guardrail(always_pass(reject().decision), make_state())
    assert payload["passed"] is True
    assert out["final_rating"] == "Buy"          # the escape this test exposes
    assert payload["action"] is None


# ---------------------------------------------------------------------------
# B7 -- purity (AST)
# ---------------------------------------------------------------------------

# hashlib is allowed for the config-error record id: content-derived identity
# needs a digest, and a digest needs no clock and no entropy.
ALLOWED_IMPORTS = {"dataclasses", "typing", "hashlib", "__future__", "src"}

FORBIDDEN_IMPORTS = {
    "os", "sys", "time", "datetime", "random", "uuid", "secrets", "socket",
    "requests", "httpx", "urllib", "http", "ssl", "yfinance", "json",
    "tradingagents", "cli", "langchain", "langchain_core", "langgraph",
}

FORBIDDEN_CALLS = {
    "datetime.now", "datetime.today", "datetime.utcnow",
    "time.time", "time.monotonic", "uuid.uuid4", "uuid.uuid1",
    "uuid4", "uuid1", "random.random",
}


def _ast_imports(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
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
            parts, base = [func.attr], func.value
            while isinstance(base, ast.Attribute):
                parts.append(base.attr)
                base = base.value
            if isinstance(base, ast.Name):
                parts.append(base.id)
            found.add(".".join(reversed(parts)))
    return found


def test_gate_import_hygiene():
    imported = _ast_imports(MODULE_PATH)
    assert imported & FORBIDDEN_IMPORTS == set(), imported & FORBIDDEN_IMPORTS
    assert imported - ALLOWED_IMPORTS == set(), imported - ALLOWED_IMPORTS


def test_gate_has_no_clock_or_random_calls():
    assert _ast_called_attributes(MODULE_PATH) & FORBIDDEN_CALLS == set()


def test_gate_is_importable_without_the_framework(monkeypatch):
    """A pure module must be usable in a process that never loaded the baseline.

    Asserted by IMPORT, in a subprocess-free way: the module is re-imported with
    the baseline blocked from being imported at all. A whole-session
    ``sys.modules`` check would only measure test order -- another test file that
    legitimately imports the baseline would make this fail for no reason.
    """
    import importlib
    import importlib.abc
    import sys

    class Refuse(importlib.abc.MetaPathFinder):
        """Refuse every ``tradingagents.*`` import for the duration."""

        def find_spec(self, fullname, path=None, target=None):
            if fullname == "tradingagents" or fullname.startswith("tradingagents."):
                raise ImportError(f"the baseline must not be imported: {fullname}")

    monkeypatch.delitem(sys.modules, "tradingagents", raising=False)
    for name in [n for n in sys.modules if n.split(".")[0] == "tradingagents"]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setattr(sys, "meta_path", [Refuse(), *sys.meta_path])
    monkeypatch.delitem(sys.modules, "src.integration.gate_support", raising=False)
    try:
        module = importlib.import_module("src.integration.gate_support")
        assert module.apply_guardrail is not None
    finally:
        monkeypatch.undo()
        sys.modules.pop("src.integration.gate_support", None)
        importlib.import_module("src.integration.gate_support")
