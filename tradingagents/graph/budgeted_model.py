"""Explicit graph-agent model boundary, installed only for an enabled budget."""

import logging
from contextvars import ContextVar
from functools import wraps

from langchain_core.messages import HumanMessage, convert_to_messages
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.runnables import Runnable, RunnableBinding, RunnableGenerator, RunnableSequence

from .context_budget import (
    ContextBudgetBlocked,
    UnverifiableCountError,
    budget_and_send,
    resolve_budget,
)

logger = logging.getLogger(__name__)
_cutoff = ContextVar("agent_budget_cutoff", default=None)


def budget_node(node):
    """Scope only the date to this invocation; history stays on the node input."""
    @wraps(node)
    def invoke(state):
        token = _cutoff.set(state["trade_date"])
        try:
            return node(state)
        finally:
            _cutoff.reset(token)

    return invoke


class BudgetedModel(Runnable):
    """A model runnable which has no direct transport fallback."""

    def __init__(self, model, adapter, config, agent_name, model_name, bound=None):
        self.model = model
        self.adapter = adapter
        self.budget_config = config
        self.agent_name = agent_name
        self.model_name = model_name
        self.bound = bound

    def _bind(self, bound):
        return BudgetedModel(
            self.model, self.adapter, self.budget_config, self.agent_name, self.model_name, bound
        )

    def bind_tools(self, tools):
        return self._bind(self.model.bind_tools(tools)) if self.model is not None else self

    def with_structured_output(self, schema):
        if self.model is None:
            return self
        method = getattr(self.model, "with_structured_output", None)
        if method is None:
            raise NotImplementedError
        chain = method(schema)
        # Only a model binding followed by a local parser can be reconstructed
        # without giving the original runnable a separate transport path.
        if (
            isinstance(chain, RunnableSequence)
            and isinstance(chain.first, RunnableBinding)
            and chain.first.bound is self.model
            and _local_parser_steps(chain.middle)
            and isinstance(chain.last, BaseOutputParser)
        ):
            return RunnableSequence(self._bind(chain.first), *chain.middle, chain.last)
        from langchain_core.runnables import RunnableLambda

        return RunnableLambda(self._block_structured)

    def _block_structured(self, _input):
        cap, threshold = resolve_budget(self.budget_config)
        from .context_budget import BudgetDiagnostic

        diagnostic = BudgetDiagnostic(
            True, "unsupported_structured_request", cap, threshold,
            None, None, 0, 0, 0, False, False,
        )
        self._log(diagnostic, provider_supported=False, counter_exact=None)
        raise ContextBudgetBlocked(diagnostic)

    def invoke(self, input, config=None, **kwargs):
        if kwargs:
            raise UnverifiableCountError("Unverified invocation options")
        return self.invoke_budget(input)

    def invoke_budget(self, input, *, transform=None, cutoff=None):
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        elif hasattr(input, "to_messages"):
            messages = input.to_messages()
        else:
            messages = convert_to_messages(input)

        counter_exact = getattr(self.adapter, "counter_exact", True)
        try:
            reply, diagnostic = budget_and_send(
                formatted_messages=messages,
                bound_model=self.bound if self.bound is not None else self.model,
                config=self.budget_config,
                adapter=self.adapter,
                model_name=self.model_name,
                cut_off=cutoff if cutoff is not None else _cutoff.get(),
                transform=transform,
            )
        except ContextBudgetBlocked as exc:
            diagnostic = exc.diagnostic
            supported = diagnostic.reason not in {"provider_unsupported", "budget_disabled"}
            self._log(
                diagnostic,
                provider_supported=supported if self.adapter is not None else False,
                counter_exact=counter_exact if diagnostic.count_before is not None else None,
            )
            raise
        self._log(diagnostic, provider_supported=True, counter_exact=counter_exact)
        return reply

    def _log(self, diagnostic, *, provider_supported, counter_exact):
        logger.info(
            "agent_input_budget %s",
            {
                "agent_name": self.agent_name,
                "model_name": self.model_name,
                **diagnostic.as_dict(),
                "provider_supported": provider_supported,
                "counter_exact": counter_exact,
                "counter_revision": getattr(self.adapter, "counter_revision", None),
                "count_unit": (
                    "local_token_estimate" if counter_exact is False
                    else "tokens" if counter_exact is True else None
                ),
            },
        )


def _local_parser_steps(steps):
    if not steps:
        return True
    # LangChain OpenAI can insert a local refusal check before its parser.
    from langchain_openai.chat_models import base

    check_refusal = getattr(base, "_check_refusal", None)
    return bool(
        check_refusal is not None and len(steps) == 1
        and isinstance(steps[0], RunnableGenerator)
        and getattr(steps[0], "_transform", None) is check_refusal
    )
