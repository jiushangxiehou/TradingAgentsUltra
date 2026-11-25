"""Verify the pinned TradingAgents 0.7.1 baseline against its content manifest.

Why this is not `git status`:
    On this host git's `core.autocrlf` is true, so a checkout writes CRLF and
    reads CRLF back as LF. That made `git add -A` report a *damaged* tree as
    clean (an extra blank line appended to a file went unnoticed). Content
    identity therefore cannot be delegated to git's index.

What is compared:
    Git stores text blobs with LF only. This host's `core.autocrlf=true` makes
    a *git* checkout write CRLF, while the codeload tarball keeps LF. The
    vendored tree is the tarball, so text files are LF on disk (the "CRLF" files
    counted elsewhere are 7 binaries that contain the bytes 0d 0a by chance).

    Hence the fingerprint ignores line-ending form and nothing else:

        sha256(bytes with CRLF -> LF) for every pinned path

    Because git canonicalises CRLF->LF too, this equals the natural git blob
    identity on any host. Flipping CRLF<->LF is not reported (it is not a
    content change and the editable install reads either form); every other
    change -- appended line, altered byte, reordered content -- is.

Two supported layouts
---------------------
vendor layout (the local working copy):
    ROOT/vendor/tradingagents-0.7.x/
    ROOT/vendor/.baseline/blob-sha-working-tree.txt

root layout (the clean dev submission tree, ADR-007):
    ROOT/  is the 0.7.1 baseline itself (ROOT/tradingagents/, ROOT/cli/, ...)
    ROOT/scripts/baseline/blob-sha-working-tree.txt

The layout is detected; no flag is needed.

Declared differences (ADR-008)
------------------------------
A pinned file may differ from upstream only if the difference is DECLARED in
`scripts/baseline-overrides.json`:

    project_owned   the five files the project owns on every layout
                    (README.md, .gitignore, .env.example, requirements.txt,
                    .github/workflows/ci.yml). Reported, never a failure.
    dev_overrides   the files the dev submission tree extends so the runtime
                    actually calls the five enhancements. Each entry names a
                    human owner, the requirement, the commit and the ADR.

The rule is "declare, never silently skip": an altered pinned file that is NOT
declared is still a failure. A declaration that no longer describes a real
difference is stale; `--strict` fails on a stale declaration so the manifest
cannot rot.

Fails on: a missing pinned file; an altered pinned file that is undeclared; in
vendor layout, an unexpected extra file; with --strict, a stale dev-override
declaration (root layout only).
Ignores:  __pycache__, .pytest_cache, tmp*, pytest-of-*, tradingagents-tests-*,
          *.egg-info, and our own BASELINE_MANIFEST.txt / PINNED_COMMIT.txt.

Usage:
    python scripts/verify_baseline.py            # tolerate run droppings
    python scripts/verify_baseline.py --strict   # vendor: any extra fails
                                                 # root: extras are project files
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "tradingagents-0.7.x"
VENDOR_MANIFEST = ROOT / "vendor" / ".baseline" / "blob-sha-working-tree.txt"
ROOT_MANIFEST = ROOT / "scripts" / "baseline" / "blob-sha-working-tree.txt"
OVERRIDES_FILE = ROOT / "scripts" / "baseline-overrides.json"

# Fallback when the declaration file is missing: the five files the project owns
# on every layout. Never an implicit permission to drift -- see ADR-008.
FALLBACK_PROJECT_OWNED = frozenset(
    {
        ".env.example",
        ".gitignore",
        ".github/workflows/ci.yml",
        "README.md",
        "requirements.txt",
    }
)

IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
# Never part of the project's file set: the local environment and git's object
# store would otherwise dominate the "project files" count.
EXCLUDED_SCAN_DIRS = {".git", ".venv"}
IGNORED_PREFIXES = ("tmp", "pytest-of-", "tradingagents-tests-")
IGNORED_NAMES = {"BASELINE_MANIFEST.txt", "PINNED_COMMIT.txt"}
IGNORED_DIR_SUFFIXES = (".egg-info",)


def fingerprint(data: bytes) -> str:
    """SHA-256 of the content with CRLF folded to LF (git's canonical text form)."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def _is_dropping(rel: str) -> bool:
    parts = rel.split("/")
    if any(p in IGNORED_DIRS for p in parts):
        return True
    if parts[0].startswith(IGNORED_PREFIXES):
        return True
    if any(p.endswith(IGNORED_DIR_SUFFIXES) for p in parts):
        return True
    return rel in IGNORED_NAMES


def _layout() -> tuple[Path, Path, bool]:
    """Return (baseline root, manifest path, root_layout)."""
    if VENDOR.is_dir() and VENDOR_MANIFEST.is_file():
        return VENDOR, VENDOR_MANIFEST, False
    if (ROOT / "tradingagents" / "__init__.py").is_file() and ROOT_MANIFEST.is_file():
        return ROOT, ROOT_MANIFEST, True
    raise SystemExit(
        "baseline layout not found: expected either "
        f"{VENDOR}/ with {VENDOR_MANIFEST}, or a root baseline with {ROOT_MANIFEST}"
    )


def load_overrides() -> tuple[dict[str, dict], dict[str, dict]]:
    """Load the declared differences, or fail if the declaration is malformed.

    A malformed declaration is a configuration fault, not a pass: verifying a
    tree against an unreadable permission list would silently accept drift.
    """
    if not OVERRIDES_FILE.is_file():
        project = {p: {"path": p, "reason": "fallback"} for p in FALLBACK_PROJECT_OWNED}
        return project, {}
    try:
        data = json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"baseline-overrides.json is unreadable: {exc}") from exc

    project_rows = data.get("project_owned", [])
    dev_rows = data.get("dev_overrides", [])
    if not isinstance(project_rows, list) or not isinstance(dev_rows, list):
        raise SystemExit("baseline-overrides.json: project_owned/dev_overrides must be lists")

    project: dict[str, dict] = {}
    for row in project_rows:
        if not isinstance(row, dict) or not row.get("path") or not row.get("reason"):
            raise SystemExit(f"baseline-overrides.json: bad project_owned row: {row!r}")
        project[row["path"]] = row

    dev: dict[str, dict] = {}
    for row in dev_rows:
        missing = [key for key in ("path", "owner", "requirement", "reason", "adr") if not row.get(key)]
        if missing:
            raise SystemExit(
                f"baseline-overrides.json: dev_overrides row {row.get('path')!r} "
                f"is missing {', '.join(missing)}"
            )
        dev[row["path"]] = row

    both = set(project) & set(dev)
    if both:
        raise SystemExit(f"baseline-overrides.json: declared twice: {sorted(both)}")
    return project, dev


def main(strict: bool = False) -> int:
    base, manifest, root_layout = _layout()
    project_owned, dev_declared = load_overrides()

    rows = [
        line.split("\t")
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line
    ]
    pinned = {rel: sha for sha, rel in rows}

    missing: list[str] = []
    undeclared: list[str] = []
    declared: list[tuple[str, str]] = []
    stale: list[str] = []
    project_owned_seen: list[str] = []
    dev_seen: list[str] = []

    for rel, sha in pinned.items():
        path = base / rel
        if not path.is_file():
            missing.append(rel)
            continue
        changed = fingerprint(path.read_bytes()) != sha

        if root_layout and rel in project_owned:
            project_owned_seen.append(rel)
            declared.append(("project-owned", rel))
            continue
        if rel in dev_declared:
            if changed:
                dev_seen.append(rel)
                declared.append(("dev-override", rel))
            else:
                stale.append(rel)
            continue
        if changed:
            undeclared.append(rel)

    # A declaration for a path that is not in the pinned set is a typo, not a grant.
    unknown = sorted((set(dev_declared) | set(project_owned)) - set(pinned))

    tracked = set(pinned)
    present = {
        p.relative_to(base).as_posix()
        for p in base.rglob("*")
        if p.is_file() and not (set(p.relative_to(base).parts) & EXCLUDED_SCAN_DIRS)
    }
    extras = present - tracked - IGNORED_NAMES
    droppings = sorted(p for p in extras if not _is_dropping(p))
    ignored = sorted(p for p in extras if _is_dropping(p))

    print(f"layout       : {'root' if root_layout else 'vendor'}")
    print(f"pinned files : {len(tracked)}")
    print(f"project-owned: {len(project_owned_seen)} declared")
    print(f"dev overrides: {len(dev_seen)} declared, {len(dev_declared) - len(dev_seen)} unused")
    print(f"missing      : {len(missing)}")
    print(f"undeclared   : {len(undeclared)}")
    print(f"stale        : {len(stale)}")
    if root_layout:
        print(f"project files: {len(droppings)} (allowed additions)")
    else:
        print(f"unexpected   : {len(droppings)}")
    print(f"run output   : {len(ignored)} files (ignored)")

    for label, items in (
        ("MISSING", missing),
        ("UNDECLARED", undeclared),
        ("STALE", stale),
        ("UNKNOWN", unknown),
        ("UNEXPECTED", droppings if not root_layout else []),
    ):
        for item in items[:20]:
            print(f"  {label}: {item}")

    if dev_seen and strict is False:
        print("declared dev overrides (owner -> file):")
        for rel in dev_seen[:24]:
            row = dev_declared[rel]
            print(f"  - {row.get('owner')} [{row.get('requirement')}]: {rel}")

    ok = not (missing or undeclared or unknown)
    if strict and not root_layout and droppings:
        ok = False
        print("--strict: files beyond the pinned set are a failure")
    if strict and stale:
        ok = False
        print("--strict: a declared dev override no longer differs from the pinned file")
    print(
        "baseline-verify:",
        "PASS (pinned baseline matches; declared differences only)" if ok else "FAIL",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(strict="--strict" in sys.argv))
