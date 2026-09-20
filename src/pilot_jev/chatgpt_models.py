"""List the models your ChatGPT sign-in can use with the Codex backend.

Usage:
    uv run python -m pilot_jev.chatgpt_models

Model names differ per account and plan, and a name that exists can still be rejected for a
ChatGPT account (HTTP 400) or be out of quota (HTTP 429). Run this to see what is on offer, then set
LLM_MODEL. Only model IDs are printed, never the token.
"""

from __future__ import annotations

import sys

import httpx

from pilot_jev.llm import chatgpt_signed_in, make_chat_model

MODELS_URL = "https://chatgpt.com/backend-api/codex/models"
# The endpoint wants a client version. Any plausible value works.
CLIENT_VERSION = "1.0.0"


def parse_models(payload: dict) -> list[dict[str, str]]:
    """Reduce the response to id, display name, and whether the account lists it."""
    return [
        {
            "id": item.get("slug") or item.get("id") or "",
            "name": item.get("display_name") or "",
            "visibility": item.get("visibility") or "",
        }
        for item in payload.get("models", [])
        if isinstance(item, dict)
    ]


def list_models() -> list[dict[str, str]]:
    # Uses the experimental model's private header helper, like the rest of the openai provider.
    model = make_chat_model(provider="openai")
    headers = {
        "Authorization": f"Bearer {model.token_provider.get_access_token()}",
        **model._codex_headers_sync(),
        "Accept": "application/json",
    }
    response = httpx.get(
        MODELS_URL, params={"client_version": CLIENT_VERSION}, headers=headers, timeout=30
    )
    response.raise_for_status()
    return parse_models(response.json())


def main() -> int:
    if not chatgpt_signed_in():
        print("Not signed in to ChatGPT. Run: uv run python -m pilot_jev.chatgpt_login")
        return 1
    for item in list_models():
        hidden = "  (hidden in the app)" if item["visibility"] == "hide" else ""
        print(f"{item['id']:28} {item['name']}{hidden}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
