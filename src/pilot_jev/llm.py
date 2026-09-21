"""Inference layer: one factory, three backends in priority order.

Jev never writes text, so the reply itself still comes from a chat model. Pick where that model
runs with `LLM_PROVIDER`:

1. `openai`   ChatGPT subscription through Codex OAuth (`langchain-openai`, experimental). It does
              not use `OPENAI_API_KEY`. Sign in once with `python -m pilot_jev.chatgpt_login`.
2. `nim`      NVIDIA NIM through `langchain-nvidia-ai-endpoints` (hosted catalog or self-hosted)
3. `lmstudio` LM Studio's OpenAI-compatible server through `langchain-openai`

With `LLM_PROVIDER` unset, the first provider that is configured wins, in that order.
"""

from __future__ import annotations

import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_openai import ChatOpenAI
from langchain_openai.chatgpt_oauth import DEFAULT_STORE_PATH

from pilot_jev.env import env_is_set, load_env

PROVIDERS = ("openai", "nim", "lmstudio")  # priority order

DEFAULT_MODELS = {
    "openai": "gpt-5.5",
    "nim": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "lmstudio": "google/gemma-4-e4b",
}
DEFAULT_LMSTUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
# Hosted NIM calls took 6-160 s in testing, so the 60 s client default is too tight.
DEFAULT_TIMEOUT_SECONDS = 180.0


def chatgpt_store_path() -> Path:
    """Where `chatgpt_login` keeps the OAuth token. Deliberately not `~/.codex/auth.json`."""
    return DEFAULT_STORE_PATH


# Fields the OAuth helper needs to use or refresh a stored token. Values are never read out.
STORE_TOKEN_FIELDS = ("access_token", "refresh_token")

STORE_HINTS = {
    "missing": "no sign-in found",
    "empty": "the token file is empty",
    "malformed": "the token file is not valid JSON",
    "incomplete": "the token file lacks a usable access token, refresh token, or expiry",
}


def _usable_expiry(value: object) -> bool:
    """The helper reads `expires_at` as an ISO timestamp or as seconds since the epoch."""
    if isinstance(value, bool):
        return False
    try:
        if isinstance(value, str):
            datetime.fromisoformat(value)
            return True
        if isinstance(value, int | float) and math.isfinite(value):
            datetime.fromtimestamp(value, tz=UTC)
            return True
    except (ValueError, OverflowError, OSError):
        pass
    return False


def chatgpt_store_status() -> str:
    """`ok`, or why the stored sign-in is unusable: `missing`, `empty`, `malformed`, `incomplete`.

    Only the structure is checked, so no token value reaches an error message or a log.
    """
    path = chatgpt_store_path()
    if not path.is_file():
        return "missing"
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "malformed"
    if not raw.strip():
        return "empty"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "malformed"
    if not isinstance(data, dict):
        return "malformed"
    if not all(isinstance(data.get(f), str) and data[f].strip() for f in STORE_TOKEN_FIELDS):
        return "incomplete"
    return "ok" if _usable_expiry(data.get("expires_at")) else "incomplete"


def chatgpt_recovery_hint() -> str:
    """One line for a user whose ChatGPT sign-in is not usable. Safe to print."""
    status = chatgpt_store_status()
    why = STORE_HINTS.get(status)
    prefix = f"{why}. " if why else ""
    return prefix + "Run: uv run python -m pilot_jev.chatgpt_login"


def chatgpt_signed_in() -> bool:
    """A usable sign-in exists. It cannot see the usage limit: set LLM_PROVIDER if it is used up."""
    return chatgpt_store_status() == "ok"


def auto_provider() -> str:
    """First configured provider in priority order: ChatGPT sign-in, NVIDIA, then LM Studio."""
    load_env()
    if chatgpt_signed_in():
        return "openai"
    if env_is_set("NVIDIA_API_KEY") or os.getenv("NVIDIA_BASE_URL"):
        return "nim"
    return "lmstudio"


def provider_name() -> str:
    load_env()
    return (os.getenv("LLM_PROVIDER") or auto_provider()).strip().lower()


def model_name(provider: str | None = None) -> str:
    provider = provider or provider_name()
    return os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(provider, "")


def timeout_seconds() -> float:
    return float(os.getenv("LLM_TIMEOUT") or DEFAULT_TIMEOUT_SECONDS)


def thinking_setting() -> bool | None:
    """`LLM_ENABLE_THINKING` true/false for reasoning models. Unset leaves the model default."""
    raw = (os.getenv("LLM_ENABLE_THINKING") or "").strip().lower()
    if raw in ("1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return None


def lmstudio_base_url() -> str:
    return os.getenv("LMSTUDIO_BASE_URL") or DEFAULT_LMSTUDIO_BASE_URL


def make_chat_model(
    *,
    provider: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
    thinking: bool | None = None,
    timeout: float | None = None,
) -> BaseChatModel:
    """Build the chat model. The two optional arguments override the environment for one model:

    `reasoning_effort` (ChatGPT: low, medium, high, xhigh), `thinking` (NIM reasoning models: the
    `enable_thinking` switch), and `timeout` in seconds (instead of `LLM_TIMEOUT`). They let an
    experiment compare reasoning settings side by side under its own time limit.
    """
    provider = (provider or provider_name()).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {PROVIDERS}, got {provider!r}")
    model = model or model_name(provider)
    timeout = timeout if timeout is not None else timeout_seconds()

    if provider == "openai":
        if not chatgpt_signed_in():
            raise RuntimeError(f"Not signed in to ChatGPT: {chatgpt_recovery_hint()}")
        # Experimental and private in langchain-openai: it may change without notice.
        from langchain_openai.chat_models.codex import _ChatOpenAICodex

        # max_retries=0: pilot_jev.retry.with_retries is the only retry owner (see that module).
        codex_kwargs: dict = {"model": model, "timeout": timeout, "max_retries": 0}
        if reasoning_effort:
            codex_kwargs["reasoning_effort"] = reasoning_effort
        return _ChatOpenAICodex(**codex_kwargs)

    if provider == "nim":
        kwargs: dict = {"model": model, "timeout": timeout}
        if api_key := os.getenv("NVIDIA_API_KEY"):
            kwargs["api_key"] = api_key
        if base_url := os.getenv("NVIDIA_BASE_URL"):
            kwargs["base_url"] = base_url
        if thinking is None:
            thinking = thinking_setting()
        if thinking is not None:
            kwargs["model_kwargs"] = {"chat_template_kwargs": {"enable_thinking": thinking}}
        return ChatNVIDIA(**kwargs)

    return ChatOpenAI(
        model=model,
        base_url=lmstudio_base_url(),
        # LM Studio does not validate the key, but the OpenAI client insists on one.
        api_key=os.getenv("LMSTUDIO_API_KEY") or "lm-studio",
        timeout=timeout,
        max_retries=0,  # pilot_jev.retry.with_retries is the only retry owner
    )
