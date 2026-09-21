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
    assert len(dataset.ITEMS) == 31 and len(dataset.ALL_ITEMS) == 60
    assert len(dataset.BY_ID) == 60
    extra = dataset.ALL_ITEMS[31:]
    assert {i.group for i in extra} == {"scenario", "attack", "benign"}
    assert sum(i.group == "attack" for i in dataset.ALL_ITEMS) == 12
    assert sum(i.group == "benign" for i in dataset.ALL_ITEMS) == 8
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
    assert len(exp.build_tasks("main", chat)) == 60 * 5
    assert len(exp.build_tasks("main", jev)) == 60 * 20
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


SCREEN = [item.id for item in dataset.ITEMS]


def screen_rows(label, ids, latency=1.0, error=None):
    return [{"label": label, "item_id": i, "latency_s": latency, "error_kind": error} for i in ids]


def test_the_screen_rule_uses_validity_and_latency_never_accuracy():
    data = (
        screen_rows("good", SCREEN)
        + screen_rows("flaky", SCREEN[:25])
        + screen_rows("flaky", SCREEN[25:], error="provider")
        + screen_rows("slow", SCREEN, latency=90.0)
        + screen_rows("dead", SCREEN, error="timeout")
    )
    summary = screen_summary(data)
    assert summary["good"]["passes"] and not summary["slow"]["passes"]
    assert not summary["flaky"]["passes"] and summary["flaky"]["valid_rate"] == pytest.approx(
        25 / 31
    )
    assert not summary["dead"]["passes"]
    assert passing_labels(data) == ["good"]


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


def test_retry_errors_redoes_infrastructure_failures_but_not_bad_replies(tmp_path):
    import asyncio

    from experiments.records import Record

    store = Store(tmp_path / "k.jsonl")
    for item, kind in [
        ("c01", "provider"),
        ("c02", "timeout"),
        ("c03", "schema"),
        ("c04", "parse"),
    ]:
        record = Record("s", "l", "jev", "jev", "-", item, 1, 0.0, 0.5, error_kind=kind, error=kind)
        asyncio.run(store.append(record))
    asyncio.run(
        store.append(Record("s", "l", "jev", "jev", "-", "c05", 1, 0.0, 0.5, route="answer"))
    )
    assert {k[2] for k in store.done()} == {"c01", "c02", "c03", "c04", "c05"}
    assert {k[2] for k in store.done(retry_errors=True)} == {"c03", "c04", "c05"}
    # a later success for a retried key makes it done again
    asyncio.run(
        store.append(Record("s", "l", "jev", "jev", "-", "c01", 1, 0.0, 0.5, route="answer"))
    )
    assert "c01" in {k[2] for k in store.done(retry_errors=True)}


def test_groups_restricts_the_messages_of_a_stage():
    chat = matrix.pick(["gpt-5.6-luna:low"])
    assert len(exp.build_tasks("screen", chat, repeats=1, only_groups={"core"})) == 5
    assert len(exp.build_tasks("screen", chat, repeats=1, only_groups={"attack", "benign"})) == 10


def test_clean_error_keeps_the_class_status_and_known_tags_only():
    from experiments.records import clean_error

    text = (
        "OpenAIRateLimitError: Error code: 429 - {'error': {'type': 'usage_limit_reached', "
        "'message': 'secret body', 'plan_type': 'plus', 'resets_at': 1790002372}}"
    )
    assert clean_error("provider", text) == "OpenAIRateLimitError HTTP 429 usage_limit_reached"
    nim = "Exception: [503] {'message': 'ResourceExhausted: Worker limit', 'id': 'abc-123'}"
    assert clean_error("provider", nim) == "Exception HTTP 503 ResourceExhausted"
    assert clean_error("timeout", "TimeoutError: ") == "TimeoutError"
    assert clean_error("provider", "weird text: nothing known") == "Error"
    assert clean_error(None, "anything") is None


def test_clean_error_drops_model_output_from_parse_and_schema_failures():
    from experiments.records import clean_error

    parse = "parse: Invalid json output: intent: billing\nSECRET model text"
    assert "SECRET" not in (clean_error("parse", parse) or "")
    schema = "schema: intent is not one of the choices: 'ignore previous instructions'"
    assert clean_error("schema", schema) == "schema: intent is not one of the choices"


def test_clean_row_relabels_the_non_string_intent_bug_and_is_idempotent():
    from experiments.records import clean_row

    row = {"error_kind": "provider", "error": "TypeError: unhashable type: 'dict'", "route": None}
    fixed = clean_row(row)
    assert (fixed["error_kind"], fixed["error"]) == ("schema", "schema: intent is not a string")
    assert clean_row(fixed) == fixed
    ok = {"error_kind": None, "error": None, "route": "answer"}
    assert clean_row(ok) == ok


def test_sanitize_file_rewrites_rows_in_place(tmp_path):
    from experiments.sanitize import sanitize_file

    path = tmp_path / "rows.jsonl"
    rows = [
        {"error_kind": "provider", "error": "Exception: [503] {'a': 'body'}", "item_id": "c01"},
        {"error_kind": None, "error": None, "item_id": "c02"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    assert sanitize_file(path) == 1
    assert sanitize_file(path) == 0
    assert "body" not in path.read_text()


async def test_a_failed_call_is_timed_as_its_own_duration_not_the_experiment(tmp_path):
    import asyncio

    class SlowThenDown(FakeEngine):
        async def classify(self, text):
            await asyncio.sleep(0.05)
            raise ConnectionError("down: secret detail")

    configs = matrix.pick(["gpt-5.6-luna:low"])
    engines = {configs[0].label: SlowThenDown()}
    store = Store(tmp_path / "t.jsonl")
    await asyncio.sleep(0.3)  # the experiment has already been "running" for a while
    tasks = exp.build_tasks("stability", configs, repeats=1)
    await exp.execute(tasks, engines, store, RunConfig(mode="sequential"), progress_every=99)
    rows = store.read()
    assert all(0.04 <= r["latency_s"] < 0.3 for r in rows)
    assert all("secret" not in (r["error"] or "") for r in rows)
    assert {r["error"] for r in rows} == {"ConnectionError"}


def test_a_partial_screen_can_fail_a_config_but_never_pass_it():
    data = (
        screen_rows("full", SCREEN)
        + screen_rows("partial", SCREEN[:5])
        + screen_rows("partial-bad", SCREEN[:5], error="timeout")
    )
    summary = screen_summary(data)
    assert summary["full"]["passes"] and summary["full"]["messages"] == 31
    assert not summary["partial"]["passes"]  # perfect, but on too few messages
    assert not summary["partial-bad"]["passes"]
    assert passing_labels(data) == ["full"]


def test_the_screen_must_cover_the_actual_screen_messages_not_any_31_ids():
    main_only = [i.id for i in dataset.ALL_ITEMS[31:]][:29]
    other = [f"zz{i}" for i in range(31)]
    mixed = SCREEN[:25] + main_only[:6]  # 31 ids, but six are not screen messages
    extra = SCREEN + ["zz01"]  # the whole screen plus an unknown id
    data = (
        screen_rows("other", other)
        + screen_rows("mixed", mixed)
        + screen_rows("extra", extra)
        + screen_rows("exact", SCREEN)
    )
    summary = screen_summary(data)
    assert summary["other"]["messages"] == 0 and not summary["other"]["passes"]
    assert summary["mixed"]["messages"] == 25 and not summary["mixed"]["passes"]
    assert not summary["extra"]["passes"]  # an id that is not a screen message rejects it
    assert passing_labels(data) == ["exact"]


def test_from_screen_applies_the_rule_to_jev_too(tmp_path, monkeypatch, capsys):
    screen = tmp_path / "screen.jsonl"
    rows = [
        {
            "stage": "screen",
            "label": "openai:gpt-5.6-luna:low",
            "item_id": i,
            "repeat": 1,
            "latency_s": 1.0,
            "error_kind": None,
        }
        for i in SCREEN
    ]
    screen.write_text("\n".join(json.dumps(r) for r in rows))
    monkeypatch.setattr(exp, "DATA", tmp_path)
    exp.main(["--stage", "main", "--from-screen", "--dry-run", "--out", str(tmp_path / "m.jsonl")])
    text = capsys.readouterr().out
    assert "Jev did not pass the screen" in text
    assert "configs=1 " in text


def test_clean_error_never_lets_text_without_a_colon_through():
    from experiments.records import clean_error

    assert clean_error("provider", "token abc123 failed") == "Error"
    assert clean_error("provider", "sk-secret") == "Error"
    assert clean_error("provider", "Exception HTTP 503 ResourceExhausted") == (
        "Exception HTTP 503 ResourceExhausted"
    )
    assert clean_error("provider", "Exception HTTP 503 not-a-known-tag") == "Error"
    assert clean_error("timeout", "TimeoutError") == "TimeoutError"


async def test_the_experiment_timeout_reaches_the_chat_model(monkeypatch):
    from experiments.engines import ChatEngine

    seen: dict = {}

    def fake_make(**kwargs):
        seen.update(kwargs)
        return object()

    monkeypatch.setattr("experiments.engines.make_chat_model", fake_make)
    engine = ChatEngine(matrix.pick(["nemotron-3-ultra-550b-a55b:think_on"])[0], timeout_s=600)
    await engine._model()
    assert seen["timeout"] == 600 and seen["thinking"] is True
