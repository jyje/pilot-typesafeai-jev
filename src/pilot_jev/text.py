"""Small message helpers shared by the graph, the middleware, and the CLIs."""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.messages import AnyMessage, HumanMessage


def message_text(message: AnyMessage) -> str:
    """Flatten a message's content, which may be a string or a list of content blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block["text"])
    return "\n".join(parts)


def last_user_text(messages: Sequence[AnyMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return message_text(message)
    return ""
