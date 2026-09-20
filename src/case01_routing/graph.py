"""Case 01: Jev as the router of a LangGraph StateGraph.

    __start__ -> triage --+--> answer    (chat model, specialist prompt per intent)
                          +--> escalate  (urgent: hand to a person, no LLM call)
                          +--> review    (unclear or low confidence: ask a person, no LLM call)
                          +--> refuse    (prompt-injection attempt, no LLM call)

`triage` makes one Jev request that fans out three independent questions. Code (`decide`) turns
the typed answers into a route. Usage with LangGraph Studio: `uv run langgraph dev`.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from pilot_jev.jev import Gateway, Jev
from pilot_jev.llm import make_chat_model
from pilot_jev.retry import with_retries
from pilot_jev.text import last_user_text
from pilot_jev.triage import DEFAULT_POLICY, NO_TEXT, Policy, arun_triage, decide

SPECIALISTS = {
    "billing": "You are a billing support specialist. Be precise about charges and next steps.",
    "technical": "You are a technical support engineer. Give concrete troubleshooting steps.",
    "account": "You are an account support specialist. Never ask for passwords.",
    "chitchat": "You are a friendly assistant. Keep it short and warm.",
}

CANNED = {
    "escalate": "This looks urgent, so I have passed it to a person who will follow up right away.",
    "review": "I am not sure what you need yet. A person will review this and get back to you.",
    "refuse": "I can't help with that request.",
}


class RoutingState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    triage: dict
    route: str


def build_graph(
    *, jev: Gateway | None = None, llm: BaseChatModel | None = None, policy: Policy | None = None
):
    """Build the graph. Backends resolve lazily so importing this module needs no credentials."""
    policy = policy or DEFAULT_POLICY
    jev = jev or Jev()
    model = llm
    model_lock = asyncio.Lock()

    async def chat_model() -> BaseChatModel:
        """Build the chat model once, off the event loop (the NIM client does blocking I/O)."""
        nonlocal model
        async with model_lock:
            if model is None:
                model = await asyncio.to_thread(make_chat_model)
            return model

    async def triage_node(state: RoutingState) -> dict:
        text = last_user_text(state["messages"])
        result = await arun_triage(jev, text) if text.strip() else NO_TEXT
        return {"triage": result.as_dict(), "route": decide(result, policy)}

    async def answer_node(state: RoutingState) -> dict:
        system = SystemMessage(SPECIALISTS[state["triage"]["intent"]])
        model = await chat_model()
        # Retry only the chat model call. Replaying the graph would call Jev again.
        reply = await with_retries(lambda: model.ainvoke([system, *state["messages"]]))
        return {"messages": [reply]}

    def canned(route: str):
        def node(state: RoutingState) -> dict:
            return {"messages": [AIMessage(CANNED[route])]}

        return node

    def pick(state: RoutingState) -> str:
        return state["route"]

    # ty does not yet accept a TypedDict class where langgraph wants its state type var.
    builder = StateGraph(RoutingState)  # ty: ignore[invalid-argument-type]
    builder.add_node("triage", triage_node)
    builder.add_node("answer", answer_node)
    for route in CANNED:
        builder.add_node(route, canned(route))

    builder.add_edge(START, "triage")
    builder.add_conditional_edges("triage", pick, ["answer", *CANNED])
    for route in ("answer", *CANNED):
        builder.add_edge(route, END)
    return builder.compile()


graph = build_graph()
