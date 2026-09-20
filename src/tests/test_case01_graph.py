import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage

from case01_routing.graph import build_graph
from tests.conftest import FakeJev, intent, noul, urgency


class ExplodingLLM:
    async def ainvoke(self, *_args, **_kwargs):
        raise AssertionError("the LLM must not be called on this route")


def fake_llm(text: str = "Here is help.") -> GenericFakeChatModel:
    return GenericFakeChatModel(messages=iter([AIMessage(text)]))


async def run(jev: FakeJev, llm, text: str = "hello"):
    return await build_graph(jev=jev, llm=llm).ainvoke({"messages": [HumanMessage(text)]})


async def test_calm_clear_message_reaches_the_llm(calm_billing):
    result = await run(calm_billing, fake_llm("Refund issued."))
    assert result["route"] == "answer"
    assert result["messages"][-1].content == "Refund issued."
    assert result["triage"]["intent"] == "billing"


async def test_triage_is_a_single_fan_out_call(calm_billing):
    await run(calm_billing, fake_llm())
    assert len(calm_billing.calls) == 1
    state, questions = calm_billing.calls[0]
    assert state == "hello"
    assert set(questions) == {"intent", "urgency", "injection"}


CASES = [
    (
        {"intent": intent("billing"), "urgency": urgency(1.9), "injection": noul(0.0)},
        "escalate",
        "This looks urgent",
    ),
    (
        {"intent": intent("other", 0.9), "urgency": urgency(0.0), "injection": noul(0.0)},
        "review",
        "I am not sure",
    ),
    (
        {"intent": intent("billing"), "urgency": urgency(0.0), "injection": noul(0.99)},
        "refuse",
        "I can't help",
    ),
]


@pytest.mark.parametrize(("answers", "route", "reply_start"), CASES)
async def test_non_answer_routes_never_call_the_llm(answers, route, reply_start):
    result = await run(FakeJev(**answers), ExplodingLLM())
    assert result["route"] == route
    assert result["messages"][-1].content.startswith(reply_start)


async def test_empty_message_goes_to_review_without_calling_jev(calm_billing):
    result = await run(calm_billing, ExplodingLLM(), text="   ")
    assert result["route"] == "review"
    assert calm_billing.calls == []


async def test_answer_uses_the_specialist_prompt_for_the_intent():
    seen = {}

    class Recorder(GenericFakeChatModel):
        async def ainvoke(self, messages, *args, **kwargs):
            seen["system"] = messages[0].content
            return AIMessage("done")

    jev = FakeJev(intent=intent("technical"), urgency=urgency(0.0), injection=noul(0.0))
    await run(jev, Recorder(messages=iter([])))
    assert "technical support engineer" in seen["system"]
