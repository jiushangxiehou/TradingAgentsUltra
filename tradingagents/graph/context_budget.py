"""Context-input token budgeting for the news_analyst pilot (REQ-CONTEXT-BUDGET).

Scope: the news_analyst pilot only. This module bounds the *context input* -- the
prompt payload a model receives -- on a per-request basis. It is deliberately
separate from two quantities it must never be confused with:

* the **output limit** (``max_tokens`` / ``max_output_tokens``); untouched here;
* **total API spend** (cumulative input+output over a run), observed only by
  ``cli.stats_handler``; not budgeted here.

Provider-adapter contract (why counting is trustworthy)
------------------------------------------------------
A real hard cap can only be proven against the *exact* request that is sent. So
counting and sending MUST go through ONE injected provider adapter:

    request = adapter.prepare(formatted_messages, bound_model)  # exact provider request
    tokens  = adapter.count(request)                            # declared budget units
    reply   = adapter.send(request)                             # the SAME request

The adapter counts the actual prepared request using its declared policy.
The CityU local estimate is a separate policy and does not claim provider
accuracy. Post-call ``usage_metadata`` cannot authorize a send. If no adapter is supplied (or
the adapter reports the model/format unsupported), the budget **fails closed**
with :class:`ContextBudgetBlocked` and the model is never called.

The module does not imitate a provider wire format for real providers. It only
builds a *description* of the request (via the adapter) and hands that same
object to ``count`` and ``send``. For the mock stage a fake adapter implements
the same three methods.

Budget policy
-------------
* **Disabled by default.** With no budget configured, the node keeps its exact
  legacy chain and this module is never entered.
* **One deterministic extractive pass, two counts at most.** Initial count and
  final count only. The pass drops whole evidence *blocks* and never rewrites,
  merges-across, or re-summarises fact text. No model summariser.
* **Deduplicate identical evidence while respecting tool grouping.** A block is
  a tool-call message plus its tool results (kept/dropped together), so
  deduplication can never orphan a ``tool_call_id``. Deduplication compares
  evidence and provenance independently of transaction IDs.
* **Preserve independent evidence.** Only explicitly irrelevant blocks may
  be trimmed for size. Equivalent tool exchanges are deduplicated as a unit.
* **Filter explicit future availability.** Future evidence is excluded before
  counting. A placeholder keeps tool pairing intact when a surviving exchange
  contains an unavailable result. Event dates never stand in for availability.
* **Anchors preserved.** System and human turns are never dropped.
* **Block on overflow / unverifiable.** When the mandatory content alone exceeds
  the cap, or a final count cannot be proven, raise :class:`ContextBudgetBlocked`
  with a content-free reason. Never return empty messages that let the graph
  silently continue.

Upstream boundaries (NOT fixed here): data vendors own point-in-time retrieval
filtering and attach provenance. Some current retrieval strings carry no
per-fact timestamp, so this layer cannot and does not invent one.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from contextvars import ContextVar
from datetime import UTC, date, datetime, time
from threading import Lock
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# Diagnostic reason codes (no prompt/news content is ever logged).
REASON_DISABLED = "budget_disabled"
REASON_UNVERIFIABLE = "count_unverifiable"
REASON_UNSUPPORTED = "provider_unsupported"
REASON_INVALID_HISTORY = "invalid_tool_history"
REASON_OVER_AFTER_COMPACTION = "over_after_compaction"
REASON_MANDATORY_OVER_CAP = "mandatory_context_over_cap"
REASON_OK = "within_budget"
REASON_OK_COMPACTED = "compacted_within_budget"
REASON_NO_COMPACTION_NEEDED = "no_compaction_needed"


class UnverifiableCountError(RuntimeError):
    """Raised by an adapter when it cannot prove an exact count for a request."""


@dataclasses.dataclass
class BudgetDiagnostic:
    """Structured, content-free record of one budgeting decision."""

    enabled: bool
    reason: str
    budget_tokens: int | None
    threshold_tokens: int | None
    count_before: int | None
    count_after: int | None
    deduped_blocks: int
    dropped_blocks: int
    compaction_passes: int
    allowed_send: bool
    overflow: bool
    summarized_blocks: int = 0

    def as_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class ContextBudgetBlocked(RuntimeError):
    """Raised to stop a send that would violate the budget contract.

    Carries a content-free :class:`BudgetDiagnostic`. The caller must NOT call
    the model when this is raised (zero requests).
    """

    def __init__(self, diagnostic: BudgetDiagnostic) -> None:
        self.diagnostic = diagnostic
        # Content-free structured warning: reason/cap/threshold/counts/attempts
        # only -- never prompt or news text.
        logger.warning(
            "context budget blocked send: reason=%s cap=%s threshold=%s "
            "count_before=%s count_after=%s attempts=%s overflow=%s",
            diagnostic.reason,
            diagnostic.budget_tokens,
            diagnostic.threshold_tokens,
            diagnostic.count_before,
            diagnostic.count_after,
            diagnostic.compaction_passes,
            diagnostic.overflow,
        )
        super().__init__(f"context budget blocked send: {diagnostic.reason}")


@runtime_checkable
class ProviderAdapter(Protocol):
    """The one trusted seam for counting and sending the identical request.

    Implementations are provider-specific (or a fake for the mock stage) and must
    satisfy:

      * ``prepare(formatted_messages, bound_model)`` returns the exact provider
        request object for those messages and that model, including system
        prompt, tool schemas, roles, and provider framing that a real send would
        include. It must not mutate ``formatted_messages``.
      * ``supports(model)`` returns True only when the adapter can both count and
        send for that exact model. False => caller fails closed.
      * ``count(request)`` returns the input-budget count for the prepared request.
        Exact counters return the provider's input-token count. The CityU local
        estimator counts UTF-8 bytes of the frozen request body as budget units
        and declares ``counter_exact=False``; these units are a local estimate,
        not provider token usage. Raise :class:`UnverifiableCountError` when the
        configured counting policy cannot produce a valid count.
      * ``send(request)`` sends that exact ``request`` and returns the model
        reply. A prepared request exposes immutable ``body: bytes``. The transport
        must consume ``require_authorized_send(self, request)`` exactly once and
        send the returned bytes unchanged, with automatic retries disabled.
    """

    def supports(self, model: str) -> bool: ...

    def prepare(self, formatted_messages: list, bound_model: Any) -> Any: ...

    def count(self, request: Any) -> int: ...

    def send(self, request: Any) -> Any: ...


@dataclasses.dataclass
class BudgetResult:
    """The request to send plus the diagnostic that produced it.

    ``request`` is the exact adapter-prepared object; the caller counts it (again
    only if needed) and sends it. When blocked, :class:`ContextBudgetBlocked` is
    raised instead and this object is not produced.
    """

    request: Any
    diagnostic: BudgetDiagnostic


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def _strict_positive_int(value: Any) -> int | None:
    """Return value as a strict positive int, or None if unset.

    Raises ValueError for present-but-invalid values (0, negative, bool, float,
    non-numeric). This is fail-closed: an invalid budget must not silently
    disable or misbehave.
    """
    if value is None or value == "":
        return None
    if type(value) is int:
        number = value
    elif isinstance(value, str) and value.isascii() and value.isdecimal():
        number = int(value)
    else:
        raise ValueError("context budget must be a positive integer")
    if number <= 0:
        raise ValueError(f"context budget must be > 0, got {number!r}")
    return number


def resolve_budget(config: dict | None) -> tuple[int | None, int | None]:
    """Return ``(cap, threshold)`` after strict validation; ``(None, None)`` if off.

    Partial configuration (only one of the two set) is an error: budgets are
    enabled only as a complete pair, so a half-configured run fails loudly rather
    than running unbounded.
    """
    if not config:
        return None, None
    cap = _strict_positive_int(config.get("context_input_hard_cap_tokens"))
    threshold = _strict_positive_int(config.get("context_input_compaction_threshold_tokens"))
    if cap is None and threshold is None:
        return None, None
    if cap is None or threshold is None:
        raise ValueError(
            "context budget requires BOTH context_input_hard_cap_tokens and "
            "context_input_compaction_threshold_tokens (partial config is invalid)"
        )
    if threshold > cap:
        raise ValueError(
            f"compaction threshold ({threshold}) must be <= hard cap ({cap})"
        )
    return cap, threshold


def is_budget_enabled(config: dict | None) -> bool:
    """True only when a complete, valid budget pair is configured."""
    cap, threshold = resolve_budget(config)
    return cap is not None and threshold is not None


# ---------------------------------------------------------------------------
# Message classification / atomic block grouping (pairing-safe)
# ---------------------------------------------------------------------------

def _msg_role(msg: Any) -> str:
    return getattr(msg, "type", getattr(msg, "role", "unknown"))


def _explicit_provenance(message: Any) -> dict:
    """Prefer response metadata; combine conflicting dates conservatively."""
    provenance = {}
    dates = []
    relevance = set()
    for container in (message.additional_kwargs, message.response_metadata):
        data = container.get("provenance")
        if not isinstance(data, dict):
            continue
        provenance.update({key: value for key, value in data.items() if value is not None})
        if data.get("available_at") is not None:
            dates.append(_availability_instant(data["available_at"]))
        if "relevance" in data:
            relevance.add(data["relevance"])
    if dates:
        # The later UTC availability instant cannot expose either source early.
        provenance["available_at"] = max(dates)
    if len(relevance) > 1:
        provenance.pop("relevance", None)
    return provenance


def _unique_arguments(pairs):
    arguments = dict(pairs)
    if len(arguments) != len(pairs):
        raise ValueError("duplicate tool argument")
    return arguments


def _tool_ids(message: Any) -> list[str]:
    normalized = getattr(message, "tool_calls", [])
    canonical = [call.get("id") for call in normalized]
    if getattr(message, "invalid_tool_calls", None) or message.additional_kwargs.get("function_call"):
        raise ValueError("invalid tool call")
    if "tool_calls" not in message.additional_kwargs:
        # LangChain-native messages have a single representation.
        ids = canonical
    else:
        raw = message.additional_kwargs["tool_calls"]
        if not isinstance(raw, list) or any(not isinstance(call, dict) for call in raw):
            raise ValueError("invalid raw tool calls")
        ids = [call.get("id") for call in raw]
        if ids != canonical:
            raise ValueError("raw and normalized tool call IDs differ")
        for original, call in zip(raw, normalized, strict=True):
            function = original.get("function")
            if not isinstance(function, dict) or function.get("name") != call["name"]:
                raise ValueError("raw and normalized tool names differ")
            raw_args = json.loads(function.get("arguments"), object_pairs_hook=_unique_arguments)
            if not isinstance(raw_args, dict) or json.dumps(
                raw_args, sort_keys=True, allow_nan=False
            ) != json.dumps(call["args"], sort_keys=True, allow_nan=False):
                raise ValueError("raw and normalized tool arguments differ")
    if any(not isinstance(call_id, str) or not call_id.strip() for call_id in ids):
        raise ValueError("invalid tool call ID")
    return ids


def group_into_blocks(messages: list) -> list[dict]:
    """Pair by ID, normalizing interleaved results without mutating history."""
    calls = set()
    results = {}
    call_ids_by_index = {}
    for index, message in enumerate(messages):
        ids = _tool_ids(message)
        call_ids_by_index[index] = ids
        for call_id in ids:
            if call_id in calls:
                raise ValueError("duplicate tool call ID")
            calls.add(call_id)
        if _msg_role(message) == "tool":
            call_id = message.tool_call_id
            if call_id not in calls or call_id in results:
                raise ValueError("unmatched or duplicate tool result")
            results[call_id] = message
    if calls != results.keys():
        raise ValueError("missing tool result")
    return [
        _make_block(
            [message, *(results[call_id] for call_id in call_ids_by_index[index])],
            anchor=_msg_role(message) in ("system", "human"),
        )
        for index, message in enumerate(messages)
        if _msg_role(message) != "tool"
    ]


def _identity(message: Any) -> str:
    # Keep source metadata and model-visible content, independent of transaction IDs.
    data = message.model_dump(exclude={"id", "tool_call_id", "tool_calls", "usage_metadata"})
    if _msg_role(message) == "tool" and _explicit_provenance(message).get("fact_id"):
        content = data.get("content")
        if isinstance(content, str):
            # Only normalize line-ending whitespace on explicitly identified
            # evidence. The tool arguments and all provenance still must match.
            data["content"] = "\n".join(line.rstrip() for line in content.splitlines()).rstrip()
    return json.dumps(
        data,
        sort_keys=True,
        default=str,
    )


def _has_assistant_text(message):
    return bool(message.content or message.additional_kwargs.get("reasoning_content"))


def _make_block(msgs: list, *, anchor: bool) -> dict:
    first, *results = msgs
    signature = None
    if results and not first.content and not first.additional_kwargs.get("function_call"):
        arguments = [
            {key: value for key, value in call.items() if key != "id"}
            for call in first.tool_calls
        ]
        first_metadata = {
            key: value for key, value in first.additional_kwargs.items() if key != "tool_calls"
        }
        first_metadata["response_metadata"] = first.response_metadata
        signature = (
            json.dumps([arguments, first_metadata], sort_keys=True, default=str),
            tuple(_identity(result) for result in results),
        )
    return {
        "messages": msgs,
        "anchor": anchor,
        "signature": signature,
        "disposable": not anchor and not (_msg_role(first) == "ai" and _has_assistant_text(first)) and all(
            _explicit_provenance(message).get("relevance") == "irrelevant"
            for message in (results or msgs)
        ),
    }


def flatten_blocks(blocks: list[dict]) -> list:
    out = []
    for b in blocks:
        out.extend(b["messages"])
    return out


# ---------------------------------------------------------------------------
# Compaction policy: dedup + explicit filters + priority
# ---------------------------------------------------------------------------

def _dedup_blocks(blocks: list[dict]) -> tuple[list[dict], int]:
    """Collapse equivalent exchanges within one user turn.

    Anchors are never deduplicated (system/human turns are semantically ordered).
    Returns (blocks, number_removed).
    """
    seen: set = set()
    kept: list[dict] = []
    removed = 0
    for b in blocks:
        if b["anchor"]:
            seen.clear()
        if b["anchor"] or b["signature"] is None:
            kept.append(b)
            continue
        if b["signature"] in seen:
            removed += 1
            continue
        seen.add(b["signature"])
        kept.append(b)
    return kept, removed


def _availability_instant(value: str) -> datetime:
    """Treat a date as the end of its UTC day; timestamps require an offset."""
    if len(value) == 10:
        return datetime.combine(date.fromisoformat(value), time.max, UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("availability timestamp requires a UTC offset")
    return parsed.astimezone(UTC)


def _filter_explicit_future(blocks: list[dict], cut_off: str | None) -> tuple[list[dict], int]:
    """Validate explicit availability before counting or sending a request.

    An undated message relies on upstream selection. The caller must supply a
    cutoff even for undated history. A future anchor blocks the request instead
    of silently removing a system or user instruction.
    """
    if cut_off is None:
        raise ValueError("missing analysis cutoff")
    cutoff = _availability_instant(cut_off)

    def is_future(message):
        value = _explicit_provenance(message).get("available_at")
        return value is not None and value > cutoff

    kept = []
    removed = 0
    for block in blocks:
        first, *results = block["messages"]
        first_future = is_future(first)
        result_future = [is_future(result) for result in results]
        if block["anchor"] and first_future:
            raise ValueError("required message is unavailable on the analysis date")
        if not results:
            if first_future:
                removed += 1
            else:
                kept.append(block)
            continue
        unavailable = [first_future or future for future in result_future]
        if all(unavailable) and (first_future or not _has_assistant_text(first)):
            removed += 1
        elif any(unavailable):
            # Preserve available assistant text and call/result pairing without
            # rewriting the provider's tool-call representation.
            from langchain_core.messages import ToolMessage

            safe_results = [
                ToolMessage(content="Evidence unavailable on the analysis date.", tool_call_id=result.tool_call_id)
                if future else result
                for result, future in zip(results, unavailable, strict=True)
            ]
            kept.append(_make_block([first, *safe_results], anchor=False))
        else:
            kept.append(block)
    return kept, removed


_FACT_FIELDS = (
    "fact_id", "ticker", "subject", "event_date", "available_at", "published_at",
    "source", "amount", "causality", "relevance",
)


def _summarize_tool_result(message):
    """Extract one explicitly annotated low-priority fact into a labelled record.

    The source must contain a verbatim line for every required field. Free-form
    vendor prose cannot safely be summarized by this rule.
    """
    if _msg_role(message) != "tool" or not isinstance(message.content, str):
        return message
    provenance = _explicit_provenance(message)
    fields = provenance.get("summary_fact")
    if provenance.get("relevance") not in {"irrelevant", "low"} or not isinstance(fields, dict):
        return message
    if set(fields) != set(_FACT_FIELDS) or any(
        not isinstance(value, str) or not value or len(value.splitlines()) != 1
        for value in fields.values()
    ):
        return message
    if any(fields[field] != provenance[field] for field in _FACT_FIELDS if field in provenance
           and field != "available_at"):
        return message
    try:
        if _availability_instant(fields["available_at"]) != provenance.get("available_at"):
            return message
    except ValueError:
        return message
    lines = [f"{field}: {fields[field]}" for field in _FACT_FIELDS]
    source_lines = message.content.splitlines()
    if any(source_lines.count(line) != 1 for line in lines):
        return message
    summary = "Extracted source fact:\n" + "\n".join(lines)
    return message.model_copy(update={"content": summary}) if len(summary) < len(message.content) else message


def _summarize_blocks(blocks):
    compacted = []
    summarized = 0
    for block in blocks:
        first, *results = block["messages"]
        extracted = [_summarize_tool_result(result) for result in results]
        if any(before is not after for before, after in zip(results, extracted, strict=True)):
            compacted.append({**block, "messages": [first, *extracted]})
            summarized += 1
        else:
            compacted.append(block)
    return compacted, summarized


def _block_size(block: dict) -> int:
    return sum(len(_identity(message)) for message in block["messages"])


def _trim_to_cap(original, blocks, cap, initial_count):
    """Plan one bounded cut from explicitly disposable evidence; never re-estimate."""
    excess = initial_count - cap
    if excess <= 0:
        return blocks, 0
    sizes = {id(block): _block_size(block) for block in original}
    total = sum(sizes.values())
    kept_ids = {id(block) for block in blocks}
    removed_size = sum(size for key, size in sizes.items() if key not in kept_ids)
    target = excess * total
    candidates = sorted(
        (block for block in blocks if block["disposable"]),
        key=lambda block: sizes[id(block)],
        reverse=True,
    )
    removed = set()
    for block in candidates:
        if removed_size * initial_count >= target:
            break
        removed.add(id(block))
        removed_size += sizes[id(block)]
    return [block for block in blocks if id(block) not in removed], len(removed)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def budget_and_send(
    *,
    formatted_messages: list,
    bound_model: Any,
    config: dict | None,
    adapter: ProviderAdapter | None,
    model_name: str,
    cut_off: str | None = None,
    send: bool = True,
    transform=None,
) -> tuple[Any, BudgetDiagnostic]:
    """Prepare, count, compact (one pass), re-count, and optionally send.

    Returns ``(reply_or_request, diagnostic)``. When over budget after the single
    pass, or when the count cannot be proven, raises :class:`ContextBudgetBlocked`
    (the caller must not call the model). The SAME ``request`` produced by
    ``adapter.prepare`` is counted and sent.

    Counting happens at most twice: the initial full request, and once after the
    single compaction pass. ``send=False`` prepares/counts/compacts but does not
    send (used to inspect the exact request without a provider round-trip).
    """
    cap, threshold = resolve_budget(config)
    if cap is None or threshold is None:
        raise ContextBudgetBlocked(
            BudgetDiagnostic(
                enabled=False,
                reason=REASON_DISABLED,
                budget_tokens=None,
                threshold_tokens=None,
                count_before=None,
                count_after=None,
                deduped_blocks=0,
                dropped_blocks=0,
                compaction_passes=0,
                allowed_send=False,
                overflow=False,
            )
        )

    if adapter is None or not _adapter_supports(adapter, model_name):
        raise ContextBudgetBlocked(
            BudgetDiagnostic(
                enabled=True,
                reason=REASON_UNSUPPORTED if adapter is not None else REASON_UNVERIFIABLE,
                budget_tokens=cap,
                threshold_tokens=threshold,
                count_before=None,
                count_after=None,
                deduped_blocks=0,
                dropped_blocks=0,
                compaction_passes=0,
                allowed_send=False,
                overflow=False,
            )
        )

    try:
        blocks = group_into_blocks(formatted_messages)
        blocks, future_dropped = _filter_explicit_future(blocks, cut_off)
    except (TypeError, ValueError):
        raise ContextBudgetBlocked(
            BudgetDiagnostic(
                True, REASON_INVALID_HISTORY, cap, threshold, None, None, 0, 0, 0, False, False
            )
        ) from None

    def _prepare(blk_list):
        try:
            messages = flatten_blocks(blk_list)
            if transform is not None:
                messages = transform(messages)
            request = adapter.prepare(messages, bound_model)
            if type(getattr(request, "body", None)) is not bytes:
                raise UnverifiableCountError("Prepared request must expose immutable bytes")
            return request
        except Exception:  # noqa: BLE001 - preparation failure is unverifiable
            logger.warning("Provider adapter prepare() failed; count unverifiable.")
            return None

    def _count_request(request: Any) -> int | None:
        if request is None:
            return None
        return _safe_count(adapter, request)

    # Initial request + count (#1). The SAME prepared request object is reused
    # for sending when no compaction is needed, so count and send act on the
    # identical request. A preparation failure maps to count_unverifiable.
    initial_request = _prepare(blocks)
    count_before_body = getattr(initial_request, "body", None)
    count_before = _count_request(initial_request)
    if count_before is None:
        raise ContextBudgetBlocked(
            BudgetDiagnostic(
                enabled=True,
                reason=REASON_UNVERIFIABLE,
                budget_tokens=cap,
                threshold_tokens=threshold,
                count_before=None,
                count_after=None,
                deduped_blocks=0,
                dropped_blocks=0,
                compaction_passes=0,
                allowed_send=False,
                overflow=False,
            )
        )

    # NOTE: we deliberately do NOT take a separate "anchors-only" count here --
    # the review bounds counting to at most two per request (initial + final).
    # Mandatory overflow is detected from the single final count below: if only
    # anchors remain and the final count still exceeds the cap, that is
    # ``mandatory_context_over_cap``.

    # Within threshold -> no compaction, send the SAME request that was counted.
    if count_before <= threshold:
        reply = _send_authorized(adapter, initial_request, count_before_body) if send else initial_request
        return reply, BudgetDiagnostic(
            enabled=True,
            reason=REASON_NO_COMPACTION_NEEDED,
            budget_tokens=cap,
            threshold_tokens=threshold,
            count_before=count_before,
            count_after=count_before,
            deduped_blocks=0,
            dropped_blocks=future_dropped,
            compaction_passes=0,
            allowed_send=True,
            overflow=False,
        )

    # Over threshold: ONE extractive pass (dedup + explicit filters + priority),
    # then a SINGLE trim to cap and a final count (count #2). No second pass.
    passed, deduped = _dedup_blocks(blocks)
    trimmed, dropped_by_trim = _trim_to_cap(blocks, passed, cap, count_before)
    trimmed, summarized = _summarize_blocks(trimmed)

    # Final request + count (#2). Reuse this exact object for sending.
    final_request = _prepare(trimmed)
    count_after_body = getattr(final_request, "body", None)
    count_after = _count_request(final_request)
    if count_after is None:
        raise ContextBudgetBlocked(
            BudgetDiagnostic(
                enabled=True,
                reason=REASON_UNVERIFIABLE,
                budget_tokens=cap,
                threshold_tokens=threshold,
                count_before=count_before,
                count_after=None,
                deduped_blocks=deduped,
                dropped_blocks=future_dropped + dropped_by_trim,
                compaction_passes=1,
                summarized_blocks=summarized,
                allowed_send=False,
                overflow=False,
            )
        )

    if count_after > cap:
        mandatory_only = all(b["anchor"] for b in trimmed)
        raise ContextBudgetBlocked(
            BudgetDiagnostic(
                enabled=True,
                reason=REASON_MANDATORY_OVER_CAP if mandatory_only else REASON_OVER_AFTER_COMPACTION,
                budget_tokens=cap,
                threshold_tokens=threshold,
                count_before=count_before,
                count_after=count_after,
                deduped_blocks=deduped,
                dropped_blocks=future_dropped + dropped_by_trim,
                compaction_passes=1,
                summarized_blocks=summarized,
                allowed_send=False,
                overflow=True,
            )
        )

    request = final_request
    reply = _send_authorized(adapter, request, count_after_body) if send else request
    return reply, BudgetDiagnostic(
        enabled=True,
        reason=REASON_OK_COMPACTED,
        budget_tokens=cap,
        threshold_tokens=threshold,
        count_before=count_before,
        count_after=count_after,
        deduped_blocks=deduped,
        dropped_blocks=future_dropped + dropped_by_trim,
        compaction_passes=1,
        summarized_blocks=summarized,
        allowed_send=True,
        overflow=False,
    )


@dataclasses.dataclass
class _SendPermit:
    adapter: ProviderAdapter
    request: Any
    body: bytes | None
    fingerprint: bytes | None
    consumed: bool = False
    lock: Any = dataclasses.field(default_factory=Lock)


# Copies of the execution context share the same permit and lock.
_send_permit: ContextVar[_SendPermit | None] = ContextVar("news_budget_send_permit", default=None)


def require_authorized_send(adapter: ProviderAdapter, request: Any) -> bytes:
    permit = _send_permit.get()
    if permit is None or permit.adapter is not adapter or permit.request is not request:
        raise UnverifiableCountError("Final request was not authorized by the context budget")
    with permit.lock:
        if permit.consumed:
            raise UnverifiableCountError("Final request was not authorized by the context budget")
        permit.consumed = True
        body = getattr(request, "body", None)
        if (
            type(body) is not bytes
            or hashlib.sha256(body).digest() != permit.fingerprint
            or body != permit.body
        ):
            raise UnverifiableCountError("Final request body differs from the counted body")
        return permit.body


def _send_authorized(adapter: ProviderAdapter, request: Any, body: Any) -> Any:
    if type(body) is not bytes:
        raise UnverifiableCountError("No immutable counted request body")
    permit = _SendPermit(adapter, request, body, hashlib.sha256(body).digest())
    token = _send_permit.set(permit)
    try:
        return adapter.send(request)
    finally:
        with permit.lock:
            permit.consumed = True
        _send_permit.reset(token)


# ---------------------------------------------------------------------------
# Adapter helpers (fail-closed)
# ---------------------------------------------------------------------------

def _adapter_supports(adapter: ProviderAdapter, model_name: str) -> bool:
    try:
        return adapter.supports(model_name) is True
    except Exception:  # noqa: BLE001 - unsupported on any fault; do not leak details
        logger.warning("Provider adapter supports() failed; treating as unsupported.")
        return False


def _safe_count(adapter: ProviderAdapter, request: Any) -> int | None:
    """Return the local budget count or None without logging request contents."""
    try:
        value = adapter.count(request)
    except UnverifiableCountError:
        return None
    except Exception:  # noqa: BLE001 - fail closed; do not leak exception/content
        logger.warning("Provider adapter count() failed; count unverifiable.")
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        return None
    return value


# ---------------------------------------------------------------------------
# Content-free diagnostics serialisation
# ---------------------------------------------------------------------------

def diagnostic_json(diag: BudgetDiagnostic) -> str:
    """Serialise a diagnostic without any prompt/news content (safe to log)."""
    return json.dumps(diag.as_dict(), sort_keys=True)
