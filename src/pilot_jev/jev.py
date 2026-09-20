"""Thin gateway over the TypeSafe SDK.

Every node, tool, and middleware in this repo talks to Jev through `Jev`, so tests can swap in a
fake with the same two methods and nothing else in the code needs to know.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol

from typesafe_sdk import (
    AsyncTypeSafeClient,
    Choice,
    Noul,
    Score,
    SystemOneResponse,
    TypeSafeClient,
)
from typesafe_sdk.constants import DEFAULT_MODEL

from pilot_jev.env import load_env

Question = Choice | Noul | Score


class Gateway(Protocol):
    """What graphs, middleware, and tools need from Jev. `Jev` and the test fakes both satisfy it."""

    @property
    def model(self) -> str: ...

    def ask(self, state: str | Mapping, questions: Mapping[str, Question]) -> SystemOneResponse: ...

    async def aask(
        self, state: str | Mapping, questions: Mapping[str, Question]
    ) -> SystemOneResponse: ...


class Jev:
    """One System One call per `ask`. Independent questions belong in the same call."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        load_env()
        self._api_key = api_key
        self._model = model or os.getenv("JEV_MODEL") or DEFAULT_MODEL

    @property
    def model(self) -> str:
        return self._model

    def ask(self, state: str | Mapping, questions: Mapping[str, Question]) -> SystemOneResponse:
        with TypeSafeClient(api_key=self._api_key, model=self._model) as client:
            return client.system_one(state=state, questions=questions)

    async def aask(
        self, state: str | Mapping, questions: Mapping[str, Question]
    ) -> SystemOneResponse:
        # A client per call keeps this safe across the event loops LangGraph creates. The price is a
        # new connection per call, which is fine for a pilot.
        async with AsyncTypeSafeClient(api_key=self._api_key, model=self._model) as client:
            return await client.system_one(state=state, questions=questions)
