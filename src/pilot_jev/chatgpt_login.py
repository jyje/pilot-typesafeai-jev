"""Sign in to ChatGPT once so the `openai` provider can use your subscription.

Usage:
    uv run python -m pilot_jev.chatgpt_login            # opens a browser (recommended)
    uv run python -m pilot_jev.chatgpt_login --device   # headless device-code flow, see below

The browser flow listens on http://localhost:1455 for the sign-in callback and waits 15 minutes.
The device-code flow is currently broken in langchain-openai 1.6.2: OpenAI answers HTTP 400
because the library sends a form-encoded body where the endpoint now wants JSON. Use the browser
flow, or try `--device` again after upgrading langchain-openai.

The token is stored at ~/.langchain/chatgpt-auth.json (mode 0600), separate from the Codex CLI
session in ~/.codex/auth.json, and refreshed automatically. Nothing is written to this repo.

This uses langchain-openai's experimental, unofficial ChatGPT OAuth helpers. Use it only where your
OpenAI account, plan, and the applicable OpenAI terms allow ChatGPT-authenticated Codex access.
"""

from __future__ import annotations

import sys

from langchain_openai.chatgpt_oauth import login_chatgpt, login_chatgpt_device

from pilot_jev.llm import chatgpt_store_path

SIGN_IN_TIMEOUT_SECONDS = 900.0

NOTICE = (
    "This signs in to your ChatGPT subscription through an experimental, unofficial integration.\n"
    "Use it only where your OpenAI account, plan, and terms permit ChatGPT-authenticated Codex use."
)


def main(argv: list[str]) -> int:
    print(NOTICE)
    if "--device" in argv:
        login_chatgpt_device()
    else:
        login_chatgpt(timeout=SIGN_IN_TIMEOUT_SECONDS)
    print(f"\nSigned in. Token stored at {chatgpt_store_path()}")
    print("Check it with: uv run python doctor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
