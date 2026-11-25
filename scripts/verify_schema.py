"""Schema gate: validate docs/req/requirements.yaml against req-schema.json.

Mirrors the CI `schema-gate` job in .github/workflows/ci.yml step for step:
the same two files, the same UTF-8 reads, `yaml.safe_load`, then
`jsonschema.validate(data, schema)` against the draft/2020-12 schema the file
declares. Local and CI verdicts therefore cannot diverge.

Read-only: it never writes to docs/.

Usage:
    python scripts/verify_schema.py
Exit 0 and prints "schema-gate: PASS", or exit 1 with the exact validation error.
"""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "docs" / "req" / "req-schema.json"
REGISTRY = ROOT / "docs" / "req" / "requirements.yaml"


def main() -> int:
    try:
        with open(SCHEMA, encoding="utf-8") as handle:
            schema = json.load(handle)
        with open(REGISTRY, encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        print("schema-gate: FAIL")
        print(f"  message : {exc.message}")
        print(f"  path    : {list(exc.absolute_path)}")
        print(f"  schema  : {list(exc.absolute_schema_path)}")
        print(f"  validator: {exc.validator!r}")
        if exc.instance is not None:
            print(f"  instance: {exc.instance!r}")
        return 1
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print("schema-gate: FAIL (could not read or parse input)")
        print(f"  {type(exc).__name__}: {exc}")
        return 1

    count = len(data.get("requirements", [])) if isinstance(data, dict) else 0
    print(f"schema-gate: PASS ({count} requirements validated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
