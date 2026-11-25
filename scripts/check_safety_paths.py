"""Run the safety-path checks (D7 gate 2, ADR-009).

Usage:
    python scripts/check_safety_paths.py [--quiet]

Exit 0 and print "check-safety-paths: PASS" when every contract, API-surface,
permission and structure check passes; exit 1 with the failing checks otherwise.
The same functions are exercised by `test/offline/test_structural_fitness.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Running `python scripts/<file>.py` puts scripts/ on sys.path, not the repo
# root; the project modules and the scripts package live at the root.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.safety_checks import run_all  # noqa: E402


def main(quiet: bool = False) -> int:
    results = run_all()
    failures = [row for row in results if not row["ok"]]
    for row in results:
        if quiet and row["ok"]:
            continue
        mark = "ok  " if row["ok"] else "FAIL"
        print(f"[{mark}] {row['check']}: {row['detail']}")
    print(f"checks: {len(results)} total, {len(failures)} failed")
    print("check-safety-paths:", "PASS (contract, security, API surface, permission)" if not failures else "FAIL")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main(quiet="--quiet" in sys.argv))
