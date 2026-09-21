"""Run many independent tasks either one after another or a window of them at a time.

`mode = "sequential"` awaits each task before starting the next. `mode = "parallel"` keeps up to
`window` tasks in flight and starts the next one as soon as any of them finishes (a sliding window,
not fixed batches). Both modes call the same worker and report every result, or the exception it
raised, to `on_result`, so the choice changes speed and load and nothing else.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from typing import Literal

Mode = Literal["parallel", "sequential"]
MODES: tuple[Mode, ...] = ("parallel", "sequential")


def validate(mode: str, window: int) -> None:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if isinstance(window, bool) or not isinstance(window, int) or window < 1:
        raise ValueError(f"window must be a whole number of at least 1, got {window!r}")


async def run_tasks[T, R](
    tasks: Sequence[T],
    worker: Callable[[T], Awaitable[R]],
    *,
    mode: Mode,
    window: int,
    on_result: Callable[[T, R | BaseException], Awaitable[None]],
) -> None:
    """Run `worker` on every task. A failing task is reported, and the others still run.

    `window` only matters in parallel mode. Cancelling this call cancels the tasks in flight.
    """
    validate(mode, window)

    async def run_one(task: T) -> None:
        try:
            outcome: R | BaseException = await worker(task)
        except Exception as exc:  # noqa: BLE001 - one bad task must not stop the experiment
            outcome = exc
        await on_result(task, outcome)

    if mode == "sequential":
        for task in tasks:
            await run_one(task)
        return

    pending = deque(tasks)

    async def slot() -> None:
        while pending:
            await run_one(pending.popleft())

    await asyncio.gather(*(slot() for _ in range(min(window, len(tasks)))))
