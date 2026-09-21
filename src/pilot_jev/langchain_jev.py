"""The same `Gateway`, backed by the LangChain integration instead of the TypeSafe SDK.

`langchain-typesafe` (optional extra, alpha) wraps the Jev API as a LangChain `Runnable`. It has its
own question and response classes, so this adapter only converts the shapes: SDK questions go in as
`{"state": ..., "questions": ...}`, and the answer comes back as the SDK's `SystemOneResponse`. Graphs,
middleware, and tests keep talking to `Gateway` and cannot tell the two apart.

Install with `uv sync --extra langchain-typesafe`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from typesafe_sdk import SystemOneResponse
from typesafe_sdk.constants import DEFAULT_MODEL

from pilot_jev.env import load_env
from pilot_jev.jev import Question


def _langchain_typesafe() -> Any:
    try:
        import langchain_typesafe
    except ImportError as exc:  # pragma: no cover - depends on the optional extra
        raise ImportError(
            "langchain-typesafe is not installed. Run `uv sync --extra langchain-typesafe`."
        ) from exc
    return langchain_typesafe


def to_langchain_question(question: Question) -> Any:
    """Convert an SDK `Choice`, `Noul`, or `Score` into the integration's class of the same name."""
    lt = _langchain_typesafe()
    fields = question.model_dump(mode="json", exclude_none=True)
    kind = fields.pop("type")
    return {"choice": lt.Choice, "noul": lt.Noul, "score": lt.Score}[kind](**fields)


def from_langchain_response(response: Any) -> SystemOneResponse:
    """Convert the integration's `ClassifierResponse` into the SDK's `SystemOneResponse`."""
    return SystemOneResponse.model_validate_json(response.model_dump_json(exclude_none=True))


class LangChainJev:
    """One `TypeSafeClassifier.invoke` per `ask`. Independent questions belong in the same call."""

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        load_env()
        self._model = model or os.getenv("JEV_MODEL") or DEFAULT_MODEL
        self._classifier = _langchain_typesafe().TypeSafeClassifier(
            model=self._model, **({"api_key": api_key} if api_key else {})
        )

    @property
    def model(self) -> str:
        return self._model

    def _request(self, state: str | Mapping, questions: Mapping[str, Question]) -> dict[str, Any]:
        return {
            "state": state,
            "questions": {qid: to_langchain_question(q) for qid, q in questions.items()},
        }

    def ask(self, state: str | Mapping, questions: Mapping[str, Question]) -> SystemOneResponse:
        return from_langchain_response(self._classifier.invoke(self._request(state, questions)))

    async def aask(
        self, state: str | Mapping, questions: Mapping[str, Question]
    ) -> SystemOneResponse:
        return from_langchain_response(
            await self._classifier.ainvoke(self._request(state, questions))
        )
