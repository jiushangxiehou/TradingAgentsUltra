"""OFFLINE tests for the blocking gates themselves (D7, ADR-008/ADR-009).

A gate that cannot fail is not a gate, so every gate gets negative tests here:
an unapproved test must be rejected, a code change without the AI-use log must
be rejected, an altered baseline file without a declaration must be rejected,
and a wrong expectation in the fixed evaluation set must fail the replay.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from scripts import gate_ai_use_log, gate_semantic_eval, gate_test_approval, safety_checks

pytestmark = pytest.mark.offline


# ---------------------------------------------------------------------------
# Gate 6 — AI-use log
# ---------------------------------------------------------------------------

def test_docs_only_change_needs_no_log():
    ok, message, code, log = gate_ai_use_log.evaluate(["README.md", "docs/req/requirements.yaml"])
    assert ok is True
    assert code == [] and log == []


def test_code_change_without_log_fails():
    ok, message, code, log = gate_ai_use_log.evaluate(["src/guardrail.py"])
    assert ok is False
    assert "without updating" in message
    assert code == ["src/guardrail.py"] and log == []


def test_code_change_with_log_passes():
    changed = ["src/guardrail.py", "docs/ai-use-log.yaml"]
    ok, message, code, log = gate_ai_use_log.evaluate(changed)
    assert ok is True
    assert log == ["docs/ai-use-log.yaml"]


def test_test_and_prompt_changes_count_as_code():
    ok, _, code, _ = gate_ai_use_log.evaluate(["test/offline/test_gates.py", "prompts/prompt_v1.1.yaml"])
    assert ok is False
    assert len(code) == 2


# ---------------------------------------------------------------------------
# Gate 1 — test approval
# ---------------------------------------------------------------------------

APPROVALS = [
    {
        "id": "TA-X",
        "tests": ["test/offline/test_guardrail.py"],
        "approved_by": "Reviewer (00000000)",
        "approved_at": "2026-11-25",
        "rationale": "example",
    }
]


def test_is_test_path():
    assert gate_test_approval.is_test_path("test/offline/test_x.py") is True
    assert gate_test_approval.is_test_path("tests/test_x.py") is True
    assert gate_test_approval.is_test_path("src/guardrail.py") is False
    assert gate_test_approval.is_test_path("test/README.md") is False


def test_manifest_requires_named_approver_and_date():
    bad = "approvals:\n  - id: TA-1\n    tests: [test/x.py]\n"
    with pytest.raises(ValueError, match="missing"):
        gate_test_approval.parse_manifest(bad)


def test_manifest_rejects_empty_test_list():
    bad = (
        "approvals:\n"
        "  - id: TA-1\n"
        "    tests: []\n"
        "    approved_by: A (00000000)\n"
        "    approved_at: '2026-11-25'\n"
        "    rationale: x\n"
    )
    with pytest.raises(ValueError):
        gate_test_approval.parse_manifest(bad)


def test_unapproved_test_change_fails_the_gate():
    verdict = gate_test_approval.evaluate(
        ["test/offline/test_new_feature.py", "src/guardrail.py"], APPROVALS
    )
    assert verdict["ok"] is False
    assert verdict["unapproved"] == ["test/offline/test_new_feature.py"]


def test_approved_test_change_passes_the_gate():
    verdict = gate_test_approval.evaluate(["test/offline/test_guardrail.py"], APPROVALS)
    assert verdict["ok"] is True
    assert verdict["unapproved"] == []


def test_non_test_change_is_not_approval_gated():
    verdict = gate_test_approval.evaluate(["src/guardrail.py"], APPROVALS)
    assert verdict["ok"] is True
    assert verdict["tests"] == []


def test_globs_cover_a_family_of_tests():
    approvals = [dict(APPROVALS[0], tests=["test/offline/*.py"])]
    verdict = gate_test_approval.evaluate(["test/offline/test_anything.py"], approvals)
    assert verdict["ok"] is True


# ---------------------------------------------------------------------------
# Gate 4 — semantic evaluation
# ---------------------------------------------------------------------------

def test_fixed_set_replays_green():
    report = gate_semantic_eval.run()
    assert report["ok"] is True
    assert report["decisions"]["escapes"] == 0
    assert report["prompt_worst"] >= report["thresholds"]["prompt_constraint_retention"]


def test_wrong_expectation_fails_the_replay(tmp_path):
    fixed = gate_semantic_eval.load_fixed_set()
    bad = json.loads(json.dumps(fixed))
    bad["decision_cases"][0]["expect_passed"] = not bad["decision_cases"][0]["expect_passed"]
    path = tmp_path / "fixed-set.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    report = gate_semantic_eval.run(path)
    assert report["ok"] is False
    assert any(not row["matched"] for row in report["decisions"]["rows"])


def test_missing_prompt_constraint_fails(tmp_path):
    fixed = gate_semantic_eval.load_fixed_set()
    bad = json.loads(json.dumps(fixed))
    bad["prompt_constraints"][0]["constraints"].append("A constraint that is not in the prompt")
    bad["thresholds"]["prompt_constraint_retention"] = 1.0
    path = tmp_path / "fixed-set-bad-prompt.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    report = gate_semantic_eval.run(path)
    assert report["ok"] is False
    assert report["prompt_worst"] < report["thresholds"]["prompt_constraint_retention"]


def test_model_baseline_change_is_detected(tmp_path):
    spec = {"file": ".env.example", "keys": {"TRADINGAGENTS_LLM_PROVIDER": "not-deepseek"}}
    result = gate_semantic_eval.check_model_baseline(spec)
    assert result["ok"] is False
    assert "TRADINGAGENTS_LLM_PROVIDER" in result["mismatches"]


# ---------------------------------------------------------------------------
# Gate 2 — safety-path checks
# ---------------------------------------------------------------------------

def test_safety_checks_all_pass_on_this_tree():
    results = safety_checks.run_all()
    failures = [row for row in results if not row["ok"]]
    assert failures == []


def test_pure_module_with_a_forbidden_import_is_reported(tmp_path, monkeypatch):
    module = tmp_path / "impure.py"
    module.write_text("import requests\nimport time\n", encoding="utf-8")
    monkeypatch.setattr(safety_checks, "ROOT", tmp_path)
    element_map = {
        "pure_modules": ["impure.py"],
        "pure_module_import_allowlist": {"impure.py": ["dataclasses"]},
    }
    results = safety_checks.check_contract(element_map)
    imports_row = [row for row in results if row["check"] == "contract/imports"][0]
    assert imports_row["ok"] is False
    assert "requests" in imports_row["detail"]


def test_permission_default_allow_is_reported(tmp_path):
    path = tmp_path / "permissions.jsonc"
    path.write_text('{"default": {"read": true, "write": false}, "roles": {}}', encoding="utf-8")
    results = safety_checks.check_permissions(path)
    deny = [row for row in results if row["check"] == "permission/default-deny"][0]
    assert deny["ok"] is False


# ---------------------------------------------------------------------------
# ADR-008 — the declared baseline overrides
# ---------------------------------------------------------------------------

def _pinned_rows() -> list[tuple[str, str]]:
    manifest = (safety_checks.ROOT / "scripts" / "baseline" / "blob-sha-working-tree.txt").read_text(
        encoding="utf-8"
    )
    return [tuple(line.split("\t")) for line in manifest.splitlines() if line]


def _fingerprint(data: bytes) -> str:
    """SHA-256 with CRLF folded to LF — the same rule as the verifier."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def test_every_altered_pinned_file_is_declared_and_vice_versa():
    overrides = json.loads((safety_checks.ROOT / "scripts" / "baseline-overrides.json").read_text(encoding="utf-8"))
    declared = {row["path"] for row in overrides["dev_overrides"]} | {
        row["path"] for row in overrides["project_owned"]
    }
    altered = {
        rel
        for sha, rel in _pinned_rows()
        if (safety_checks.ROOT / rel).is_file()
        and _fingerprint((safety_checks.ROOT / rel).read_bytes()) != sha
    }
    undeclared = sorted(altered - declared)
    stale = sorted(declared - altered)
    assert altered == declared, f"undeclared={undeclared}, stale={stale}"


def test_baseline_verifier_passes_strictly():
    proc = subprocess.run(
        [sys.executable, "scripts/verify_baseline.py", "--strict"],
        cwd=safety_checks.ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout
