# AGENTS.md

Context for AI coding agents (Claude Code, Codex, Hermes, Copilot). Released as v0.1.0. The plan and
checklist that guided the work lived in `PLAN.md`, one item per commit and ticked only after the work
had run. It was removed at release and stays in git history (`git log -- PLAN.md`).

## Purpose

Pilot for TypeSafe AI's **Jev** (System One model) inside **LangGraph** and **Deep Agents**. Jev
returns typed judgments and probabilities, never text, so a chat model still writes replies. The
chat model runs on (1) a **ChatGPT subscription**, (2) **NVIDIA NIM**, or (3) **LM Studio**, chosen with
`LLM_PROVIDER` or, when unset, the first one that is configured.

## Structure

```
.claude/skills/            skills (real files); .agents is a symlink to .claude
  typesafe-ai/             TypeSafe skill, read it before writing Jev code
  centered-readme/         README hero block style
  git-commit-helper/       commit message policy
  python-lint/             ruff, ty, pytest before any Python change is done
  make-pilot-agent-project/  recipe that produced this repo
docs/                      guides with Mermaid diagrams, EN plus -ko/-ja/-zh-CN twins; docs/images/ has the TypeSafe logos
temp/                      gitignored private notes, never publish or commit
src/                       uv app, Python 3.13
  pilot_jev/               shared code: env, jev gateway, llm factory, chatgpt_login, chatgpt_models, retry, text, triage
  case01_routing/          Jev as a LangGraph router
  case02_deepagents/       Jev as guardrail middleware and verify tool in a Deep Agent
  notebooks/               executed verification notebooks, plus -ko twins and ko.json
  tests/                   offline pytest suite
  doctor.py                environment and connectivity diagnostics
  sync_notebooks_ko.py     rebuilds the -ko notebooks from the English ones
  langgraph.json           graphs for `langgraph dev`
```

## Commands (run in `src/`)

```bash
uv sync                                  # add --extra notebook --extra studio as needed
uv run python doctor.py                  # env, Jev, chat model
uv run pytest                            # offline unit tests
uv run ruff check --fix . && uv run ruff format . && uv run ty check .   # python-lint skill
uv run python -m case01_routing.main
uv run python -m case02_deepagents.main
uv run langgraph dev                     # needs --extra studio
uv run python sync_notebooks_ko.py       # after re-running an English notebook
```

## Environment (`.env` at the repo root, template in `.env.sample`)

| Variable | Required | Notes |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | yes | https://console.typesafe.ai/keys |
| `LLM_PROVIDER` | no | (1) `openai`, (2) `nim`, (3) `lmstudio`. Unset picks the first configured |
| `LLM_MODEL` | no | defaults: `gpt-5.5` (openai), `nvidia/nemotron-3.5-lightning-30b-a3b` (nim), `google/gemma-4-e4b` (lmstudio) |
| `LLM_TIMEOUT` | no | seconds, default 180. Hosted NIM calls took 20 to 157 s |
| `LLM_ENABLE_THINKING` | no | `false` sends `enable_thinking: false` to NIM reasoning models. Unset keeps the model default. Recommended `false` |
| `NVIDIA_API_KEY` | nim | https://build.nvidia.com. Also stored in the macOS keychain |
| `NVIDIA_BASE_URL` | no | self-hosted NIM |
| `LMSTUDIO_BASE_URL` | no | default `http://127.0.0.1:1234/v1` |
| `JEV_MODEL` | no | default `jev-latest` |

Read the key from the keychain without printing it:
`NVIDIA_API_KEY="$(security find-generic-password -s 'NVIDIA API Key' -a pilot-typesafeai-jev -w)" uv run ...`

## Conventions

- Source code, comments, `AGENTS.md`, and `docs/` are English. `README.md`
  and each `docs/` page have translated twins, always in this order: English (default), Korean
  (`-ko`), Japanese (`-ja`), Simplified Chinese (`-zh-CN`). Edit English first, then the twins.
- Keep the README short and visual. Put detail and Mermaid diagrams in `docs/`.
- Follow the TypeSafe skill: read the live docs at https://docs.typesafe.ai/llms.txt before writing
  Jev code, ask independent questions in one request, keep policy in code, and treat thresholds as
  starting points to evaluate.
- The Korean notebooks are generated: never edit them by hand. Code and results come from the English
  notebook, Korean Markdown from `src/notebooks/ko.json`. Run `sync_notebooks_ko.py` after changes.
- Every Jev call goes through the `pilot_jev.jev.Gateway` protocol (implemented by `Jev`) so tests can
  swap in a fake. Code and tests must pass `ruff check --fix`, `ruff format`, `ty check`, and `pytest`
  (`python-lint` skill). Suppress a finding only with the exact rule and a reason.
- Model names are account specific. Find them with `python -m pilot_jev.chatgpt_models`, and keep
  account-specific names out of public docs.
- The `openai` provider uses ChatGPT OAuth, never `OPENAI_API_KEY`. It is experimental and unofficial,
  so keep the terms warning. Never read or copy `~/.codex/auth.json`; the token store is
  `~/.langchain/chatgpt-auth.json`.
- The NIM package is `langchain-nvidia-ai-endpoints` (`ChatNVIDIA`). There is no `langchain-nvidia-nim`.
- A model listed in the NIM catalog can still return `410 Gone`. Call it before relying on it.
- The `.env` file is gitignored. Never print, log, or commit key values.
- Commits follow `.claude/skills/git-commit-helper/SKILL.md`. Keep one meaningful piece of work per commit.
  Never commit or push without explicit approval, and never put session IDs, session URLs, or co-author trailers in a commit.
