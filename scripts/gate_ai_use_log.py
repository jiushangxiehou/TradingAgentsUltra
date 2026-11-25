"""AI-use-log gate (D7 gate 6).

A change to code or prompts must update `docs/ai-use-log.yaml` in the same
change set, or the merge is blocked.

The old workflow compared `HEAD^..HEAD`, so a multi-commit push could slip a
code change past it. This gate compares the whole range (`base..head`), and it
resolves the base from the CI event instead of assuming one parent:

    --base <rev>            explicit (used by the tests and by hand)
    GITHUB_EVENT_BEFORE     push event: the previous branch tip
    GITHUB_BASE_REF         pull request: the target branch (`origin/<ref>`)
    HEAD~1                  last-resort local default

Usage:
    python scripts/gate_ai_use_log.py [--base REV] [--head REV] [--list]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = "docs/ai-use-log.yaml"

# Paths whose change is "code or prompts" for the purpose of this gate.
CODE_PREFIXES = (
    "src/",
    "tradingagents/",
    "cli/",
    "scripts/",
    "test/",
    "tests/",
    "prompts/",
)

ZERO_SHA = "0" * 40


def classify(changed: list[str]) -> tuple[list[str], list[str]]:
    """Split a change set into (code/prompt files, ai-use-log files)."""
    code = [path for path in changed if path.startswith(CODE_PREFIXES)]
    log = [path for path in changed if path == LOG_PATH]
    return code, log


def evaluate(changed: list[str]) -> tuple[bool, str, list[str], list[str]]:
    """Return (ok, message, code_files, log_files)."""
    code, log = classify(changed)
    if not code:
        return True, "no code or prompt change in the diff", code, log
    if not log:
        return (
            False,
            f"{len(code)} code/prompt file(s) changed without updating {LOG_PATH}",
            code,
            log,
        )
    return True, f"{len(code)} code/prompt file(s) changed and {LOG_PATH} updated", code, log


def _rev_exists(rev: str) -> bool:
    try:
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def resolve_base(explicit: str | None = None) -> str:
    """Pick the base revision of the change set, in the CI's own terms."""
    if explicit:
        return explicit
    before = os.environ.get("GITHUB_EVENT_BEFORE", "").strip()
    if before and before != ZERO_SHA and _rev_exists(before):
        return before
    base_ref = os.environ.get("GITHUB_BASE_REF", "").strip()
    if base_ref:
        for candidate in (f"origin/{base_ref}", base_ref):
            if _rev_exists(candidate):
                return candidate
    return "HEAD~1"


def changed_files(base: str, head: str = "HEAD", worktree: bool = False) -> list[str]:
    """Paths changed between base and head (or the working tree with --worktree).

    `--worktree` exists so the gate can be run before a commit: it compares the
    base revision with the working tree and adds the untracked files. CI uses
    the revision range.
    """
    # With --worktree, omit the head so git compares base with the working tree.
    args = ["git", "diff", "--name-only", base] if worktree else ["git", "diff", "--name-only", base, head]
    proc = subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True)
    paths = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if worktree:
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        paths += [line.strip() for line in untracked.stdout.splitlines() if line.strip()]
    return sorted(set(paths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=None, help="base revision (default: CI event)")
    parser.add_argument("--head", default="HEAD", help="head revision (default: HEAD)")
    parser.add_argument("--list", action="store_true", help="print the changed files")
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="compare the base revision with the working tree (pre-commit use)",
    )
    args = parser.parse_args(argv)

    base = resolve_base(args.base)
    if not _rev_exists(base):
        print(f"ai-use-log: FAIL (base revision not found: {base})", file=sys.stderr)
        return 2

    changed = changed_files(base, args.head, worktree=args.worktree)
    ok, message, code, log = evaluate(changed)
    print(f"range      : {base}..{args.head}")
    print(f"changed    : {len(changed)} file(s)")
    if args.list:
        for path in changed:
            print(f"  {path}")
    print(f"code/prompt: {len(code)} file(s)")
    print(f"ai-use-log : {len(log)} file(s)")
    print("ai-use-log:", "PASS" if ok else "FAIL", f"({message})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
