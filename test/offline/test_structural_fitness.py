"""OFFLINE structural fitness tests (D3/D4, ADR-007/ADR-008).

The structural tier of the three-tier verification strategy: imports, module
boundaries, permissions, and the architectural fitness function that checks the
element map against the code that actually exists. These are the checks the
project previously called a TODO.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

from scripts import safety_checks

pytestmark = pytest.mark.offline

ROOT = Path(__file__).resolve().parents[2]
ELEMENT_MAP = json.loads((ROOT / "scripts" / "element-map.json").read_text(encoding="utf-8"))
OVERRIDES = json.loads((ROOT / "scripts" / "baseline-overrides.json").read_text(encoding="utf-8"))
STUDENT_ID = re.compile(r"\(\d{8}\)")


# ---------------------------------------------------------------------------
# ADR-007 — one element, one owning module, one importable contract
# ---------------------------------------------------------------------------

def test_submission_tree_is_declared_as_dev():
    assert ELEMENT_MAP["submission_tree"] == "dev"
    assert (ROOT / "docs" / "architecture" / "adr" / "007-dev-submission-element-map.md").is_file()


def test_every_element_has_existing_modules_and_facade():
    for element in ELEMENT_MAP["elements"]:
        for rel in element["modules"]:
            assert (ROOT / rel).is_file(), f"{element['element']}: missing module {rel}"
        assert (ROOT / element["facade"]).is_file(), f"{element['element']}: missing facade"


def test_every_facade_exports_its_declared_contract():
    for element in ELEMENT_MAP["elements"]:
        facade = element["facade"].replace("/", ".").removesuffix(".py")
        module = importlib.import_module(facade)
        missing = [name for name in element["facade_exports"] if not hasattr(module, name)]
        assert missing == [], f"{element['element']}: facade {facade} misses {missing}"


def test_every_element_has_an_owner_with_a_student_id():
    for element in ELEMENT_MAP["elements"]:
        assert STUDENT_ID.search(element["owner"]), f"{element['element']}: owner has no student id"


def test_structural_constraints_document_names_the_modules():
    doc = (ROOT / "docs" / "code-governance" / "structural-constraints.md").read_text(encoding="utf-8")
    for element in ELEMENT_MAP["elements"]:
        assert element["element"] in doc.lower(), f"element not documented: {element['element']}"
        for rel in element["modules"]:
            assert rel in doc, f"module not documented: {rel}"


def test_pure_modules_do_not_import_the_framework():
    for rel in ELEMENT_MAP["pure_modules"]:
        source = (ROOT / rel).read_text(encoding="utf-8")
        assert "tradingagents" not in source, f"{rel} must stay framework-free (ADR-007)"


def test_facades_import_the_runtime_not_a_copy():
    for element in ELEMENT_MAP["elements"]:
        if element["facade"] in element["modules"]:
            continue
        source = (ROOT / element["facade"]).read_text(encoding="utf-8")
        assert "from tradingagents" in source or "import tradingagents" in source, (
            f"{element['facade']} is expected to re-export the runtime module"
        )


# ---------------------------------------------------------------------------
# ADR-008 — declared baseline overrides
# ---------------------------------------------------------------------------

def test_override_manifest_is_complete_and_owned():
    pinned = {
        rel
        for _, rel in (
            line.split("\t")
            for line in (ROOT / "scripts" / "baseline" / "blob-sha-working-tree.txt").read_text(encoding="utf-8").splitlines()
            if line
        )
    }
    rows = OVERRIDES["dev_overrides"]
    assert len(rows) == 19
    for row in rows:
        assert row["path"] in pinned, f"override not a pinned file: {row['path']}"
        assert (ROOT / row["path"]).is_file(), f"override file missing: {row['path']}"
        assert STUDENT_ID.search(row["owner"]), f"override owner has no student id: {row['path']}"
        assert row["requirement"].startswith("REQ-"), f"override without a requirement: {row['path']}"
        assert row["adr"].startswith("ADR-"), f"override without an ADR: {row['path']}"
        assert len(row["reason"]) > 20, f"override reason too thin: {row['path']}"


def test_project_owned_files_are_declared():
    owned = {row["path"] for row in OVERRIDES["project_owned"]}
    assert owned == {"README.md", ".gitignore", ".env.example", "requirements.txt", ".github/workflows/ci.yml"}


def test_baseline_policy_document_exists():
    assert (ROOT / "docs" / "architecture" / "baseline-overrides.md").is_file()
    assert (ROOT / "docs" / "architecture" / "adr" / "008-declared-baseline-overrides.md").is_file()


# ---------------------------------------------------------------------------
# ADR-009 — static analysis and the safety-path checks
# ---------------------------------------------------------------------------

def test_static_analysis_gate_is_configured():
    config = (ROOT / "mypy.ini").read_text(encoding="utf-8")
    assert "files = src" in config
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "mypy" in requirements
    assert (ROOT / "docs" / "architecture" / "adr" / "009-static-analysis-gate.md").is_file()


def test_safety_path_checks_are_all_green():
    results = safety_checks.run_all()
    assert [row for row in results if not row["ok"]] == []


def test_permission_model_defaults_to_deny():
    results = safety_checks.check_permissions()
    deny = [row for row in results if row["check"] == "permission/default-deny"][0]
    assert deny["ok"] is True


# ---------------------------------------------------------------------------
# D5 — one consolidated, labelled transcript document
# ---------------------------------------------------------------------------

def test_d5_consolidated_document_exists_and_labels_every_member():
    path = ROOT / "transcripts" / "D5-team-session-transcripts.md"
    assert path.is_file(), "the consolidated D5 document is missing"
    text = path.read_text(encoding="utf-8")
    for name, student_id in (
        ("CUI Haoyu", "60760270"),
        ("ZhuXuan", "60377218"),
        ("Fan Hao", "60835652"),
    ):
        assert name in text and student_id in text, f"D5 does not label {name} ({student_id})"


def test_every_member_has_a_transcript_with_the_required_file_name():
    """Section 5 of the brief: transcripts are named `<student-id>-<name>.md`."""
    files = [p.name for p in (ROOT / "transcripts").glob("*.md")]
    pattern = re.compile(r"^\d{8}-[A-Za-z].*\.md$")
    for student_id in ("60760270", "60835652", "60377218"):
        matches = [name for name in files if name.startswith(student_id + "-")]
        assert matches, f"no <student-id>-<name>.md transcript for {student_id}"
        assert all(pattern.match(name) for name in matches), matches
