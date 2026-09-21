"""The doctor's live check goes through the same retry owner as the graphs."""

import pytest
from langchain_core.messages import AIMessage

import doctor
from pilot_jev.retry import DEFAULT_ATTEMPTS


class CountingModel:
    def __init__(self, *errors: Exception) -> None:
        self.errors = list(errors)
        self.calls = 0

    async def ainvoke(self, *_args, **_kwargs):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return AIMessage("ok")


@pytest.fixture
def setup(monkeypatch):
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr("pilot_jev.retry.asyncio.sleep", no_sleep)
    monkeypatch.setattr(doctor, "chatgpt_signed_in", lambda: True)

    def use(model: CountingModel) -> CountingModel:
        monkeypatch.setattr(doctor, "make_chat_model", lambda: model)
        return model

    return use


def test_a_transient_failure_is_retried_and_the_check_passes(setup):
    model = setup(CountingModel(ConnectionResetError("reset"), TimeoutError("slow")))
    assert doctor.llm_section("openai") is True
    assert model.calls == DEFAULT_ATTEMPTS


def test_a_permanent_failure_is_reported_after_one_call(setup):
    model = setup(CountingModel(ValueError("rejected")))
    assert doctor.llm_section("openai") is False
    assert model.calls == 1


def test_a_backend_that_stays_down_is_reported_after_the_default_number_of_calls(setup):
    model = setup(CountingModel(*[TimeoutError("slow")] * 10))
    assert doctor.llm_section("openai") is False
    assert model.calls == DEFAULT_ATTEMPTS
