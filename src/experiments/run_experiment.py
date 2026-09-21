"""Collect the data: run every (config, message, repeat) and append one JSONL row each.

    uv run python -m experiments.run_experiment --stage screen --dry-run
    uv run python -m experiments.run_experiment --stage screen
    uv run python -m experiments.run_experiment --stage screen --mode sequential
    uv run python -m experiments.run_experiment --stage main --from-screen

The run mode and window come from experiments/config.toml (default: parallel, window 10) and can be
overridden with --mode and --window. A stopped run resumes: rows that already succeeded are skipped
(add --retry-errors to redo the failed ones).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from experiments import config as run_config
from experiments import dataset, matrix
from experiments.engines import Engine, make_engine
from experiments.matrix import EngineConfig
from experiments.records import Key, Record, Store
from experiments.runner import MODES, run_tasks
from experiments.selection import passing_labels
from pilot_jev.env import load_env
from pilot_jev.triage import decide

DATA = Path(__file__).parent / "data"

# stage: (message groups or None for all, repeats for chat models, repeats for Jev)
STAGES: dict[str, tuple[set[dataset.Group] | None, int, int]] = {
    "screen": (None, 3, 3),
    "main": (None, 5, 20),
    "stability": ({"core"}, 10, 10),
}


@dataclass(frozen=True)
class Task:
    stage: str
    config: EngineConfig
    item: dataset.Item
    repeat: int

    @property
    def key(self) -> Key:
        return (self.stage, self.config.label, self.item.id, self.repeat)


def build_tasks(
    stage: str, configs: Sequence[EngineConfig], *, repeats: int | None = None
) -> list[Task]:
    groups, chat_repeats, jev_repeats = STAGES[stage]
    items = dataset.select(groups)
    tasks = []
    for cfg in configs:
        n = repeats or (jev_repeats if cfg.engine == "jev" else chat_repeats)
        tasks += [Task(stage, cfg, item, r) for item in items for r in range(1, n + 1)]
    return tasks


def order(tasks: list[Task], how: str, seed: int) -> list[Task]:
    if how == "shuffle":
        tasks = list(tasks)
        random.Random(seed).shuffle(tasks)
    return tasks


def classify_error(exc: BaseException) -> str:
    return "timeout" if isinstance(exc, TimeoutError) else "provider"


async def execute(
    tasks: list[Task],
    engines: Mapping[str, Engine],
    store: Store,
    cfg: run_config.RunConfig,
    *,
    progress_every: int = 25,
) -> Counter:
    counts: Counter = Counter()
    total = len(tasks)
    started = time.time()

    async def worker(task: Task) -> Record:
        began = time.time()
        outcome = await engines[task.config.label].classify(task.item.text)
        record = Record(
            stage=task.stage,
            label=task.config.label,
            engine=task.config.engine,
            model=task.config.model,
            setting=task.config.setting,
            item_id=task.item.id,
            repeat=task.repeat,
            started_at=began,
            latency_s=round(time.time() - began, 3),
            input_tokens=outcome.input_tokens,
            output_tokens=outcome.output_tokens,
            reasoning_tokens=outcome.reasoning_tokens,
        )
        if outcome.triage is None:
            record.error_kind, record.error = (
                (outcome.error or "schema: ").split(":", 1)[0],
                outcome.error,
            )
            return record
        t = outcome.triage
        record.intent, record.intent_confidence = t.intent, t.intent_confidence
        record.urgency, record.injection, record.route = t.urgency, t.injection, decide(t)
        return record

    async def on_result(task: Task, outcome: Record | BaseException) -> None:
        if isinstance(outcome, BaseException):
            outcome = Record(
                stage=task.stage,
                label=task.config.label,
                engine=task.config.engine,
                model=task.config.model,
                setting=task.config.setting,
                item_id=task.item.id,
                repeat=task.repeat,
                started_at=started,
                latency_s=round(time.time() - started, 3),
                error_kind=classify_error(outcome),
                error=f"{type(outcome).__name__}: {outcome}"[:200],
            )
        await store.append(outcome)
        counts["ok" if outcome.ok else outcome.error_kind or "error"] += 1
        finished = sum(counts.values())
        if finished % progress_every == 0 or finished == total:
            print(f"  {finished}/{total}  {dict(counts)}  {time.time() - started:.0f}s", flush=True)

    await run_tasks(tasks, worker, mode=cfg.mode, window=cfg.window, on_result=on_result)
    return counts


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--stage", choices=list(STAGES), required=True)
    p.add_argument("--only", nargs="*", help="run configs whose label contains any of these")
    p.add_argument("--from-screen", action="store_true", help="main stage: passing configs only")
    p.add_argument("--repeats", type=int, help="override the repeats of the stage")
    p.add_argument("--mode", choices=list(MODES))
    p.add_argument("--window", type=int)
    p.add_argument("--retry-errors", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", type=Path, help="JSONL path (default: data/<stage>.jsonl)")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    load_env()
    cfg = run_config.load(overrides={"mode": args.mode, "window": args.window})
    store = Store(args.out or DATA / f"{args.stage}.jsonl")
    configs = matrix.pick(args.only)
    if args.from_screen:
        keep = set(passing_labels(Store(DATA / "screen.jsonl").read())) | {matrix.JEV.label}
        configs = [c for c in configs if c.label in keep]
    tasks = build_tasks(args.stage, configs, repeats=args.repeats)
    done = store.done(retry_errors=args.retry_errors)
    todo = order([t for t in tasks if t.key not in done], cfg.order, cfg.seed)
    print(
        f"stage={args.stage} mode={cfg.mode} window={cfg.window} (in flight: {cfg.in_flight}) "
        f"configs={len(configs)} tasks={len(tasks)} todo={len(todo)} -> {store.path}"
    )
    if args.dry_run or not todo:
        return 0
    engines = {c.label: make_engine(c, timeout_s=cfg.timeout_s) for c in configs}
    counts = asyncio.run(execute(todo, engines, store, cfg))
    print(f"finished: {dict(counts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
