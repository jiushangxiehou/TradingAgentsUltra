"""Test-approval gate (D7 gate 1).

A test that guards a change must be approved by a human *before* the
implementation it guards is merged. The approval record is a manifest,
`docs/test-approval.yaml`: a machine-readable list of approved test files with
the approver, the date, the rationale and the requirement.

The gate reads the manifest **at the base revision**, because an entry that only
arrives with the change did not exist when implementation started. If the
manifest does not exist at the base (the commit that introduces it, or a
repository that has not adopted it yet), the gate falls back to the manifest at
head, prints BOOTSTRAP, and still requires a named approver and a date; the
compensating control is CODEOWNERS review on `docs/test-approval.yaml`.

Usage:
    python scripts/gate_test_approval.py [--base REV] [--head REV] [--list]
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `python scripts/...` puts scripts/ on sys.path
    sys.path.insert(0, str(ROOT))

from scripts.gate_ai_use_log import resolve_base  # noqa: E402

MANIFEST_PATH = "docs/test-approval.yaml"
TEST_PREFIXES = ("test/", "tests/")
BOOTSTRAP = "BOOTSTRAP"


def is_test_path(path: str) -> bool:
    return path.startswith(TEST_PREFIXES) and path.endswith(".py")


def parse_manifest(text: str) -> list[dict]:
    """Parse and validate the approval manifest; a malformed manifest is a fault."""
    data = yaml.safe_load(text) or {}
    approvals = data.get("approvals")
    if not isinstance(approvals, list):
        raise ValueError("manifest has no 'approvals' list")
    for index, entry in enumerate(approvals, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"approval #{index} is not a mapping")
        missing = [key for key in ("id", "tests", "approved_by", "approved_at", "rationale") if not entry.get(key)]
        if missing:
            raise ValueError(f"approval #{index} ({entry.get('id', '?')}) is missing {', '.join(missing)}")
        if not isinstance(entry["tests"], list) or not all(isinstance(p, str) and p for p in entry["tests"]):
            raise ValueError(f"approval {entry['id']}: 'tests' must be a non-empty list of paths/globs")
    return approvals


def approval_for(path: str, approvals: list[dict]) -> dict | None:
    for entry in approvals:
        for pattern in entry["tests"]:
            if fnmatch.fnmatchcase(path, pattern):
                return entry
    return None


def evaluate(changed: list[str], approvals: list[dict]) -> dict:
    """Return the gate verdict for a change set and an approval list."""
    tests = sorted({path for path in changed if is_test_path(path)})
    unapproved = [path for path in tests if approval_for(path, approvals) is None]
    return {
        "ok": not unapproved,
        "tests": tests,
        "unapproved": unapproved,
        "approvals": len(approvals),
    }


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def changed_files(base: str, head: str = "HEAD", worktree: bool = False) -> list[str]:
    """Paths changed between base and head (or the working tree with --worktree)."""
    # With --worktree, omit the head so git compares base with the working tree.
    proc = _git("diff", "--name-only", base) if worktree else _git("diff", "--name-only", base, head)
    if proc.returncode != 0:
        raise SystemExit(f"git diff failed: {proc.stderr.strip()}")
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if worktree:
        untracked = _git("ls-files", "--others", "--exclude-standard")
        paths += [line.strip() for line in untracked.stdout.splitlines() if line.strip()]
    return sorted(set(paths))


def manifest_at(rev: str) -> tuple[str, list[dict]] | None:
    proc = _git("show", f"{rev}:{MANIFEST_PATH}")
    if proc.returncode != 0:
        return None
    return BOOTSTRAP, parse_manifest(proc.stdout)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--list", action="store_true")
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="compare the base revision with the working tree (pre-commit use)",
    )
    args = parser.parse_args(argv)

    base = resolve_base(args.base)
    changed = changed_files(base, args.head, worktree=args.worktree)

    loaded = manifest_at(base)
    source = "base"
    if loaded is None:
        manifest_file = ROOT / MANIFEST_PATH
        if not manifest_file.is_file():
            print(f"test-approval: FAIL (no {MANIFEST_PATH} at {base} or head)")
            return 1
        approvals = parse_manifest(manifest_file.read_text(encoding="utf-8"))
        source = BOOTSTRAP
    else:
        _, approvals = loaded

    verdict = evaluate(changed, approvals)
    print(f"range      : {base}..{args.head}")
    print(f"manifest   : {source} ({verdict['approvals']} approvals)")
    print(f"test files : {len(verdict['tests'])}")
    if args.list:
        for path in verdict["tests"]:
            entry = approval_for(path, approvals)
            print(f"  {path} -> {entry['id'] if entry else 'UNAPPROVED'}")
    for path in verdict["unapproved"]:
        print(f"  UNAPPROVED: {path}")
    print(
        "test-approval:",
        "PASS" if verdict["ok"] else "FAIL",
        "" if verdict["ok"] else "(every changed test needs an approval in the base manifest)",
    )
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
