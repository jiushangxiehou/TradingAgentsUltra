"""Semantic-evaluation gate (D7 gate 4).

D7 asks for a **fixed evaluation set replayed on prompt/model changes**, with a
threshold that blocks the merge. This gate implements the deterministic half:

    prompt constraint retention   every standing constraint declared in
                                  docs/eval/fixed-set.json must still be present
                                  in its prompt file
    decision replay               the fixed labelled decision set is replayed
                                  through the frozen guardrail; the verdict and
                                  the audit trigger must match, and the number
                                  of escapes must be zero
    model baseline                the configured provider/models must equal the
                                  declared baseline; a model change without
                                  updating the set is blocked here

The live half -- an actual model answer measured for faithfulness/relevancy
>= 0.6 -- is test/live/test_live_prose.py; it needs an API key and is not part
of CI. This gate says exactly what it measures and does not claim model-output
quality.

Usage:
    python scripts/gate_semantic_eval.py [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXED_SET = ROOT / "docs" / "eval" / "fixed-set.json"


def load_fixed_set(path: Path = FIXED_SET) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prompt_retention(entries: list[dict]) -> list[dict]:
    """Per file: how many declared constraints are still present."""
    rows = []
    for entry in entries:
        path = ROOT / entry["file"]
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        constraints = entry["constraints"]
        present = [c for c in constraints if c.lower() in text.lower()]
        ratio = len(present) / len(constraints) if constraints else 1.0
        rows.append(
            {
                "file": entry["file"],
                "present": len(present),
                "total": len(constraints),
                "ratio": round(ratio, 4),
                "missing": [c for c in constraints if c not in present],
            }
        )
    return rows


def replay_decisions(cases: list[dict]) -> dict:
    """Replay the labelled decision set through the frozen guardrail."""
    from src.guardrail import Decision, evaluate_decision

    rows = []
    escapes = 0
    for case in cases:
        decision = Decision(
            rating=case["rating"],
            size_pct=case["size_pct"],
            short_amount=case["short_amount"],
            available_cash=case["available_cash"],
            instrument_id=case.get("instrument_id", "SEM-EVAL"),
        )
        result = evaluate_decision(decision)
        trigger = result.audit.trigger.value if result.audit is not None else None
        matched = result.passed == case["expect_passed"] and trigger == case["expect_trigger"]
        if case["expect_passed"] is False and result.passed is True:
            escapes += 1
        rows.append(
            {
                "id": case["id"],
                "expected": [case["expect_passed"], case["expect_trigger"]],
                "actual": [result.passed, trigger],
                "matched": matched,
            }
        )
    total = len(rows)
    matched_count = sum(row["matched"] for row in rows)
    return {
        "rows": rows,
        "accuracy": round(matched_count / total, 4) if total else 1.0,
        "escapes": escapes,
        "total": total,
    }


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def check_model_baseline(spec: dict) -> dict:
    values = parse_env_file(ROOT / spec["file"])
    mismatches = {
        key: {"expected": expected, "actual": values.get(key)}
        for key, expected in spec["keys"].items()
        if values.get(key) != expected
    }
    return {"file": spec["file"], "ok": not mismatches, "mismatches": mismatches}


def run(path: Path = FIXED_SET) -> dict:
    fixed = load_fixed_set(path)
    prompts = prompt_retention(fixed["prompt_constraints"])
    decisions = replay_decisions(fixed["decision_cases"])
    model = check_model_baseline(fixed["model_baseline"])
    thresholds = fixed["thresholds"]

    worst_prompt = min((row["ratio"] for row in prompts), default=1.0)
    ok = (
        worst_prompt >= thresholds["prompt_constraint_retention"]
        and decisions["accuracy"] >= thresholds["decision_accuracy"]
        and decisions["escapes"] <= thresholds["safety_escapes"]
        and model["ok"]
    )
    return {
        "ok": ok,
        "thresholds": thresholds,
        "prompts": prompts,
        "prompt_worst": worst_prompt,
        "decisions": decisions,
        "model": model,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)

    report = run()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        threshold = report["thresholds"]["prompt_constraint_retention"]
        print(f"prompt-constraint retention (threshold {threshold:.2f}):")
        for row in report["prompts"]:
            print(f"  {row['ratio']:.2f}  {row['file']}  ({row['present']}/{row['total']})")
            for missing in row["missing"]:
                print(f"        missing: {missing}")
        print(
            "decision replay (threshold {:.2f}, escapes <= {}):".format(
                report["thresholds"]["decision_accuracy"], report["thresholds"]["safety_escapes"]
            )
        )
        for row in report["decisions"]["rows"]:
            mark = "ok  " if row["matched"] else "FAIL"
            print(f"  [{mark}] {row['id']}: expected={row['expected']} actual={row['actual']}")
        print(
            f"  accuracy: {report['decisions']['accuracy']:.2f}"
            f"  escapes: {report['decisions']['escapes']}"
        )
        print("model baseline:", "ok" if report["model"]["ok"] else "CHANGED")
        for key, delta in report["model"]["mismatches"].items():
            print(f"  {key}: expected {delta['expected']!r}, actual {delta['actual']!r}")
    print(
        "semantic-eval:",
        "PASS" if report["ok"] else "FAIL",
        "(deterministic replay; live faithfulness/relevancy lives in test/live)",
    )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
