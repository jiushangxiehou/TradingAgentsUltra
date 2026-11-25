"""OFFLINE CLI-entry tests (ADR-006, REQ-HARD-GUARDRAIL).

No API, no network, no LLM. The "CLI" here is a fake module with the same two
names the real one has (``cli.main.app`` and ``cli.run.TradingAgentsGraph``),
so the wrapper's behaviour is tested without importing typer's prompt machinery
or touching the user's preferences.

C6 asserts the negative that matters: running the entry point must not reach a
provider, and must not construct a real graph.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("tradingagents")

from src.integration import entry
from src.integration.decision_adapter import ExecutionIntent
from src.integration.governed_graph import EXECUTION_INTENT

pytestmark = pytest.mark.offline

TRADE_DATE = "2026-11-24"


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeApp:
    """Stands in for ``cli.main.app``: records its argv, optionally raises."""

    def __init__(self, code: int | None = None) -> None:
        self.seen: list[list[str]] = []
        self.code = code

    def __call__(self, args=None):
        self.seen.append(list(args) if args is not None else None)
        if self.code is not None:
            raise SystemExit(self.code)


class FakeRunModule:
    """Stands in for ``cli.run``: one attribute, the class the CLI builds."""

    def __init__(self) -> None:
        class RealGraph:
            def __init__(self, *args, **kwargs):
                self.args = args

        self.TradingAgentsGraph = RealGraph


class FakeMainModule:
    def __init__(self, app) -> None:
        self.app = app


def recording_app(body, *, code=None):
    """An app whose call body is body.

    The callable must be defined on the TYPE: assigning __call__ on an
    instance does not change how Python invokes it, so a per-test body needs a
    per-test class.
    """

    class App:
        def __init__(self) -> None:
            self.seen: list = []

        def __call__(self, args=None):
            self.seen.append(list(args) if args is not None else None)
            if code is not None:
                raise SystemExit(code)
            return body(args)

    return App()


@pytest.fixture
def fake_cli(monkeypatch):
    """Install ``cli.main`` and ``cli.run`` fakes for the duration of one test."""
    run_module = FakeRunModule()
    app = FakeApp()
    main_module = FakeMainModule(app)
    monkeypatch.setitem(sys.modules, "cli", SimpleNamespace(main=main_module, run=run_module))
    monkeypatch.setitem(sys.modules, "cli.main", main_module)
    monkeypatch.setitem(sys.modules, "cli.run", run_module)
    # ``set_app`` rebinds the module attribute too: the wrapper resolves
    # ``cli.main.app`` at call time, exactly as the real CLI does.
    holder = SimpleNamespace(run=run_module, app=app, main=main_module)

    def set_app(new_app):
        holder.app = new_app
        main_module.app = new_app

    holder.set_app = set_app
    return holder


# ---------------------------------------------------------------------------
# C1 -- install patches, then restores -- including on an exception
# ---------------------------------------------------------------------------

def test_c1_install_patches_and_restores():
    module = FakeRunModule()
    original = module.TradingAgentsGraph

    class Guarded:
        pass

    with entry.install(module, Guarded) as installed:
        assert installed is Guarded
        assert module.TradingAgentsGraph is Guarded
    assert module.TradingAgentsGraph is original


def test_c1_install_restores_after_an_exception():
    module = FakeRunModule()
    original = module.TradingAgentsGraph

    class Guarded:
        pass

    with pytest.raises(RuntimeError), entry.install(module, Guarded):
        assert module.TradingAgentsGraph is Guarded
        raise RuntimeError("run blew up")
    assert module.TradingAgentsGraph is original


# ---------------------------------------------------------------------------
# C2 -- flags are stripped; upstream argv is untouched; the class is visible
# ---------------------------------------------------------------------------

def test_c2_flags_are_stripped_and_upstream_args_pass_through(fake_cli):
    code = entry.run_guarded_cli(
        ["NVDA", "--guardrail-position-fraction", "0.05",
         "--guardrail-short-amount", "250", "--date", TRADE_DATE]
    )
    assert code == 0
    assert fake_cli.app.seen == [["NVDA", "--date", TRADE_DATE]]


def test_c2_the_upstream_argv_is_not_reordered(fake_cli):
    argv = ["--date", TRADE_DATE, "NVDA", "--analysts", "market,news", "--no-checkpoint"]
    entry.run_guarded_cli(list(argv))
    assert fake_cli.app.seen == [argv]


def test_c2_the_guarded_class_is_installed_at_call_time_and_restored(fake_cli):
    original = fake_cli.run.TradingAgentsGraph
    result: dict = {}

    def body(args=None):
        # Visible from INSIDE the app, which is when the CLI builds its graph.
        result["during"] = fake_cli.run.TradingAgentsGraph
        result["intent"] = EXECUTION_INTENT.get()

    fake_cli.set_app(recording_app(body))
    entry.run_guarded_cli(["--guardrail-position-fraction", "0.05"])

    assert result["during"] is not original
    assert result["during"].__name__ == "GuardedTradingAgentsGraph"
    assert result["intent"] == ExecutionIntent(size_pct=0.05, short_amount=None)
    assert fake_cli.run.TradingAgentsGraph is original     # restored


def test_c2_the_context_var_is_reset_after_the_run(fake_cli):
    seen: dict = {}
    fake_cli.set_app(recording_app(lambda args: seen.setdefault("intent", EXECUTION_INTENT.get())))

    entry.run_guarded_cli(["--guardrail-short-amount", "0"])

    assert seen["intent"] == ExecutionIntent(size_pct=None, short_amount=0.0)
    assert EXECUTION_INTENT.get() is None


def test_c2_no_flags_means_no_intent(fake_cli):
    seen: dict = {}
    fake_cli.set_app(recording_app(lambda args: seen.setdefault("intent", EXECUTION_INTENT.get())))

    assert entry.run_guarded_cli(["NVDA"]) == 0
    assert seen["intent"] is None


def test_c2_system_exit_from_the_app_becomes_the_return_code(fake_cli):
    fake_cli.set_app(recording_app(lambda args: None, code=3))

    assert entry.run_guarded_cli(["NVDA"]) == 3
    assert fake_cli.run.TradingAgentsGraph.__name__ == "RealGraph"   # restored


def test_c2_an_exception_from_the_app_still_restores(fake_cli):
    original = fake_cli.run.TradingAgentsGraph

    def body(args=None):
        raise RuntimeError("boom")

    fake_cli.set_app(recording_app(body))
    with pytest.raises(RuntimeError):
        entry.run_guarded_cli(["NVDA"])
    assert fake_cli.run.TradingAgentsGraph is original
    assert EXECUTION_INTENT.get() is None


# ---------------------------------------------------------------------------
# C3 -- an invalid float is exit 2, and the app never runs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "argv",
    [
        ["NVDA", "--guardrail-position-fraction", "abc"],
        ["NVDA", "--guardrail-position-fraction", "0.05", "--guardrail-short-amount", "x"],
        ["NVDA", "--guardrail-position-fraction", "0.05", "--guardrail-short-amount"],
        ["NVDA", "--guardrail-position-fraction"],
    ],
    ids=["bad-position", "bad-short", "short-without-value", "position-without-value"],
)
def test_c3_invalid_value_returns_2_and_never_calls_app(fake_cli, argv):
    assert entry.run_guarded_cli(argv) == 2
    assert fake_cli.app.seen == []


def test_c3_an_empty_value_is_not_silently_zero(fake_cli):
    assert entry.run_guarded_cli(["NVDA", "--guardrail-position-fraction", ""]) == 2
    assert fake_cli.app.seen == []


# ---------------------------------------------------------------------------
# C4 -- one flag is a valid, half-specified intent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "argv,expected",
    [
        (["--guardrail-position-fraction", "0.05"], ExecutionIntent(0.05, None)),
        (["--guardrail-short-amount", "0"], ExecutionIntent(None, 0.0)),
    ],
    ids=["position-only", "short-only"],
)
def test_c4_one_flag_leaves_the_other_field_none(argv, expected):
    intent, remaining = entry.strip_guardrail_flags(argv)
    assert intent == expected
    assert remaining == []


def test_c4_a_half_specified_intent_is_rejected_by_the_graph(monkeypatch, tmp_path):
    """The CLI's job ends at handing over a partial intent; the gate fails closed."""
    from src.guardrail import evaluate_decision
    from src.integration.decision_adapter import build_decision

    intent, _ = entry.strip_guardrail_flags(["--guardrail-position-fraction", "0.05"])
    adapted = build_decision(
        final_state={"company_of_interest": "NVDA", "final_rating": "Buy"},
        rating="Buy", intent=intent, available_cash=10_000.0,
    )
    result = evaluate_decision(adapted.decision)
    assert result.passed is False
    assert result.audit.trigger.value == "MALFORMED_DECISION"
    assert result.decision.rating == "Hold"


# ---------------------------------------------------------------------------
# C5 -- --help is a clean exit
# ---------------------------------------------------------------------------

def test_c5_help_exits_zero_through_the_wrapper():
    """The real typer app, real argv: ``--help`` must not be turned into an error.

    ``--help`` is upstream's flag, not the integration's, so it must pass
    through untouched and exit 0. No run is started, so no graph is built.
    """
    assert entry.run_guarded_cli(["--help"]) == 0


def test_c5_help_is_not_eaten_by_the_integration_parser():
    intent, remaining = entry.strip_guardrail_flags(["--help"])
    assert intent is None
    assert remaining == ["--help"]


# Cleanup 3: the guarded options must be discoverable, on stderr only.

@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_c5_help_prints_the_guarded_options_line_to_stderr(fake_cli, capsys, flag):
    """typer's help cannot list flags typer never sees, so we say so ourselves.

    STDERR, not stdout: the upstream help text on stdout must stay
    byte-identical for anything that greps or diffs it. The exit code is the
    upstream one (0), unchanged.
    """
    code = entry.run_guarded_cli([flag])
    captured = capsys.readouterr()

    assert code == 0
    assert entry.GUARDED_OPTIONS_LINE in captured.err.splitlines()
    assert entry.GUARDED_OPTIONS_LINE == (
        "guarded options: --guardrail-position-fraction FLOAT (0.05 = 5%), "
        "--guardrail-short-amount FLOAT"
    )
    assert entry.GUARDED_OPTIONS_LINE not in captured.out
    # The help request still reached the CLI untouched.
    assert fake_cli.app.seen == [[flag]]


def test_c5_the_options_line_is_printed_before_delegating(fake_cli, capsys):
    """Ordering: printed first, so it survives a CLI that exits immediately."""
    seen_so_far: list[str] = []

    def body(args=None):
        seen_so_far.append(capsys.readouterr().err)

    fake_cli.set_app(recording_app(body))
    entry.run_guarded_cli(["--help"])

    assert entry.GUARDED_OPTIONS_LINE in seen_so_far[0]


def test_c5_an_ordinary_run_prints_no_options_line(fake_cli, capsys):
    assert entry.run_guarded_cli(["NVDA"]) == 0
    captured = capsys.readouterr()
    assert entry.GUARDED_OPTIONS_LINE not in captured.err
    assert captured.err == ""


def test_c5_the_guarded_flags_do_not_trigger_the_help_line(fake_cli, capsys):
    """Our own flags work on their own; help output is for help."""
    entry.run_guarded_cli(["NVDA", "--guardrail-position-fraction", "0.05"])
    assert entry.GUARDED_OPTIONS_LINE not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# C6 -- no real network or graph construction
# ---------------------------------------------------------------------------

def test_c6_no_provider_client_is_constructed(fake_cli):
    """A guarded run must not reach a model or a vendor from these tests."""
    from tradingagents import llm_clients

    calls: list[str] = []
    original = getattr(llm_clients, "create_llm_client", None)

    def spy(*args, **kwargs):
        calls.append("create")
        if original is not None:
            return original(*args, **kwargs)
        return None

    try:
        if original is not None:
            from unittest import mock

            with mock.patch.object(llm_clients, "create_llm_client", spy):
                entry.run_guarded_cli(["NVDA", "--guardrail-position-fraction", "0.05"])
        else:
            entry.run_guarded_cli(["NVDA", "--guardrail-position-fraction", "0.05"])
    finally:
        assert calls == []
    assert fake_cli.app.seen == [["NVDA"]]


def test_c6_the_entry_module_imports_the_cli_lazily():
    """``import src.integration.entry`` must not import the CLI itself."""
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(entry.__file__).read_text(encoding="utf-8"))
    top_level = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            top_level |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            top_level.add(node.module.split(".")[0])
    assert "cli" not in top_level
    assert "tradingagents" not in top_level
