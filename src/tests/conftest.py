"""Offline fixtures: a fake Jev that returns real SDK response objects."""

from __future__ import annotations

import json

import pytest
from typesafe_sdk import SystemOneResponse


def build_response(**answers: dict) -> SystemOneResponse:
    payload = {
        "model": "jev-test",
        "answers": answers,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
    # JSON mode is what the SDK itself uses; it turns score-level keys like "0" into ints.
    return SystemOneResponse.model_validate_json(json.dumps(payload))


def intent(choice: str = "billing", confidence: float = 0.9) -> dict:
    return {
        "type": "choice",
        "choice": choice,
        "confidence": confidence,
        "probabilities": {choice: 0.9, "other": 0.1} if choice != "other" else {"other": 1.0},
    }


def urgency(score: float = 0.0) -> dict:
    return {
        "type": "score",
        "score": score,
        "confidence": 1.0,
        "legend": {"0": "low", "1": "mid", "2": "high"},
        "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0},
    }


def noul(p: float) -> dict:
    return {"type": "noul", "noul": p}


class FakeJev:
    """Same two methods as `pilot_jev.jev.Jev`. Returns only the answers that were asked for."""

    model = "jev-test"

    def __init__(self, **answers: dict) -> None:
        self.answers = answers
        self.calls: list[tuple] = []

    def _respond(self, state, questions) -> SystemOneResponse:
        self.calls.append((state, dict(questions)))
        return build_response(**{k: v for k, v in self.answers.items() if k in questions})

    def ask(self, state, questions) -> SystemOneResponse:
        return self._respond(state, questions)

    async def aask(self, state, questions) -> SystemOneResponse:
        return self._respond(state, questions)


@pytest.fixture
def calm_billing() -> FakeJev:
    return FakeJev(intent=intent("billing"), urgency=urgency(0.2), injection=noul(0.01))
