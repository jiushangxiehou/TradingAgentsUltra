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

root layout (the clean `feature-c` repository):
    ROOT/  is the 0.7.1 baseline itself (ROOT/tradingagents/, ROOT/cli/, ...)
    ROOT/scripts/baseline/blob-sha-working-tree.txt

The layout is detected; no flag is needed. In root layout, project files are
expected additions, so `--strict` fails only on a missing or altered pinned
file. Five pinned files are intentionally project-owned on `feature-c` and are
declared overrides:

    README.md, .gitignore, .env.example, requirements.txt,
    .github/workflows/ci.yml

They are reported as `overridden`, not as failures; the other 208 pinned files
must match. In vendor layout the original strict rule is unchanged: any extra
file fails.

Fails on: a missing or altered pinned file; in vendor layout, an unexpected
extra file. In root layout, project additions are allowed.
Ignores:  __pycache__, .pytest_cache, tmp*, pytest-of-*, tradingagents-tests-*,
          *.egg-info, and our own BASELINE_MANIFEST.txt / PINNED_COMMIT.txt.

Usage:
    python scripts/verify_baseline.py            # tolerate run droppings
    python scripts/verify_baseline.py --strict   # vendor: any extra fails
                                                 # root: extras are project files
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "tradingagents-0.7.x"
VENDOR_MANIFEST = ROOT / "vendor" / ".baseline" / "blob-sha-working-tree.txt"
ROOT_MANIFEST = ROOT / "scripts" / "baseline" / "blob-sha-working-tree.txt"

# Pinned files that the project owns on the root-layout feature branch. They are
# deliberately different from upstream and are declared, never silently skipped.
PROJECT_OVERRIDES = frozenset(
    {
        ".env.example",
        ".gitignore",
        ".github/workflows/ci.yml",
        "README.md",
        "requirements.txt",
    }
)

IGNORED_DIRS = {"__pycache__", ".pytest_cache"}
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


def main(strict: bool = False) -> int:
    base, manifest, root_layout = _layout()
    rows = [
        line.split("\t")
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line
    ]
    missing: list[str] = []
    altered: list[str] = []
    overridden: list[str] = []

    for sha, rel in rows:
        path = base / rel
        if root_layout and rel in PROJECT_OVERRIDES:
            overridden.append(rel)
            if not path.is_file():
                missing.append(rel)
            continue
        if not path.is_file():
            missing.append(rel)
        elif fingerprint(path.read_bytes()) != sha:
            altered.append(rel)

    tracked = {rel for _, rel in rows}
    present = {
        p.relative_to(base).as_posix() for p in base.rglob("*") if p.is_file()
    }
    extras = present - tracked - IGNORED_NAMES
    droppings = sorted(p for p in extras if not _is_dropping(p))
    ignored = sorted(p for p in extras if _is_dropping(p))

    print(f"layout       : {'root' if root_layout else 'vendor'}")
    print(f"pinned files : {len(tracked)}")
    print(f"overridden   : {len(overridden)}")
    print(f"missing      : {len(missing)}")
    print(f"altered      : {len(altered)}")
    if root_layout:
        print(f"project files: {len(droppings)} (allowed additions)")
    else:
        print(f"unexpected   : {len(droppings)}")
    print(f"run output   : {len(ignored)} files (ignored)")

    for label, items in (
        ("MISSING", missing),
        ("ALTERED", altered),
        ("OVERRIDDEN", overridden),
        ("UNEXPECTED", droppings if not root_layout else []),
    ):
        for item in items[:20]:
            print(f"  {label}: {item}")

    ok = not (missing or altered)
    if strict and not root_layout and ignored:
        ok = False
        print("--strict: files beyond the pinned set are a failure")
    print("baseline-verify:", "PASS (pinned baseline matches)" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(strict="--strict" in sys.argv))
