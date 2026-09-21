"""The runner runs every task once in either mode, and the window really bounds the concurrency."""

import asyncio

import pytest

from experiments.runner import run_tasks, validate


class Probe:
    """A worker that records how many tasks are in flight and the order they finish."""

    def __init__(self) -> None:
        self.in_flight = 0
        self.max_in_flight = 0
        self.started: list[int] = []
        self.results: dict[int, object] = {}

    async def work(self, task: int) -> int:
        self.started.append(task)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(0.01)
            if task == 3:
                raise RuntimeError("boom")
            return task * 10
        finally:
            self.in_flight -= 1

    async def collect(self, task: int, outcome) -> None:
        self.results[task] = outcome


async def run(mode: str, window: int, tasks=range(12)) -> Probe:
    probe = Probe()
    await run_tasks(list(tasks), probe.work, mode=mode, window=window, on_result=probe.collect)  # ty: ignore[invalid-argument-type]
    return probe


async def test_sequential_mode_runs_one_task_at_a_time_in_order():
    probe = await run("sequential", window=10)
    assert probe.max_in_flight == 1
    assert probe.started == list(range(12))


@pytest.mark.parametrize("window", [1, 2, 5, 10])
async def test_parallel_mode_never_exceeds_the_window(window):
    probe = await run("parallel", window=window)
    assert probe.max_in_flight == window


async def test_a_window_larger_than_the_task_list_starts_them_all_at_once():
    probe = await run("parallel", window=10, tasks=range(4))
    assert probe.max_in_flight == 4


async def test_window_of_ten_keeps_ten_in_flight_over_a_long_list():
    probe = await run("parallel", window=10, tasks=range(50))
    assert probe.max_in_flight == 10


@pytest.mark.parametrize("mode", ["sequential", "parallel"])
async def test_every_task_is_reported_once_and_a_failure_does_not_stop_the_rest(mode):
    probe = await run(mode, window=4)
    assert sorted(probe.results) == list(range(12))
    assert isinstance(probe.results[3], RuntimeError)
    assert probe.results[5] == 50


async def test_both_modes_report_the_same_outcomes():
    a, b = await run("sequential", 1), await run("parallel", 10)
    assert {k: repr(v) for k, v in a.results.items()} == {k: repr(v) for k, v in b.results.items()}


async def test_the_window_slides_instead_of_waiting_for_a_whole_batch():
    """A slow task holds one slot while the other slots keep working through the list."""
    order: list[int] = []

    async def work(task: int) -> None:
        await asyncio.sleep(0.2 if task == 0 else 0.01)
        order.append(task)

    async def collect(_task, _outcome) -> None:
        return None

    await run_tasks(list(range(8)), work, mode="parallel", window=2, on_result=collect)
    assert order[-1] == 0  # the slow first task finishes last, all the others went past it


@pytest.mark.parametrize(
    ("mode", "window"), [("serial", 1), ("parallel", 0), ("parallel", -3), ("parallel", True)]
)
def test_bad_settings_are_rejected(mode, window):
    with pytest.raises(ValueError):
        validate(mode, window)
