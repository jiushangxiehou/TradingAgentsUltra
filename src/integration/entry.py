"""CLI entry point: run the upstream CLI with the guardrail engaged.

ADR-006 / REQ-HARD-GUARDRAIL

The integration does not fork the CLI. It wraps ``cli.main`` and patches the
class ``cli.run`` imported, so the SAME command line, the SAME interactive
prompts and the SAME report flow run -- with one difference: the graph they get
is ``GuardedTradingAgentsGraph``.

Two surfaces are added, and both are stripped from ``argv`` BEFORE ``typer``
sees them (typer rejects unknown top-level options, and the details of the
guardrail are the integration's, not the upstream CLI's):

    --guardrail-position-fraction FLOAT   fraction of portfolio value, 0.05 = 5%
    --guardrail-short-amount FLOAT        absolute notional, same currency as cash

Both are required for a decision to pass the gate. Supplying neither is not an
error here: it produces ``intent=None``, the graph treats every required field
as missing, and the guardrail fails closed to Hold. That is the policy --
absent intent is a rejection, not a crash.

Because typer never sees those two flags, its own ``--help`` cannot mention
them. When ``--help``/``-h`` is present, one line naming them is printed to
STDERR before delegating, leaving the help text on stdout untouched.
"""

from __future__ import annotations

import contextlib
import sys
from argparse import ArgumentParser

from src.integration.decision_adapter import ExecutionIntent
from src.integration.governed_graph import EXECUTION_INTENT

POSITION_FLAG = "--guardrail-position-fraction"
SHORT_FLAG = "--guardrail-short-amount"
HELP_FLAGS = ("--help", "-h")

# Printed to STDERR, so ``--help`` output on stdout stays byte-identical to the
# upstream CLI's (a script that diffs or greps the help text keeps working).
# stderr is where extra, integration-owned information belongs.
GUARDED_OPTIONS_LINE = (
    "guarded options: --guardrail-position-fraction FLOAT (0.05 = 5%), "
    "--guardrail-short-amount FLOAT"
)


def build_parser() -> ArgumentParser:
    """The integration's own flags. ``add_help=False``: upstream owns ``--help``."""
    parser = ArgumentParser(add_help=False)
    parser.add_argument(POSITION_FLAG, dest="position_fraction")
    parser.add_argument(SHORT_FLAG, dest="short_amount")
    return parser


def strip_guardrail_flags(argv: list[str]) -> tuple[ExecutionIntent | None, list[str]]:
    """Split the integration's flags out of ``argv``.

    Raises ``SystemExit`` (argparse's own, code 2) when a flag is present
    without a value, and ``ValueError`` when a value is not a float -- the
    caller turns both into an exit code and never reaches the CLI.
    """
    parser = build_parser()
    known, remaining = parser.parse_known_args(argv)
    if known.position_fraction is None and known.short_amount is None:
        return None, remaining
    intent = ExecutionIntent(
        size_pct=_as_float(known.position_fraction) if known.position_fraction is not None else None,
        short_amount=_as_float(known.short_amount) if known.short_amount is not None else None,
    )
    return intent, remaining


def _as_float(text: str) -> float:
    try:
        return float(text)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"not a number: {text!r}") from exc


@contextlib.contextmanager
def install(module, graph_cls):
    """Patch ``module.TradingAgentsGraph`` for the duration of the block.

    The CLI resolves the class at call time (``cli/run.py`` imports it at module
    level and constructs it inside ``run_analysis``), so patching the name on
    the module is enough to give every call the guarded graph. The original is
    restored in ``finally`` -- including when the body raises -- so an
    exception in one run cannot leave the process guarded by accident.
    """
    original = module.TradingAgentsGraph
    module.TradingAgentsGraph = graph_cls
    try:
        yield graph_cls
    finally:
        module.TradingAgentsGraph = original


def run_guarded_cli(argv: list[str] | None = None) -> int:
    """Run the upstream CLI, guarded. Returns the process exit code."""
    args = list(sys.argv[1:]) if argv is None else list(argv)
    try:
        intent, remaining = strip_guardrail_flags(args)
    except SystemExit as exc:  # argparse already parsed one of OUR flags badly
        return int(exc.code or 2)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    token = EXECUTION_INTENT.set(intent)
    try:
        if any(flag in remaining for flag in HELP_FLAGS):
            # The user asked for help: tell them the two options upstream's help
            # cannot list. Before delegating, so it is visible even if the CLI
            # prints its help and exits.
            print(GUARDED_OPTIONS_LINE, file=sys.stderr)

        # Imported lazily: importing the CLI builds a typer app and touches the
        # terminal, so it must not happen on a plain ``import src.integration``.
        from cli import run as cli_run
        from cli.main import app as cli_app

        from src.integration.governed_graph import GuardedTradingAgentsGraph

        with install(cli_run, GuardedTradingAgentsGraph):
            try:
                cli_app(args=remaining)
            except SystemExit as exc:
                return int(exc.code or 0)
        return 0
    finally:
        EXECUTION_INTENT.reset(token)
