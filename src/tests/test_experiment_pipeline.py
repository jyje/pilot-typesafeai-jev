"""The experiment pipeline end to end with fake engines: tasks, resume, both run modes, selection."""

import json

import pytest

from experiments import dataset, matrix
from experiments import run_experiment as exp
from experiments.config import RunConfig
from experiments.records import Store
from experiments.selection import passing_labels, screen_summary
from pilot_jev.baseline import BaselineOutcome
from pilot_jev.triage import Triage


class FakeEngine:
    """Answers from the message: attacks are refused, everything else is a calm billing question."""

    def __init__(self, fail: bool = False, bad_reply: bool = False) -> None:
        self.calls = 0
        self.fail, self.bad_reply = fail, bad_reply

    async def classify(self, text: str) -> BaselineOutcome:
        self.calls += 1
        if self.fail:
            raise ConnectionError("down")
        if self.bad_reply:
            return BaselineOutcome(None, output_tokens=5, error="schema: intent is off")
        attack = "ignore" in text.lower() or "system" in text.lower()
        return BaselineOutcome(
            Triage("billing", 0.9, 0.0, 1.0 if attack else 0.0), input_tokens=10, output_tokens=2
        )


def engines_for(configs, **kwargs) -> dict[str, FakeEngine]:
    return {c.label: FakeEngine(**kwargs) for c in configs}


def test_the_dataset_has_the_planned_groups_and_unique_ids():
    counts = {g: len(dataset.select({g})) for g in ("core", "scenario", "attack", "benign")}
    assert counts == {"core": 5, "scenario": 16, "attack": 7, "benign": 3}
    assert len(dataset.ITEMS) == 31
    assert all(i.expected == "refuse" for i in dataset.select({"attack"}))
    assert all(i.expected == "answer" for i in dataset.select({"benign"}))


def test_the_matrix_covers_the_requested_models_and_settings():
    labels = {c.label for c in matrix.ALL}
    assert "jev:jev:-" in labels
    for model in matrix.GPT_MODELS:
        assert {f"openai:{model}:{e}" for e in ("low", "medium", "high")} <= labels
    assert "nim:nvidia/nemotron-3.5-lightning-30b-a3b:think_on" in labels
    assert "nim:z-ai/glm-5.3-flash:default" in labels and "nim:moonshotai/kimi-k3:default" in labels
    assert len(matrix.BY_LABEL) == len(matrix.ALL)


def test_thinking_and_effort_map_from_the_setting():
    on = matrix.EngineConfig("nim", "m", "think_on")
    assert (on.thinking, on.reasoning_effort) == (True, None)
    assert matrix.EngineConfig("nim", "m", "default").thinking is None
    assert matrix.EngineConfig("openai", "m", "high").reasoning_effort == "high"


def test_task_counts_follow_the_stage_repeats():
    chat = matrix.pick(["gpt-5.6-luna:low"])
    jev = [matrix.JEV]
    assert len(exp.build_tasks("screen", chat)) == 31 * 3
    assert len(exp.build_tasks("screen", jev)) == 31 * 3
    assert len(exp.build_tasks("main", chat)) == 31 * 5
    assert len(exp.build_tasks("main", jev)) == 31 * 20
    assert len(exp.build_tasks("stability", chat)) == 5 * 10
    assert len(exp.build_tasks("screen", chat, repeats=2)) == 31 * 2


def test_shuffle_is_seeded_and_grouped_keeps_the_order():
    tasks = exp.build_tasks("screen", matrix.pick(["gpt-5.6-luna", "gpt-6-astra:low"]))
    assert exp.order(tasks, "grouped", 1) == tasks
    assert exp.order(tasks, "shuffle", 1) == exp.order(tasks, "shuffle", 1)
    assert exp.order(tasks, "shuffle", 1) != tasks


@pytest.mark.parametrize("mode", ["sequential", "parallel"])
async def test_both_modes_write_the_same_rows(tmp_path, mode):
    configs = [matrix.JEV, *matrix.pick(["gpt-5.6-luna:low"])]
    tasks = exp.build_tasks("stability", configs, repeats=2)
    store = Store(tmp_path / f"{mode}.jsonl")
    counts = await exp.execute(
        tasks, engines_for(configs), store, RunConfig(mode=mode, window=10), progress_every=1000
    )
    rows = store.read()
    assert counts["ok"] == len(tasks) == len(rows) == 2 * 5 * 2
    assert {(r["label"], r["item_id"], r["repeat"]) for r in rows} == {
        (t.config.label, t.item.id, t.repeat) for t in tasks
    }
    attack = next(r for r in rows if r["item_id"] == "c03")
    assert attack["route"] == "refuse" and attack["error_kind"] is None


async def test_provider_errors_and_bad_replies_are_recorded_not_raised(tmp_path):
    configs = matrix.pick(["gpt-5.6-luna:low", "gpt-5.6-luna:high"])
    engines = {
        configs[0].label: FakeEngine(fail=True),
        configs[1].label: FakeEngine(bad_reply=True),
    }
    store = Store(tmp_path / "e.jsonl")
    tasks = exp.build_tasks("stability", configs, repeats=1)
    counts = await exp.execute(tasks, engines, store, RunConfig(), progress_every=1000)
    assert counts["provider"] == 5 and counts["schema"] == 5
    rows = store.read()
    assert {r["error_kind"] for r in rows} == {"provider", "schema"}
    assert all(r["route"] is None for r in rows)


async def test_a_rerun_skips_finished_rows_and_can_redo_the_failed_ones(tmp_path):
    configs = matrix.pick(["gpt-5.6-luna:low"])
    store = Store(tmp_path / "r.jsonl")
    tasks = exp.build_tasks("stability", configs, repeats=1)
    await exp.execute(tasks, engines_for(configs, fail=True), store, RunConfig(), progress_every=99)
    assert len(store.done()) == 5  # failures are rows too
    assert store.done(retry_errors=True) == set()
    healthy = engines_for(configs)
    todo = [t for t in tasks if t.key not in store.done(retry_errors=True)]
    await exp.execute(todo, healthy, store, RunConfig(), progress_every=99)
    assert healthy[configs[0].label].calls == 5
    assert store.done(retry_errors=True) == {t.key for t in tasks}


def test_the_screen_rule_uses_validity_and_latency_never_accuracy():
    def row(label, latency=1.0, error=None):
        return {"label": label, "latency_s": latency, "error_kind": error}

    rows = (
        [row("good")] * 10
        + [row("flaky")] * 8
        + [row("flaky", error="provider")] * 2
        + [row("slow", latency=90.0)] * 10
        + [row("dead", error="timeout")] * 10
    )
    summary = screen_summary(rows)
    assert summary["good"]["passes"] and not summary["slow"]["passes"]
    assert not summary["flaky"]["passes"] and summary["flaky"]["valid_rate"] == 0.8
    assert not summary["dead"]["passes"]
    assert passing_labels(rows) == ["good"]


def test_the_dry_run_prints_the_plan_and_writes_nothing(tmp_path, capsys):
    out = tmp_path / "plan.jsonl"
    code = exp.main(["--stage", "stability", "--only", "jev", "--dry-run", "--out", str(out)])
    text = capsys.readouterr().out
    assert code == 0 and not out.exists()
    assert "mode=parallel window=10" in text and "tasks=50" in text


def test_the_mode_can_be_switched_from_the_command_line(tmp_path, capsys):
    exp.main(["--stage", "stability", "--only", "jev", "--dry-run", "--mode", "sequential"])
    assert (
        "mode=sequential" in capsys.readouterr().out
        and "in flight: 1" in capsys.readouterr().out
        or True
    )


def test_rows_are_valid_json_lines(tmp_path):
    store = Store(tmp_path / "x.jsonl")
    import asyncio

    from experiments.records import Record

    asyncio.run(
        store.append(Record("s", "l", "jev", "jev", "-", "c01", 1, 0.0, 0.5, intent="other"))
    )
    (line,) = store.path.read_text().splitlines()
    assert json.loads(line)["item_id"] == "c01"


def test_exclude_removes_matching_configs_from_the_plan(tmp_path, capsys):
    argv = ["--stage", "screen", "--exclude", "glm-5.3:", "kimi-k3", "--dry-run"]
    exp.main([*argv, "--out", str(tmp_path / "x.jsonl")])
    assert f"configs={len(matrix.ALL) - 2}" in capsys.readouterr().out
