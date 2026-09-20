"""Case 02: Jev inside a Deep Agent, in two shapes.

1. `JevGuardrailMiddleware` screens the user's message once, before the agent starts. A likely
   prompt-injection ends the run with a refusal, so no model tokens are spent on it.
2. `verify_claim` is a tool. The agent hands Jev a claim plus the evidence it found and gets back
   a typed verdict with a confidence, instead of grading its own work in prose.

Usage with LangGraph Studio: `uv run langgraph dev` (the graph is built by `make_graph`).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from deepagents import create_deep_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool, ToolException
from typesafe_sdk import Choice, SystemOneResponse, TypeSafeError

from pilot_jev.jev import Jev
from pilot_jev.llm import make_chat_model
from pilot_jev.text import last_user_text
from pilot_jev.triage import DEFAULT_POLICY, INJECTION_QUESTION

REFUSAL = "I can't help with that request."

VERDICTS = {
    "supported": "The evidence states or clearly implies the claim",
    "contradicted": "The evidence states something that conflicts with the claim",
    "unrelated": "The evidence does not address the claim either way",
}
# Untuned starting point: below this confidence the tool result asks for human review.
REVIEW_BELOW = 0.6

SYSTEM_PROMPT = (
    "You are a careful research assistant. Before you state a factual claim in your final "
    "answer, check it against the evidence you found using the verify_claim tool. Drop claims "
    "that come back contradicted or unrelated, and say so plainly when needs_review is true."
)


class JevGuardrailMiddleware(AgentMiddleware):
    """Refuse likely prompt-injection before the agent loop starts."""

    def __init__(
        self, jev: Jev | None = None, *, block_at: float = DEFAULT_POLICY.injection_block
    ) -> None:
        super().__init__()
        self._jev = jev or Jev()
        self._block_at = block_at

    def _verdict(self, response: SystemOneResponse) -> dict[str, Any] | None:
        # Written so that a NaN probability fails closed.
        if not response.nouls["injection"].noul < self._block_at:
            return {"messages": [AIMessage(REFUSAL)], "jump_to": "end"}
        return None

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state, runtime) -> dict[str, Any] | None:
        text = last_user_text(state["messages"])
        if not text.strip():
            return None
        return self._verdict(self._jev.ask(text, {"injection": INJECTION_QUESTION}))

    @hook_config(can_jump_to=["end"])
    async def abefore_agent(self, state, runtime) -> dict[str, Any] | None:
        text = last_user_text(state["messages"])
        if not text.strip():
            return None
        return self._verdict(await self._jev.aask(text, {"injection": INJECTION_QUESTION}))


def _verify_request(claim: str, evidence: str) -> tuple[dict, dict]:
    state = {"claim": claim, "evidence": evidence}
    questions = {
        "verdict": Choice(
            instructions="Judging only from `evidence`, does it support `claim`?",
            criteria=VERDICTS,
        )
    }
    return state, questions


def _verify_result(response: SystemOneResponse) -> str:
    answer = response.choices["verdict"]
    return json.dumps(
        {
            "verdict": answer.choice,
            "confidence": round(answer.confidence, 3),
            "probabilities": {k: round(v, 3) for k, v in answer.probabilities.items()},
            "needs_review": answer.confidence < REVIEW_BELOW,
        }
    )


def build_verify_tool(jev: Jev | None = None) -> StructuredTool:
    jev = jev or Jev()

    def verify_claim(claim: str, evidence: str) -> str:
        """Check whether the evidence supports the claim. Returns a JSON verdict with confidence."""
        try:
            return _verify_result(jev.ask(*_verify_request(claim, evidence)))
        except TypeSafeError as exc:
            raise ToolException(f"Jev could not verify the claim: {exc}") from exc

    async def averify_claim(claim: str, evidence: str) -> str:
        try:
            return _verify_result(await jev.aask(*_verify_request(claim, evidence)))
        except TypeSafeError as exc:
            raise ToolException(f"Jev could not verify the claim: {exc}") from exc

    # handle_tool_error hands a Jev failure to the model as text instead of aborting the run.
    return StructuredTool.from_function(
        func=verify_claim, coroutine=averify_claim, name="verify_claim", handle_tool_error=True
    )


def make_agent(llm: BaseChatModel | None = None, jev: Jev | None = None, **kwargs: Any):
    """Graph factory for LangGraph Studio; also the entry point for `main.py` and tests."""
    jev = jev or Jev()
    return create_deep_agent(
        model=llm or make_chat_model(),
        tools=[build_verify_tool(jev)],
        system_prompt=SYSTEM_PROMPT,
        middleware=[JevGuardrailMiddleware(jev)],
        **kwargs,
    )


_graph = None


async def make_graph():
    """Zero-argument async factory for `langgraph.json`, which rejects factories with more than two
    parameters. The agent is built once and off the event loop, because the NIM client does
    blocking I/O when it is created.
    """
    global _graph
    if _graph is None:
        _graph = await asyncio.to_thread(make_agent)
    return _graph
