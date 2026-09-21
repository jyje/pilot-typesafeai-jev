"""The LangChain-backed gateway converts shapes and nothing else."""

import pytest

pytest.importorskip("langchain_typesafe")

import langchain_typesafe as lt
from typesafe_sdk import SystemOneResponse

from pilot_jev.langchain_jev import LangChainJev, to_langchain_question
from pilot_jev.triage import arun_triage, decide, parse_triage, triage_questions

ANSWERS = {
    "intent": {
        "type": "choice",
        "choice": "billing",
        "confidence": 0.9,
        "probabilities": {"billing": 0.9, "other": 0.1},
    },
    "urgency": {
        "type": "score",
        "score": 0.2,
        "legend": {0: "can wait", 1: "soon", 2: "urgent"},
        "probabilities": {0: 0.8, 1: 0.2, 2: 0.0},
        "confidence": 0.8,
    },
    "injection": {"type": "noul", "noul": 0.01},
}


class FakeClassifier:
    """Stands in for `TypeSafeClassifier`: records the request and returns a real response."""

    def __init__(self) -> None:
        self.requests: list[dict] = []

    def _respond(self, request: dict) -> lt.ClassifierResponse:
        self.requests.append(request)
        answers = {k: v for k, v in ANSWERS.items() if k in request["questions"]}
        return lt.ClassifierResponse.model_validate(
            {"model": "jev-test", "answers": answers, "usage": {}, "request_id": "req-1"}
        )

    def invoke(self, request: dict) -> lt.ClassifierResponse:
        return self._respond(request)

    async def ainvoke(self, request: dict) -> lt.ClassifierResponse:
        return self._respond(request)


@pytest.fixture
def gateway(monkeypatch) -> LangChainJev:
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    jev = LangChainJev()
    jev._classifier = FakeClassifier()
    return jev


def test_sdk_questions_become_the_integrations_classes():
    converted = {k: to_langchain_question(q) for k, q in triage_questions().items()}
    assert isinstance(converted["intent"], lt.Choice)
    assert isinstance(converted["urgency"], lt.Score)
    assert isinstance(converted["injection"], lt.Noul)


def test_ask_sends_state_and_all_questions_in_one_request(gateway):
    response = gateway.ask("hello", triage_questions())
    (request,) = gateway._classifier.requests
    assert request["state"] == "hello"
    assert set(request["questions"]) == {"intent", "urgency", "injection"}
    assert isinstance(response, SystemOneResponse)


def test_the_answer_comes_back_as_the_sdk_response_type(gateway):
    response = gateway.ask("hello", triage_questions())
    assert response.choices["intent"].choice == "billing"
    assert response.scores["urgency"].score == 0.2
    assert response.nouls["injection"].noul == 0.01


def test_triage_runs_unchanged_on_this_gateway(gateway):
    triage = parse_triage(gateway.ask("I was charged twice", triage_questions()))
    assert triage.intent == "billing"
    assert decide(triage) == "answer"


async def test_aask_and_async_triage_work_too(gateway):
    triage = await arun_triage(gateway, "I was charged twice")
    assert decide(triage) == "answer"
    assert len(gateway._classifier.requests) == 1


def test_a_missing_package_gives_a_pointer_to_the_extra(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "langchain_typesafe":
            raise ImportError(name)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match="uv sync --extra langchain-typesafe"):
        LangChainJev()
