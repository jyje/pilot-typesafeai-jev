"""Sign in to ChatGPT once so the `openai` provider can use your subscription.

Usage:
    uv run python -m pilot_jev.chatgpt_login            # opens a browser
    uv run python -m pilot_jev.chatgpt_login --device   # headless device-code flow

The token is stored at ~/.langchain/chatgpt-auth.json (mode 0600), separate from the Codex CLI
session in ~/.codex/auth.json, and refreshed automatically. Nothing is written to this repo.

This uses langchain-openai's experimental, unofficial ChatGPT OAuth helpers. Use it only where your
OpenAI account, plan, and the applicable OpenAI terms allow ChatGPT-authenticated Codex access.
"""

from __future__ import annotations

import sys

from langchain_openai.chatgpt_oauth import login_chatgpt, login_chatgpt_device

from pilot_jev.llm import chatgpt_store_path

NOTICE = (
    "This signs in to your ChatGPT subscription through an experimental, unofficial integration.\n"
    "Use it only where your OpenAI account, plan, and terms permit ChatGPT-authenticated Codex use."
)


def main(argv: list[str]) -> int:
    print(NOTICE)
    (login_chatgpt_device if "--device" in argv else login_chatgpt)()
    print(f"\nSigned in. Token stored at {chatgpt_store_path()}")
    print("Check it with: uv run python doctor.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
