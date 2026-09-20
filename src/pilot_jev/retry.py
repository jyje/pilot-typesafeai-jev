"""Retry a whole graph call when the chat model backend fails transiently.

`ChatNVIDIA` has no retry setting, and wrapping it in `with_retry()` would stop it being a chat
model that agents can bind tools to. Retrying the call around the graph is the simple fix.

Jev errors are never retried here: the TypeSafe SDK already retries them, and replaying the graph
would call (and bill) Jev again.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable

import aiohttp
import requests
from typesafe_sdk import TypeSafeError

TRANSIENT = (
    ConnectionError,
    TimeoutError,
    aiohttp.ClientError,
    requests.exceptions.ConnectionError,
    requests.exceptions.Timeout,
)
# langchain-nvidia-ai-endpoints raises HTTP failures as a plain Exception("[503] ...").
_NIM_HTTP_TRANSIENT = re.compile(r"^\[(429|500|502|503|504)\]")


def is_transient(exc: Exception) -> bool:
    if isinstance(exc, TypeSafeError):
        return False
    if isinstance(exc, TRANSIENT):
        return True
    return type(exc) is Exception and bool(_NIM_HTTP_TRANSIENT.match(str(exc)))


async def with_retries[T](
    call: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    delay: float = 5.0,
    on_retry: Callable[[int, Exception], None] | None = None,
) -> T:
    for attempt in range(1, attempts + 1):
        try:
            return await call()
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            if on_retry:
                on_retry(attempt, exc)
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")
