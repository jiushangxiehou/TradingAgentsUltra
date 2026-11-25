"""``python -m src.integration`` -- the guarded CLI.

Kept as a thin shim so the entry point is reachable without a console script:

    python -m src.integration --help
    python -m src.integration NVDA --guardrail-position-fraction 0.05 \\
                                 --guardrail-short-amount 0
"""

from __future__ import annotations

import sys

from src.integration.entry import run_guarded_cli

if __name__ == "__main__":
    raise SystemExit(run_guarded_cli(sys.argv[1:]))
