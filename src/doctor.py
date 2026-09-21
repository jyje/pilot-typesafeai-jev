"""Diagnostics: environment, Jev connectivity, and the chat-model backend.

Usage: uv run python doctor.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

from langchain_core.messages import HumanMessage
from typesafe_sdk import Noul

from pilot_jev.env import env_is_set, load_env
from pilot_jev.jev import Jev
from pilot_jev.llm import (
    PROVIDERS,
    chatgpt_recovery_hint,
    chatgpt_signed_in,
    chatgpt_store_path,
    lmstudio_base_url,
    make_chat_model,
    model_name,
    provider_name,
)

load_env()
# Keep LangSmith out of diagnostics runs.
os.environ["LANGSMITH_TRACING"] = "false"

PASS, FAIL, SKIP = "  [PASS]", "  [FAIL]", "  [SKIP]"
SEP = "-" * 52


def section(title: str) -> None:
    print(f"\n{SEP}\n {title}\n{SEP}")


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"{PASS if ok else FAIL} {label}" + (f"\n         {detail}" if detail else ""))
    return ok


def skip(label: str, why: str) -> None:
    print(f"{SKIP} {label}\n         {why}")


def is_set(name: str) -> bool:
    return env_is_set(name)


def env_section(provider: str) -> bool:
    section("1. Environment")
    ok = check("TYPESAFE_API_KEY is set", is_set("TYPESAFE_API_KEY"), "value hidden")
    ok &= check(
        f"LLM_PROVIDER is one of {PROVIDERS}",
        provider in PROVIDERS,
        f"value: {provider}" + ("" if os.getenv("LLM_PROVIDER") else " (auto: first configured)"),
    )
    if provider == "openai":
        ok &= check(
            "Signed in to ChatGPT (no OPENAI_API_KEY needed)",
            chatgpt_signed_in(),
            str(chatgpt_store_path()) if chatgpt_signed_in() else chatgpt_recovery_hint(),
        )
    elif provider == "nim":
        hosted = is_set("NVIDIA_API_KEY")
        self_hosted = bool(os.getenv("NVIDIA_BASE_URL"))
        ok &= check(
            "NVIDIA_API_KEY (hosted catalog) or NVIDIA_BASE_URL (self-hosted NIM)",
            hosted or self_hosted,
            "hosted: key set" if hosted else f"self-hosted: {os.getenv('NVIDIA_BASE_URL')}",
        )
    elif provider == "lmstudio":
        check("LMSTUDIO_BASE_URL", True, lmstudio_base_url())
    check("LLM_MODEL", True, model_name(provider) if provider in PROVIDERS else "n/a")
    return ok


def jev_section() -> bool:
    section("2. Jev (TypeSafe System One)")
    if not is_set("TYPESAFE_API_KEY"):
        skip("Noul question", "TYPESAFE_API_KEY is not set")
        return True
    jev = Jev()
    try:
        response = jev.ask(
            "Hi, my integration has been failing for 3 days. Please help ASAP.",
            {"urgent": Noul(instructions="The message conveys urgency or time-sensitivity")},
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics report every failure kind
        return check("Noul question", False, f"{type(exc).__name__}: {exc}")
    p = response.nouls["urgent"].noul
    return check("Noul question", 0.0 <= p <= 1.0, f"model={response.model}  P(urgent)={p:.2f}")


def lmstudio_reachable() -> bool:
    url = lmstudio_base_url().rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            ids = [m["id"] for m in json.load(resp).get("data", [])]
    except (OSError, ValueError, KeyError, AttributeError) as exc:
        return check("LM Studio server reachable", False, f"{url}: {exc}")
    wanted = model_name("lmstudio")
    return check(
        "LM Studio server reachable",
        True,
        f"{len(ids)} model(s) listed; '{wanted}' "
        + ("is available" if wanted in ids else "is NOT listed (load it in LM Studio)"),
    )


def llm_section(provider: str) -> bool:
    section("3. Chat model backend")
    if provider not in PROVIDERS:
        skip("Basic inference", "invalid LLM_PROVIDER")
        return True
    if provider == "openai" and not chatgpt_signed_in():
        skip("Basic inference", "not signed in to ChatGPT")
        return True
    if provider == "nim" and not (is_set("NVIDIA_API_KEY") or os.getenv("NVIDIA_BASE_URL")):
        skip("Basic inference", "no NVIDIA_API_KEY or NVIDIA_BASE_URL")
        return True
    if provider == "lmstudio" and not lmstudio_reachable():
        return False
    try:
        reply = make_chat_model().invoke([HumanMessage("Reply with the single word: ok")])
    except Exception as exc:  # noqa: BLE001
        return check("Basic inference", False, f"{type(exc).__name__}: {exc}")
    return check("Basic inference", bool(reply.text), f"reply: {reply.text.strip()[:60]!r}")


def main() -> int:
    provider = provider_name()
    results = [env_section(provider), jev_section(), llm_section(provider)]
    print(f"\n{SEP}\n {'All checks passed' if all(results) else 'Some checks failed'}\n{SEP}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
