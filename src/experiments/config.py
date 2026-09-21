"""Run settings: defaults, then `config.toml`, then environment variables, then explicit overrides.

    [run]
    mode = "parallel"      # or "sequential"
    window = 10            # tasks in flight in parallel mode
    timeout_s = 600        # one model call
    order = "shuffle"      # or "grouped": shuffle mixes providers so no one is hit all at once
    seed = 7

Environment: EXPERIMENT_MODE, EXPERIMENT_WINDOW, EXPERIMENT_TIMEOUT_S, EXPERIMENT_ORDER,
EXPERIMENT_SEED.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from experiments.runner import Mode, validate

HERE = Path(__file__).parent
DEFAULT_PATH = HERE / "config.toml"
ORDERS = ("shuffle", "grouped")
ENV_NAMES = {
    "mode": "EXPERIMENT_MODE",
    "window": "EXPERIMENT_WINDOW",
    "timeout_s": "EXPERIMENT_TIMEOUT_S",
    "order": "EXPERIMENT_ORDER",
    "seed": "EXPERIMENT_SEED",
}


@dataclass(frozen=True)
class RunConfig:
    mode: Mode = "parallel"
    window: int = 10
    timeout_s: float = 600.0
    order: Literal["shuffle", "grouped"] = "shuffle"
    seed: int = 7

    def __post_init__(self) -> None:
        validate(self.mode, self.window)
        if not self.timeout_s > 0:
            raise ValueError(f"timeout_s must be positive, got {self.timeout_s!r}")
        if self.order not in ORDERS:
            raise ValueError(f"order must be one of {ORDERS}, got {self.order!r}")

    @property
    def in_flight(self) -> int:
        """How many tasks run at the same time under these settings."""
        return 1 if self.mode == "sequential" else self.window


def _coerce(name: str, value: Any) -> Any:
    try:
        if name in ("window", "seed"):
            return int(value)
        if name == "timeout_s":
            return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} has an invalid value: {value!r}") from exc
    return str(value).strip().lower()


def load(
    path: Path | None = DEFAULT_PATH,
    env: Mapping[str, str] | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> RunConfig:
    """Merge the layers. Unknown keys in the file or in `overrides` are an error, not ignored."""
    values: dict[str, Any] = {}
    if path is not None and path.is_file():
        values.update(tomllib.loads(path.read_text(encoding="utf-8")).get("run", {}))
    env = os.environ if env is None else env
    for name, variable in ENV_NAMES.items():
        if env.get(variable):
            values[name] = env[variable]
    values.update({k: v for k, v in (overrides or {}).items() if v is not None})
    unknown = set(values) - set(ENV_NAMES)
    if unknown:
        raise ValueError(f"unknown run settings: {sorted(unknown)}")
    return replace(RunConfig(), **{k: _coerce(k, v) for k, v in values.items()})
