"""Which engines, models, and reasoning settings the experiments compare.

`setting` names one reasoning setting of a model. For ChatGPT models it is the `reasoning_effort`.
For NIM reasoning models it is `think_off` or `think_on`, the `enable_thinking` switch. `default`
means the model has no switch that works: GLM-5.3-Flash ignored it in a probe, and the Kimi and
GLM-5.3 models were too slow to test settings.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Engine = Literal["jev", "openai", "nim"]

GPT_MODELS = ("gpt-6-astra", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
GPT_EFFORTS = ("low", "medium", "high")
NIM_SWITCHABLE = (
    "nvidia/nemotron-3.5-lightning-30b-a3b",
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
)
NIM_FIXED = ("z-ai/glm-5.3-flash", "z-ai/glm-5.3", "moonshotai/kimi-k3")


@dataclass(frozen=True)
class EngineConfig:
    engine: Engine
    model: str
    setting: str

    @property
    def label(self) -> str:
        return f"{self.engine}:{self.model}:{self.setting}"

    @property
    def thinking(self) -> bool | None:
        return {"think_on": True, "think_off": False}.get(self.setting)

    @property
    def reasoning_effort(self) -> str | None:
        return self.setting if self.engine == "openai" else None


JEV = EngineConfig("jev", "jev", "-")
ALL: list[EngineConfig] = [
    JEV,
    *(EngineConfig("openai", m, e) for m in GPT_MODELS for e in GPT_EFFORTS),
    *(EngineConfig("nim", m, s) for m in NIM_SWITCHABLE for s in ("think_off", "think_on")),
    *(EngineConfig("nim", m, "default") for m in NIM_FIXED),
]
BY_LABEL: dict[str, EngineConfig] = {c.label: c for c in ALL}
assert len(BY_LABEL) == len(ALL), "engine labels must be unique"


def pick(patterns: list[str] | None) -> list[EngineConfig]:
    """Configs whose label contains any pattern. No patterns means all of them."""
    if not patterns:
        return list(ALL)
    return [c for c in ALL if any(p in c.label for p in patterns)]
