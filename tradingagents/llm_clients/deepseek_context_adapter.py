"""Opt-in DeepSeek Chat Completions transport for agent input budgets."""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from langchain_core.callbacks.manager import CallbackManager
from langchain_core.outputs import LLMResult
from openai.types.chat import ChatCompletion

from tradingagents.graph.context_budget import UnverifiableCountError, require_authorized_send

from .base_client import normalize_content
from .openai_client import OPENAI_COMPATIBLE_PROVIDERS, DeepSeekChatOpenAI

_OFFICIAL_BASE = OPENAI_COMPATIBLE_PROVIDERS["deepseek"].base_url
CITYU_BASE = "https://llm.cs.cityu.edu.hk/v1"
CITYU_MODEL = "CS5351/DeepSeek-V4-Flash"
_REQUEST_FIELDS = frozenset(
    (
        "model", "messages", "tools", "stream", "temperature", "max_tokens", "thinking",
        "parallel_tool_calls", "tool_choice",
    )
)
_MESSAGE_FIELDS = {
    "system": {"role", "content", "name"},
    "user": {"role", "content", "name"},
    "assistant": {"role", "content", "name", "tool_calls", "reasoning_content"},
    "tool": {"role", "content", "tool_call_id"},
}


@dataclass(frozen=True)
class PreparedDeepSeekRequest:
    """Immutable JSON input. Credentials remain in the existing SDK client."""

    body: bytes = field(repr=False)
    _model: DeepSeekChatOpenAI = field(repr=False, compare=False)


class DeepSeekProviderAdapter:
    """Reuse the configured client; enable counting only with an explicit counter.

    Only the budget's scoped authorization can unlock the transport.
    No production counter is supplied here.
    """

    def __init__(
        self,
        model_name: str,
        counter: Callable[[PreparedDeepSeekRequest], int] | None = None,
        *,
        counter_revision: str | None = None,
        base_url: str | None = None,
    ):
        self.base_url = (base_url or _OFFICIAL_BASE).rstrip("/")
        if self.base_url != _OFFICIAL_BASE and (self.base_url, model_name) != (CITYU_BASE, CITYU_MODEL):
            raise ValueError("Unsupported DeepSeek budget endpoint/model")
        self.model_name = model_name
        self._counter = counter
        self.counter_revision = counter_revision

    def supports(self, model: str) -> bool:
        return bool(callable(self._counter) and self.counter_revision and model == self.model_name)

    def _supports_client(self, model) -> bool:
        return (
            isinstance(model, DeepSeekChatOpenAI)
            and self.supports(model.model_name)
            and str(model.root_client.base_url).rstrip("/") == self.base_url
        )

    def prepare(self, formatted_messages, bound_model) -> PreparedDeepSeekRequest:
        model = getattr(bound_model, "bound", bound_model)
        if not self._supports_client(model):
            raise UnverifiableCountError("DeepSeek model, counter or endpoint is unsupported")

        options = getattr(bound_model, "kwargs", {})
        # LangChain's tracing metadata is not part of the provider schema.
        wire_options = {k: v for k, v in options.items() if k != "ls_structured_output_format"}
        payload = model._get_request_payload(formatted_messages, **wire_options)
        if model._use_responses_api(payload):
            raise UnverifiableCountError("DeepSeek budget requires Chat Completions")
        if "max_completion_tokens" in payload:
            if "max_tokens" in payload:
                raise UnverifiableCountError("Ambiguous output token limit")
            payload["max_tokens"] = payload.pop("max_completion_tokens")
        extra_body = payload.pop("extra_body", None)
        if extra_body is not None:
            if set(extra_body) - {"thinking"} or set(extra_body) & payload.keys():
                raise UnverifiableCountError("Unsupported or duplicate DeepSeek options")
            payload.update(extra_body)
        if (
            payload.keys() - _REQUEST_FIELDS
            or payload.get("model") != self.model_name
            or payload.get("stream", False) is not False
        ):
            raise UnverifiableCountError("Unsupported DeepSeek request fields")
        if "thinking" in payload and payload["thinking"] not in (
            {"type": "enabled"}, {"type": "disabled"}
        ):
            raise UnverifiableCountError("Unsupported DeepSeek thinking configuration")
        for message in payload["messages"]:
            role = message["role"]
            content = message.get("content")
            if (
                role not in _MESSAGE_FIELDS
                or message.keys() - _MESSAGE_FIELDS[role]
                or (not isinstance(content, str) and not (
                    role == "assistant" and content is None and message.get("tool_calls")
                ))
            ):
                raise UnverifiableCountError("Unsupported DeepSeek message fields")
        return PreparedDeepSeekRequest(
            body=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8"),
            _model=model,
        )

    def count(self, request: PreparedDeepSeekRequest) -> int:
        if self._counter is None or not self.supports(request._model.model_name):
            raise UnverifiableCountError("DeepSeek counter is unavailable")
        tokens = self._counter(request)
        if type(tokens) is not int or tokens <= 0:
            raise UnverifiableCountError("DeepSeek counter did not return a positive integer")
        return tokens

    def send(self, request: PreparedDeepSeekRequest):
        body = require_authorized_send(self, request)
        model = request._model
        client = model.root_client
        if not self._supports_client(model):
            raise UnverifiableCountError("DeepSeek send configuration no longer matches")
        # Use the existing SDK's transport/auth without rebuilding the model
        # request or giving the SDK's typed completion builder a chance to add fields.
        # Preserve usage callbacks while keeping prompt and reply text out of
        # the events emitted by this transport.
        callbacks = CallbackManager.configure(local_callbacks=model.callbacks)
        run, = callbacks.on_chat_model_start({"name": self.model_name}, [[]])
        try:
            response = client.with_options(max_retries=0).post(
                "/chat/completions", cast_to=ChatCompletion, content=body,
                options={"headers": {"Content-Type": "application/json"}},
            )
            result = model._create_chat_result(response)
        except Exception:
            run.on_llm_error(RuntimeError("Budgeted transport failed"))
            raise
        safe_generations = [
            generation.model_copy(update={
                "text": "",
                "generation_info": None,
                "message": type(generation.message)(
                    content="", usage_metadata=generation.message.usage_metadata
                ),
            })
            for generation in result.generations
        ]
        run.on_llm_end(LLMResult(generations=[safe_generations]))
        return normalize_content(result.generations[0].message)
