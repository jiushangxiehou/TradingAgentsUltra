"""Compare two JUnit XML files by test ID and verdict.

Usage:
    python scripts/diff_junit.py <baseline.xml> <current.xml> [--allow "id1,id2"]

Exit 0 when the current run matches the baseline, or when every difference is
confined to IDs listed in --allow and the verdict there is the same failure
reason as in the baseline. Any other difference is a regression: exit 1.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def outcomes(path: Path) -> dict[str, tuple[str, str]]:
    root = ET.parse(path).getroot()
    result: dict[str, tuple[str, str]] = {}
    for case in root.iter("testcase"):
        name = f"{case.get('classname')}::{case.get('name')}"
        verdict, reason = "passed", ""
        for tag in ("failure", "error", "skipped"):
            node = case.find(tag)
            if node is not None:
                verdict = tag
                message = node.get("message") or ""
                text = (node.text or "").strip().splitlines()
                reason = f"{message} | {text[-1] if text else ''}".strip(" |")
                break
        result[name] = (verdict, reason)
    return result


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    allowed: set[str] = set()
    if "--allow" in argv:
        allowed = {item.strip() for item in argv[argv.index("--allow") + 1].split(",") if item.strip()}

    base = outcomes(Path(argv[1]))
    cur = outcomes(Path(argv[2]))

    only_base = sorted(set(base) - set(cur))
    only_cur = sorted(set(cur) - set(base))
    changed = sorted(k for k in set(base) & set(cur) if base[k] != cur[k])

    print(f"baseline tests : {len(base)}")
    print(f"current tests  : {len(cur)}")
    print(f"ID set identical: {not only_base and not only_cur}")
    print(f"verdicts changed: {len(changed)}")

    regressions: list[str] = []
    for key in only_base:
        regressions.append(f"DROPPED   {key}")
    for key in only_cur:
        regressions.append(f"NEW       {key}")
    for key in changed:
        was, why_now = base[key], cur[key]
        tolerated = key in allowed and was[0] == why_now[0] and was[1] == why_now[1]
        line = f"{'EXPECTED' if tolerated else 'REGRESSED'} {key}: {was[0]} -> {why_now[0]}"
        if not tolerated:
            regressions.append(line)
        else:
            print(f"  {line} (allowed, same reason)")
    for key in sorted(allowed):
        if key not in cur:
            regressions.append(f"ALLOWED-MISSING {key}")

    for line in regressions:
        print(f"  {line}")
    ok = not regressions
    print("junit-diff:", "PASS (no regressions)" if ok else "FAIL (regressions above)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
