import json
from typing import cast

import pytest

from pilot_jev import llm
from pilot_jev.llm import chatgpt_signed_in as real_chatgpt_signed_in


class Recorder:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


def kwargs_of(model) -> dict:
    """The factory returns a chat model type; the tests replace it with `Recorder`."""
    return cast(Recorder, model).kwargs


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_TIMEOUT",
        "LLM_ENABLE_THINKING",
        "NVIDIA_API_KEY",
        "NVIDIA_BASE_URL",
        "LMSTUDIO_BASE_URL",
        "LMSTUDIO_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "load_env", lambda: None)
    monkeypatch.setattr(llm, "chatgpt_signed_in", lambda: False)
    monkeypatch.setattr(llm, "ChatNVIDIA", Recorder)
    monkeypatch.setattr(llm, "ChatOpenAI", Recorder)


def test_nim_is_chosen_automatically_when_a_key_is_set(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    model = llm.make_chat_model()
    assert isinstance(model, Recorder)
    assert kwargs_of(model) == {
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "timeout": 180.0,
        "api_key": "nvapi-test",
    }


def test_nim_passes_key_and_self_hosted_base_url(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nim")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    monkeypatch.setenv("NVIDIA_BASE_URL", "http://0.0.0.0:8000/v1")
    assert kwargs_of(llm.make_chat_model()) == {
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "timeout": 180.0,
        "api_key": "nvapi-test",
        "base_url": "http://0.0.0.0:8000/v1",
    }


def test_lmstudio_uses_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    kwargs = kwargs_of(llm.make_chat_model())
    assert kwargs["base_url"] == "http://127.0.0.1:1234/v1"
    assert kwargs["api_key"] == "lm-studio"
    assert kwargs["model"] == "google/gemma-4-e4b"
    assert kwargs["max_retries"] == 0  # pilot_jev.retry is the only retry owner


def test_model_env_overrides_the_provider_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3-8b")
    assert kwargs_of(llm.make_chat_model())["model"] == "qwen/qwen3-8b"


def test_unknown_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        llm.make_chat_model()


def test_timeout_is_configurable(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("LLM_TIMEOUT", "30")
    assert kwargs_of(llm.make_chat_model())["timeout"] == 30.0


def test_thinking_off_is_sent_to_nim_only_when_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nim")
    assert "model_kwargs" not in kwargs_of(llm.make_chat_model())
    monkeypatch.setenv("LLM_ENABLE_THINKING", "false")
    assert kwargs_of(llm.make_chat_model())["model_kwargs"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_empty_provider_falls_back_to_the_automatic_choice(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    assert llm.provider_name() == "nim"


def test_model_name_does_not_crash_on_an_unknown_provider(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    assert llm.model_name("ollama") == ""


def test_auto_provider_follows_the_priority_order(monkeypatch):
    assert llm.auto_provider() == "lmstudio"
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    assert llm.auto_provider() == "nim"
    monkeypatch.setattr(llm, "chatgpt_signed_in", lambda: True)
    assert llm.auto_provider() == "openai"


def test_explicit_provider_beats_the_automatic_choice(monkeypatch):
    monkeypatch.setattr(llm, "chatgpt_signed_in", lambda: True)
    monkeypatch.setenv("LLM_PROVIDER", "lmstudio")
    assert llm.provider_name() == "lmstudio"


def test_openai_requires_a_chatgpt_sign_in():
    with pytest.raises(RuntimeError, match="chatgpt_login"):
        llm.make_chat_model(provider="openai")


def test_openai_uses_the_codex_oauth_model_without_an_api_key(monkeypatch):
    from langchain_openai.chat_models import codex

    monkeypatch.setattr(llm, "chatgpt_signed_in", lambda: True)
    monkeypatch.setattr(codex, "_ChatOpenAICodex", Recorder)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    model = llm.make_chat_model(provider="openai")
    assert kwargs_of(model) == {"model": "gpt-5.5", "timeout": 180.0, "max_retries": 0}


def test_provider_priority_order_is_openai_nim_lmstudio():
    assert llm.PROVIDERS == ("openai", "nim", "lmstudio")


def test_chatgpt_models_are_reduced_to_id_name_and_visibility():
    from pilot_jev.chatgpt_models import parse_models

    payload = {
        "models": [
            {"slug": "model-a", "display_name": "Model A", "visibility": "list", "extra": 1},
            {"id": "model-b"},
            "not a dict",
        ]
    }
    assert parse_models(payload) == [
        {"id": "model-a", "name": "Model A", "visibility": "list"},
        {"id": "model-b", "name": "", "visibility": ""},
    ]


def test_a_placeholder_nvidia_key_does_not_count_as_configured(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    assert llm.auto_provider() == "lmstudio"
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-a-real-looking-key")
    assert llm.auto_provider() == "nim"


VALID_STORE = {
    "access_token": "secret-access",
    "refresh_token": "secret-refresh",
    "expires_at": "2030-01-01T00:00:00+00:00",
    "account_id": None,
}


@pytest.fixture
def store(tmp_path, monkeypatch):
    token = tmp_path / "chatgpt-auth.json"
    monkeypatch.setattr(llm, "chatgpt_store_path", lambda: token)
    return token


def test_a_missing_or_empty_token_file_is_not_a_sign_in(store):
    assert llm.chatgpt_store_status() == "missing"
    store.write_text("")
    assert llm.chatgpt_store_status() == "empty"
    store.write_text("  \n")
    assert llm.chatgpt_store_status() == "empty"
    assert real_chatgpt_signed_in() is False


@pytest.mark.parametrize("text", ["{not json", '["a"]', '"a string"', "null", '{"access_token": '])
def test_a_malformed_token_file_is_not_a_sign_in(store, text):
    store.write_text(text)
    assert llm.chatgpt_store_status() == "malformed"
    assert real_chatgpt_signed_in() is False


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"access_token": ""},
        {"access_token": None},
        {"refresh_token": 5},
        {"expires_at": None},
        {"expires_at": True},
        {"expires_at": "not-a-date"},
        {"expires_at": ""},
        {"expires_at": 1e30},
        {"expires_at": float("nan")},
        {"expires_at": float("inf")},
    ],
)
def test_a_structurally_incomplete_store_is_rejected(store, patch):
    data = {**VALID_STORE, **patch} if patch else {}
    store.write_text(json.dumps(data))  # NaN and inf serialize as bare tokens Python reads back
    assert llm.chatgpt_store_status() == "incomplete"
    assert real_chatgpt_signed_in() is False


@pytest.mark.parametrize("expires_at", ["2030-01-01T00:00:00+00:00", 1893456000, 1893456000.5])
def test_a_valid_store_is_accepted(store, expires_at):
    store.write_text(json.dumps({**VALID_STORE, "expires_at": expires_at}))
    assert llm.chatgpt_store_status() == "ok"
    assert real_chatgpt_signed_in() is True


@pytest.mark.parametrize("expires_at", ["not-a-date", 1e30])
def test_an_unparseable_expiry_falls_back_to_nim_in_auto_mode(store, monkeypatch, expires_at):
    monkeypatch.setattr(llm, "chatgpt_signed_in", real_chatgpt_signed_in)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    store.write_text(json.dumps({**VALID_STORE, "expires_at": expires_at}))
    assert llm.provider_name() == "nim"


def test_a_corrupt_store_falls_back_to_nim_in_auto_mode(store, monkeypatch):
    monkeypatch.setattr(llm, "chatgpt_signed_in", real_chatgpt_signed_in)
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test")
    store.write_text("{truncated")
    assert llm.provider_name() == "nim"
    store.write_text(json.dumps(VALID_STORE))
    assert llm.provider_name() == "openai"


def test_the_error_and_hint_explain_the_problem_without_token_values(store):
    store.write_text(json.dumps({**VALID_STORE, "refresh_token": ""}))
    with pytest.raises(RuntimeError, match="chatgpt_login") as caught:
        llm.make_chat_model(provider="openai")
    text = f"{caught.value} {llm.chatgpt_recovery_hint()}"
    assert "refresh token" in text
    assert "secret-access" not in text
    store.write_text(json.dumps(VALID_STORE))
    assert llm.chatgpt_recovery_hint().startswith("Run:")
