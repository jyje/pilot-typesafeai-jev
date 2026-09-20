"""The gateway passes state and questions through and picks the right model."""

from typing import ClassVar

from pilot_jev import jev as jev_module
from pilot_jev.jev import DEFAULT_MODEL, Jev
from pilot_jev.triage import triage_questions
from tests.conftest import build_response, intent, noul, urgency


class FakeClient:
    instances: ClassVar[list["FakeClient"]] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls = []
        FakeClient.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def system_one(self, **kwargs):
        self.calls.append(kwargs)
        return build_response(intent=intent(), urgency=urgency(), injection=noul(0.0))


class AsyncFakeClient(FakeClient):
    async def system_one(self, **kwargs):
        self.calls.append(kwargs)
        return build_response(intent=intent(), urgency=urgency(), injection=noul(0.0))


def setup_function():
    FakeClient.instances.clear()


def test_ask_passes_state_and_questions_and_closes_the_client(monkeypatch):
    monkeypatch.setattr(jev_module, "TypeSafeClient", FakeClient)
    monkeypatch.delenv("JEV_MODEL", raising=False)
    questions = triage_questions()
    Jev().ask("hello", questions)
    client = FakeClient.instances[0]
    assert client.kwargs["model"] == DEFAULT_MODEL
    assert client.calls == [{"state": "hello", "questions": questions}]


async def test_aask_uses_the_async_client(monkeypatch):
    monkeypatch.setattr(jev_module, "AsyncTypeSafeClient", AsyncFakeClient)
    await Jev(model="jev-1.2.3").aask({"claim": "c"}, triage_questions())
    client = FakeClient.instances[0]
    assert client.kwargs["model"] == "jev-1.2.3"
    assert client.calls[0]["state"] == {"claim": "c"}


def test_model_can_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("JEV_MODEL", "jev-from-env")
    assert Jev().model == "jev-from-env"
