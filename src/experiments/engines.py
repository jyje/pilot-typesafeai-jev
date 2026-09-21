"""One `classify(text)` per engine: Jev, or a chat model answering with structured output.

Both return a `BaselineOutcome`, so the runner treats them the same. Provider and network errors are
raised (the runner records them), and a reply that does not fit the schema is returned as data.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from experiments.matrix import EngineConfig
from pilot_jev.baseline import BaselineOutcome, SchemaForm, arun_baseline
from pilot_jev.jev import Gateway, Jev
from pilot_jev.llm import make_chat_model
from pilot_jev.triage import parse_triage, triage_questions


class Engine(Protocol):
    async def classify(self, text: str) -> BaselineOutcome: ...


class JevEngine:
    """The official SDK, one request with all three questions, as in Case 01."""

    def __init__(self, gateway: Gateway | None = None) -> None:
        self._jev = gateway or Jev()

    async def classify(self, text: str) -> BaselineOutcome:
        response = await self._jev.aask(text, triage_questions())
        usage = getattr(response, "usage", None)
        return BaselineOutcome(
            parse_triage(response),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )


class ChatEngine:
    """A chat model with structured output. The model is built once, on first use."""

    def __init__(
        self, config: EngineConfig, *, timeout_s: float, method: str | None = None
    ) -> None:
        self._config = config
        self._timeout_s = timeout_s
        self._method = method
        # ChatNVIDIA takes a JSON Schema, not a TypedDict. Same schema, derived from the TypedDict.
        self._schema_form: SchemaForm = "json_schema" if config.engine == "nim" else "typeddict"
        self._chat = None
        self._lock = asyncio.Lock()

    async def _model(self):
        async with self._lock:
            if self._chat is None:
                # Built off the event loop: construction can read files and the environment.
                self._chat = await asyncio.to_thread(
                    make_chat_model,
                    provider=self._config.engine,
                    model=self._config.model,
                    reasoning_effort=self._config.reasoning_effort,
                    thinking=self._config.thinking,
                )
            return self._chat

    async def classify(self, text: str) -> BaselineOutcome:
        chat = await self._model()
        return await asyncio.wait_for(
            arun_baseline(chat, text, method=self._method, schema_form=self._schema_form),
            timeout=self._timeout_s,
        )


def make_engine(config: EngineConfig, *, timeout_s: float) -> Engine:
    if config.engine == "jev":
        return JevEngine()
    return ChatEngine(config, timeout_s=timeout_s)
