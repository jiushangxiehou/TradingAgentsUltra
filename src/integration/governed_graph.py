"""The guarded graph: the baseline graph with the gate and the evidence chain.

ADR-006 / REQ-HARD-GUARDRAIL / REQ-TRACEABILITY / INV-GUARDRAIL-ZERO-ESCAPE /
INV-RATING-VALIDITY / INV-TRACE-COMPLETENESS

This module EXTENDS ``TradingAgentsGraph``; it does not replace it. Every
upstream behaviour -- the graph, the checkpoint scope, the state log, the memory
log -- is inherited untouched, and the guardrail and the trace are wrapped
around the one method every finished run passes through: ``record_decision``.

Why ``record_decision`` is the guarded boundary
-----------------------------------------------
``propagate()`` and the CLI both end a run there (the CLI streams the graph
itself and then calls it), so a gate placed there sees every run exactly once,
finished, whatever path produced it. Gating earlier would miss the CLI's stream
path; gating later would be after the decision had already been logged.

The order inside ``record_decision`` is pinned, and it is a safety property,
not a style choice:

1. finish the capture -- the evidence set is closed before anything reads it;
2. read the rating the agents actually produced (``run_rating``) -- BEFORE the
   gate rewrites anything, or the gate would be auditing its own output;
3. build the decision from the explicit execution intent and the book;
4. evaluate it with the frozen guardrail;
5. apply the verdict to a COPY, then copy it back into the caller's dict in
   place -- the CLI's ``_offer_reports`` holds that exact object;
6. ``super().record_decision(...)`` -- the memory log is written from the state
   the gate produced, so a rejected run is remembered as Hold;
7. attest the trace and write the sidecar -- after the memory log, because
   evidence about a decision must never be the reason a decision is not
   remembered.

A trace failure never changes the rating. The guardrail is the gate; the trace
is the evidence.

The one clock read in the integration lives in ``create_run_state``: one UTC
instant per run, injected into the recorder so a replay is byte-identical.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path

from tradingagents.agents.rating import run_rating
from tradingagents.dataflows.symbols import safe_ticker_component
from tradingagents.graph.trading_graph import TradingAgentsGraph

from src.guardrail import GuardrailError, GuardrailLimits, evaluate_decision
from src.integration.decision_adapter import ExecutionIntent, build_decision
from src.integration.gate_support import (
    NOTE_GUARDRAIL_CONFIG_ERROR,
    apply_guardrail,
    config_error_result,
    limits_payload,
)
from src.integration.trace_adapter import DataCapture, begin_capture, build_trace

logger = logging.getLogger(__name__)

# The execution intent for the run about to start. ``entry`` sets it from the
# CLI flags; a programmatic caller may set it, or pass ``execution_intent=`` to
# the constructor. Unset means "no intent was supplied", which fails closed.
EXECUTION_INTENT: ContextVar[ExecutionIntent | None] = ContextVar(
    "guardrail_execution_intent", default=None
)

# The sidecar's filename stem: ``guardrail_trace_<trade_date>.json``.
SIDECAR_PREFIX = "guardrail_trace_"


@contextmanager
def _previous_capture(graph: GuardedTradingAgentsGraph):
    """Finish whatever capture a previous run left open, then let this one go.

    A capture left open on the instance means an earlier run never reached
    ``record_decision``. Its patched functions must be restored before a new
    capture patches them again, or the second capture wraps the first and the
    restore order inverts.
    """
    graph._finish_capture()
    try:
        yield
    finally:
        graph._finish_capture()


class GuardedTradingAgentsGraph(TradingAgentsGraph):
    """``TradingAgentsGraph`` with a hard guardrail and an evidence chain."""

    def __init__(
        self,
        *args,
        execution_intent: ExecutionIntent | None = None,
        guardrail_limits: GuardrailLimits | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        # ``None`` is a real value here: "no intent was supplied at all". The
        # adapter turns that into missing required fields, and the guardrail
        # rejects it. There is no default size and no default short.
        self.execution_intent = execution_intent
        self.guardrail_limits = (
            guardrail_limits if isinstance(guardrail_limits, GuardrailLimits) else GuardrailLimits()
        )
        self.portfolio = None
        self._capture: DataCapture | None = None
        self._capture_calls: tuple = ()
        self._capture_errors: list[str] = []
        self._capture_finished = True
        self.started_at: str | None = None
        self.last_trace: dict[str, object] | None = None

    # -- capture lifecycle -------------------------------------------------

    def create_run_state(self, company_name, trade_date, asset_type: str = "stock", portfolio=None):
        """Open the evidence capture, then build the run's initial state.

        This is the integration's ONLY clock read: one UTC instant per run,
        taken before any data is fetched, so it is the honest "as of" for the
        whole run and the same instant on every replay.
        """
        self._finish_capture()
        self.portfolio = portfolio
        self.started_at = datetime.now(UTC).isoformat()
        self._capture_finished = False
        self._capture_calls = ()
        self._capture_errors = []
        self.last_trace = None
        try:
            self._capture = begin_capture(self.started_at)
        except Exception as exc:  # noqa: BLE001 - no capture is not a failed run
            self._capture = None
            self._capture_errors.append(f"capture-start: {type(exc).__name__}")
        try:
            return super().create_run_state(company_name, trade_date, asset_type, portfolio)
        except BaseException:
            # The run never started: leave no patched function behind.
            self._finish_capture()
            raise

    def _finish_capture(self) -> None:
        """Close the capture: store its calls and errors. Never raises, idempotent."""
        if self._capture_finished:
            return
        self._capture_finished = True
        capture = self._capture
        self._capture = None
        if capture is None:
            return
        try:
            self._capture_calls = tuple(capture.finish())
        except Exception as exc:  # noqa: BLE001 - the run outranks its evidence
            self._capture_calls = ()
            self._capture_errors.append(f"capture-finish: {type(exc).__name__}")
        try:
            self._capture_errors.extend(capture.capture_errors)
        except Exception as exc:  # noqa: BLE001
            self._capture_errors.append(f"capture-errors: {type(exc).__name__}")

    # -- run wrappers: always restore -------------------------------------

    def stream_run(self, graph_input, **args):
        """Stream the run, finishing the capture however the stream ends."""
        try:
            yield from super().stream_run(graph_input, **args)
        finally:
            self._finish_capture()

    def propagate(self, company_name, trade_date, asset_type: str = "stock", portfolio=None):
        """Run the graph, finishing the capture however the run ends."""
        with _previous_capture(self):
            return super().propagate(company_name, trade_date, asset_type, portfolio)

    # -- the guarded boundary ---------------------------------------------

    def record_decision(self, company_name, trade_date, final_state):
        """Gate the finished decision, remember it, then attest the evidence."""
        self._finish_capture()

        # (2) The rating the agents produced, read BEFORE the gate rewrites it.
        rating = run_rating(final_state)

        intent = self.execution_intent
        if intent is None:
            intent = EXECUTION_INTENT.get()
        cash = getattr(self.portfolio, "cash", None) if self.portfolio is not None else None
        adapted = build_decision(
            final_state=final_state, rating=rating, intent=intent, available_cash=cash
        )
        notes: list[str] = [
            str(note.get("code")) for note in adapted.report.get("notes", []) if isinstance(note, dict)
        ]

        try:
            result = evaluate_decision(adapted.decision, self.guardrail_limits)
        except GuardrailError as exc:
            # A gate that cannot run is a rejection, not a pass.
            result = config_error_result(exc, self.guardrail_limits)
            notes.append(NOTE_GUARDRAIL_CONFIG_ERROR)

        state_out, payload = apply_guardrail(result, final_state, notes=tuple(notes))
        payload["limits"] = limits_payload(self.guardrail_limits)
        payload["original_rating"] = rating
        payload["load_report"] = adapted.report
        payload["trace"] = None

        # (7) In place: the CLI's _offer_reports reads THIS object.
        final_state.clear()
        final_state.update(state_out)
        final_state["guardrail"] = payload

        # (8) The memory log is written before the trace, so evidence can never
        # cost a decision its memory-log entry.
        super().record_decision(company_name, trade_date, final_state)

        # (9)-(10) Attest, then write the sidecar. Neither may change the rating.
        self._attest(
            company_name=company_name,
            trade_date=trade_date,
            final_state=final_state,
            rating=rating,
            payload=payload,
        )

    # -- trace -------------------------------------------------------------

    def _attest(self, *, company_name, trade_date, final_state, rating, payload) -> None:
        try:
            trace = build_trace(
                calls=self._capture_calls,
                started_at=self.started_at or "",
                final_state=final_state,
                ticker=str(company_name),
                trade_date=str(trade_date),
                rating=str(final_state.get("final_rating") or rating),
                capture_errors=tuple(self._capture_errors),
            )
        except Exception as exc:  # noqa: BLE001 - defensively: build_trace must not raise
            trace = self._trace_failure(exc, final_state, company_name, trade_date, rating)
        self.last_trace = trace
        payload["trace"] = trace
        final_state["guardrail"] = payload
        self._write_sidecar(company_name, trade_date, payload, trace)

    @staticmethod
    def _trace_failure(exc, final_state, company_name, trade_date, rating) -> dict[str, object]:
        from src.integration.trace_adapter import REPORT_KEYS

        unbacked = [
            key for key in REPORT_KEYS
            if isinstance(final_state.get(key), str) and final_state.get(key).strip()
        ]
        return {
            "traceable": False,
            "checked_links": 0,
            "resolved_links": 0,
            "findings": [],
            "decision_id": f"decision:{company_name}:{trade_date}:"
                           f"{final_state.get('final_rating') or rating}",
            "snapshot_count": 0,
            "table": [],
            "unbacked_reports": unbacked,
            "capture_errors": [],
            "trace_error": f"{type(exc).__name__}: {exc}",
        }

    def sidecar_path(self, company_name, trade_date) -> Path:
        """``<results_dir>/<safe_ticker>/TradingAgentsStrategy_logs/guardrail_trace_<date>.json``."""
        safe_ticker = safe_ticker_component(str(company_name))
        return (
            Path(self.config["results_dir"])
            / safe_ticker
            / "TradingAgentsStrategy_logs"
            / f"{SIDECAR_PREFIX}{trade_date}.json"
        )

    def _write_sidecar(self, company_name, trade_date, payload, trace) -> None:
        """Write the audit sidecar beside the state log. A failure is recorded."""
        try:
            path = self.sidecar_path(company_name, trade_date)
            path.parent.mkdir(parents=True, exist_ok=True)
            body = {"guardrail": payload, "trace": trace}
            path.write_text(
                json.dumps(body, indent=4, ensure_ascii=False, sort_keys=True, default=repr),
                encoding="utf-8",
            )
            payload["sidecar"] = str(path)
        except Exception as exc:  # noqa: BLE001 - a failed write never fails a run
            payload["sidecar"] = None
            payload["sidecar_error"] = f"{type(exc).__name__}: {exc}"
            logger.warning("Guardrail sidecar not written for %s: %s", company_name, exc)

    # -- settings ----------------------------------------------------------

    def run_settings(self) -> dict:
        """The upstream settings, plus what this run was judged against."""
        settings = super().run_settings()
        settings["guardrail_limits"] = limits_payload(self.guardrail_limits)
        settings["trace_enabled"] = True
        return settings

