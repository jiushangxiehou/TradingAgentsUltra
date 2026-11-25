"""Deterministic safety-path checks (D7 gate 2, ADR-009).

The four checks the project brief asks for on safety-relevant paths, expressed
as pure functions so both CI (`scripts/check_safety_paths.py`) and the offline
test suite (`test/offline/test_structural_fitness.py`) run exactly the same
code:

    contract     the pure modules import only their allowlist and reference
                 their ADR; no clock, UUID, network or process access
    api surface  the public names of the frozen modules match
                 docs/architecture/api-surface.json
    permission   .opencode/permissions.jsonc still defaults to deny and covers
                 the safety-critical files
    structure    every architectural element maps to existing modules, and the
                 structural-constraints document names them

Nothing here reads the network, the clock or a model.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ELEMENT_MAP = ROOT / "scripts" / "element-map.json"
API_SURFACE = ROOT / "docs" / "architecture" / "api-surface.json"
PERMISSIONS = ROOT / ".opencode" / "permissions.jsonc"
STRUCTURAL_DOC = ROOT / "docs" / "code-governance" / "structural-constraints.md"

# Calls that would make a "pure, deterministic" module impure.
FORBIDDEN_CALL_SUFFIXES = ("now", "today", "utcnow", "time", "uuid4", "uuid1", "randint", "random")
FORBIDDEN_MODULES = {"time", "uuid", "random", "socket", "subprocess", "urllib", "requests", "http", "os"}

if str(ROOT) not in sys.path:  # scripts/run from anywhere
    sys.path.insert(0, str(ROOT))


def _check(name: str, ok: bool, detail: str) -> dict[str, object]:
    return {"check": name, "ok": bool(ok), "detail": detail}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def imports_of(path: Path) -> list[str]:
    """Top-level module names imported by a source file (relative imports skipped)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            if node.module:
                names.add(node.module.split(".")[0])
    return sorted(names)


def forbidden_calls(path: Path) -> list[str]:
    """Attribute calls that would make a pure module non-deterministic."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in FORBIDDEN_CALL_SUFFIXES:
            found.append(f"{path.name}: .{node.func.attr}()")
    return found


def check_contract(element_map: dict) -> list[dict[str, object]]:
    results = []
    allow = element_map.get("pure_module_import_allowlist", {})
    pure = element_map.get("pure_modules", [])
    for rel in pure:
        path = ROOT / rel
        if not path.is_file():
            results.append(_check("contract/imports", False, f"{rel} is missing"))
            continue
        allowed = set(allow.get(rel, []))
        used = set(imports_of(path))
        extra = sorted(used - allowed)
        missing = sorted(allowed - used)
        results.append(
            _check(
                "contract/imports",
                not extra,
                f"{rel}: imports {sorted(used)}; not allowlisted: {extra or 'none'}"
                + (f"; declared but unused: {missing}" if missing else ""),
            )
        )
        bad_calls = forbidden_calls(path)
        results.append(
            _check(
                "contract/purity",
                not bad_calls,
                f"{rel}: clock/uuid/random calls: {bad_calls or 'none'}",
            )
        )
        text = path.read_text(encoding="utf-8")
        has_adr = re.search(r"ADR-00\d", text) is not None
        results.append(
            _check(
                "contract/adr-reference",
                has_adr,
                f"{rel}: ADR reference present: {has_adr}",
            )
        )
    return results


def _public_names(module_name: str) -> list[str]:
    module = importlib.import_module(module_name)
    names = []
    for name, obj in vars(module).items():
        if name.startswith("_") or isinstance(obj, types.ModuleType):
            continue
        if getattr(obj, "__module__", None) == module_name or name.isupper():
            names.append(name)
    return sorted(names)


def check_api_surface(surface: dict) -> list[dict[str, object]]:
    results = []
    for module_name, expected in surface.get("modules", {}).items():
        try:
            actual = _public_names(module_name)
        except Exception as exc:  # noqa: BLE001 - an unimportable module is a failure
            results.append(_check("api-surface/import", False, f"{module_name}: {type(exc).__name__}"))
            continue
        added = sorted(set(actual) - set(expected))
        removed = sorted(set(expected) - set(actual))
        results.append(
            _check(
                "api-surface",
                not added and not removed,
                f"{module_name}: added={added or 'none'}, removed={removed or 'none'}",
            )
        )
    return results


def _strip_jsonc(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|\s)//[^\n]*", r"\1", text)
    return text


def check_permissions(path: Path = PERMISSIONS) -> list[dict[str, object]]:
    try:
        data = json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        return [_check("permission/parse", False, f"{path.name}: {exc}")]

    results = []
    default = data.get("default", {})
    deny = default.get("read") is False and default.get("write") is False
    results.append(_check("permission/default-deny", deny, f"default={default}"))

    roles = data.get("roles", {})
    bad_paths = [
        f"{role}:{item}"
        for role, spec in roles.items()
        for key in ("read", "write", "exec")
        for item in spec.get(key, [])
        if not isinstance(item, str) or not item.strip()
    ]
    results.append(
        _check("permission/paths", not bad_paths and bool(roles), f"roles={len(roles)}; bad paths={bad_paths or 'none'}")
    )

    rules = data.get("guard_rules", [])
    covers = any(
        rule.get("effect") in {"deny", "require-architecture-decision"}
        and any("guardrail" in p for p in rule.get("paths", []))
        for rule in rules
    )
    results.append(_check("permission/safety-coverage", covers, f"guard rules={len(rules)}"))
    return results


def check_structure(element_map: dict, doc: Path = STRUCTURAL_DOC) -> list[dict[str, object]]:
    results = []
    doc_text = doc.read_text(encoding="utf-8") if doc.is_file() else ""
    for element in element_map.get("elements", []):
        name = element.get("element", "?")
        modules = element.get("modules", [])
        missing = [rel for rel in modules if not (ROOT / rel).is_file()]
        facade = element.get("facade")
        missing_facade = bool(facade) and not (ROOT / facade).is_file()
        results.append(
            _check(
                "structure/modules",
                not missing and not missing_facade,
                f"{name}: missing={missing or 'none'}, facade={facade or 'none'} missing={missing_facade}",
            )
        )
        undocumented = [rel for rel in modules if rel not in doc_text]
        results.append(
            _check(
                "structure/doc",
                not undocumented,
                f"{name}: undocumented modules={undocumented or 'none'}",
            )
        )
    return results


def run_all() -> list[dict[str, object]]:
    element_map = load_json(ELEMENT_MAP)
    surface = load_json(API_SURFACE)
    results: list[dict[str, object]] = []
    results += check_contract(element_map)
    results += check_api_surface(surface)
    results += check_permissions()
    results += check_structure(element_map)
    return results
