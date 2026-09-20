# Getting started

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (it installs Python 3.13 for you)
- A TypeSafe API key: https://console.typesafe.ai/keys
- One chat model backend, in priority order: a ChatGPT subscription, an NVIDIA key from
  https://build.nvidia.com, or LM Studio running locally

## Setup

```bash
cp .env.sample .env      # fill in TYPESAFE_API_KEY, and NVIDIA_API_KEY for NIM
cd src
uv sync

# Only for the OpenAI subscription provider, once:
uv run python -m pilot_jev.chatgpt_login
```

`.env` lives at the repo root and is gitignored. `.env.sample` shows the format with placeholders.

## Environment

| Variable | Required | Notes |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | yes | read by the TypeSafe SDK |
| `LLM_PROVIDER` | no | `openai`, `nim`, or `lmstudio`. Unset picks the first configured, in that order |
| `LLM_MODEL` | no | defaults: `gpt-5.5` (openai), `nvidia/nemotron-3.5-lightning-30b-a3b` (nim), `google/gemma-4-e4b` (lmstudio) |
| `LLM_TIMEOUT` | no | seconds, default 180 |
| `LLM_ENABLE_THINKING` | no | `false` turns thinking off for NIM reasoning models |
| `NVIDIA_API_KEY` | nim | hosted catalog |
| `NVIDIA_BASE_URL` | no | self-hosted NIM |
| `LMSTUDIO_BASE_URL` | no | default `http://127.0.0.1:1234/v1` |
| `JEV_MODEL` | no | default `jev-latest` |

## Run it

Commands run from `src/`.

```bash
uv run python doctor.py                    # keys, Jev, chat model
uv run python -m case01_routing.main       # five sample messages
uv run python -m case01_routing.main "Where is my invoice?"     # your own message
uv run python -m case02_deepagents.main    # a clean request and an injection attempt
uv run pytest                              # offline unit tests
uv run ruff check . && uv run ruff format --check .
```

Switch the chat model per command without editing `.env`:

```bash
LLM_PROVIDER=lmstudio uv run python -m case01_routing.main
```

## Notebooks

```bash
uv sync --extra notebook
uv run jupyter lab notebooks/
```

`notebooks/01-case01-routing.ipynb` and `notebooks/02-case02-deepagents.ipynb` run each case
against the live services. Run them one at a time: hosted NIM slows down under concurrent load.
To execute one headless and keep its outputs:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01-case01-routing.ipynb
```

## LangGraph Studio

```bash
uv sync --extra studio
uv run langgraph dev --no-browser
```

`langgraph.json` registers two graphs: `routing` (Case 01) and `deepagent` (Case 02). The server
reads `../.env`.

## Using coding agents

Skills live in `.claude/skills/`. `.agents` is a symlink to `.claude`, so Claude Code, Codex,
Hermes, and Copilot see the same skills. Read the `typesafe-ai` skill before writing code that
calls Jev.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `Not signed in to ChatGPT` | run `uv run python -m pilot_jev.chatgpt_login` once |
| `doctor.py`: `TYPESAFE_API_KEY` not set | put it in the repo-root `.env`, not in `src/` |
| `410 Gone` from NIM | the model reached end of life. Pick another with `LLM_MODEL` |
| `403 Forbidden` from NIM | the key cannot run inference. Create a new key at build.nvidia.com |
| `ReadTimeout` or `SocketTimeoutError` | hosted latency. Raise `LLM_TIMEOUT` (for example 600) |
| Reply starts with `Here's a thinking process` | set `LLM_ENABLE_THINKING=false` |
| LM Studio `n_keep >= n_ctx` | load the model with a context length of at least 16384 |
| LM Studio model not listed | load it: `lms load <model> --context-length 32768` |
