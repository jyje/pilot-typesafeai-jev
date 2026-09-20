# Plan: pilot-typesafeai-jev

This file is the single source of truth for scope and progress. **When every box below is checked,
v0.1 is ready to publish.**

## Goal

Show how TypeSafe AI's **Jev** (a System One model) fits into **LangGraph** and **Deep Agents**, and
document what actually happens when it does. Jev returns typed judgments and calibrated
probabilities, never generated text, so code owns the workflow and a chat model still writes the
replies. The chat model runs on a **ChatGPT subscription** (1), **NVIDIA NIM** (2), or **LM Studio** (3).

## How to use this checklist

- One checklist item is one meaningful piece of work and **one commit**. The commit title is in
  backticks after each item.
- Tick an item only after the work has run and been verified.
- New work that turns up gets a new item. Work finished before it had an item is added afterwards.
- Commits and pushes happen only after explicit approval, following
  `.claude/skills/git-commit-helper/SKILL.md`. Never add session IDs, session URLs, or co-author
  trailers.

## Decisions

| Topic | Decision |
| --- | --- |
| Python | 3.13. 3.14 hit a `tokenizers` wheel gap in a sibling pilot |
| Jev access | `typesafe-sdk`, key in `TYPESAFE_API_KEY`, model `jev-latest` |
| Inference layer | One factory, `LLM_PROVIDER=openai` (1), `nim` (2), or `lmstudio` (3). Unset picks the first configured, in that order |
| ChatGPT subscription | `langchain-openai` experimental `_ChatOpenAICodex` with ChatGPT OAuth. No `OPENAI_API_KEY`. Token in `~/.langchain/chatgpt-auth.json`, never `~/.codex/auth.json`. Unofficial, so the terms warning stays in the docs |
| NVIDIA NIM | `langchain-nvidia-ai-endpoints` (`ChatNVIDIA`). There is no `langchain-nvidia-nim` package |
| LM Studio | OpenAI-compatible route through `langchain-openai`, base URL `/v1` |
| Layout | Flat uv app in `src/`, shared code in `src/pilot_jev/`, one folder per case |
| Skills | Real files in `.claude/skills/`. `.agents` is a symlink so Codex, Hermes, and Copilot see them |
| Private notes | `temp/` is gitignored and accumulates reference analysis. Never published |
| Docs | README short and visual. Detail in `docs/` with Mermaid diagrams. English, then Korean (`-ko`), Japanese (`-ja`), Simplified Chinese (`-zh-CN`), always in that order |
| Secrets | Repo-root `.env`, `.env.sample` holds format only, NVIDIA key also in the macOS keychain |

## Verification strategy

| Tier | What | Needs keys |
| --- | --- | --- |
| 1. Unit | `pytest` with a fake Jev that returns real SDK response objects | no |
| 2. Script | `doctor.py`, `python -m case01_routing.main`, `python -m case02_deepagents.main` | yes |
| 3. Notebook | `src/notebooks/*.ipynb`, executed end to end, outputs kept | yes |

Tier 2 runs on NIM and on LM Studio (gemma-4-e4b, 32k context). The ChatGPT provider needs an
interactive sign-in, so its live checks wait for that (see the checklist).

## Known constraints

- Jev accepts text only.
- Deep Agents adds about 5,800 tokens of system prompt. Local models need at least 16k context.
- Hosted NIM is slow and uneven: 6 to 160 s per call, sometimes connection resets, sometimes
  degraded output. See `docs/05-verification.md`.
- The NIM catalog list is not proof a model is callable (`410 Gone` end-of-life models are listed).

## Checklist

### Foundation

- [x] Repository basics: MIT license, `.gitignore` for `.env` and `temp/` &mdash; `🎉 init: set up repository`
- [x] Skills: TypeSafe (`npx skills add --copy`), `centered-readme`, `git-commit-helper`, `.agents -> .claude` &mdash; `✨ feat(skills): add TypeSafe, centered-readme, and git-commit-helper skills`
- [x] uv app on Python 3.13 with dependencies and `studio` and `notebook` extras &mdash; `🔨 build(uv): add Python 3.13 uv app with dependencies`

### Core library

- [x] Chat model factory: ChatGPT subscription (1), NVIDIA NIM (2), LM Studio (3), automatic choice, timeout, thinking toggle, retry helper, `.env.sample` &mdash; `✨ feat(llm): add chat model factory for ChatGPT, NVIDIA NIM, and LM Studio`
- [x] Jev gateway (sync and async) and the triage policy &mdash; `✨ feat(jev): add Jev gateway and triage policy`
- [x] ChatGPT sign-in helper (`python -m pilot_jev.chatgpt_login`, browser or device code) &mdash; `✨ feat(login): add ChatGPT sign-in helper`

### Cases

- [x] Case 01: Jev as a LangGraph router, with tests &mdash; `✨ feat(routing): add LangGraph router case`
- [x] Case 02: Jev guardrail middleware and `verify_claim` tool in a Deep Agent, `langgraph.json`, with tests &mdash; `✨ feat(deepagents): add guardrail middleware and verify tool case`
- [x] `doctor.py` diagnostics &mdash; `✨ feat(doctor): add environment and connectivity diagnostics`

### Verification evidence

- [x] Executed notebooks for both cases on the final code, on LM Studio because hosted NIM output was not reliable enough to keep as an example &mdash; `✅ test(notebooks): add executed verification notebooks`
- [ ] Live check of the ChatGPT provider: sign in, then `doctor.py` and a minimal Case 01 run with a model the plan still allows (`LLM_MODEL=...`), keeping calls to a minimum. **Blocked on the user's interactive sign-in**

### Quality gate (fixes land in the feature commits above, since nothing is committed yet)

- [x] Code review by a subagent: 13 findings triaged, the valid ones applied (blocking model construction moved off the event loop, retry policy narrowed and never replays Jev, NaN fails closed, empty input handled, tool errors reach the model, dead code removed), 56 tests and lint green
- [x] Optimization pass: all three tiers re-run on the final code (LM Studio and NIM scripts, both notebooks, `langgraph dev`); ChatGPT excluded, see above

### Documentation

- [x] English: short README and `docs/` with Mermaid diagrams (overview, Jev, inference layer, cases, getting started, verification), official TypeSafe logos &mdash; `📄 docs(en): add README, guides, and TypeSafe logos`
  - [x] README, `01` to `04` written
  - [x] `05-verification.md` written from the final regression run
- [x] Korean translation &mdash; `📄 docs(ko): add Korean README and guides`
- [x] Japanese translation &mdash; `📄 docs(ja): add Japanese README and guides`
- [x] Simplified Chinese translation &mdash; `📄 docs(zh-cn): add Simplified Chinese README and guides`
- [x] Agent context: `AGENTS.md`, `CLAUDE.md`, and this plan &mdash; `📄 docs(agents): add agent context and plan`

### Reusable recipe

- [x] `make-pilot-agent-project` skill, updated with what this run taught &mdash; `✨ feat(skills): add make-pilot-agent-project skill`

### Release gate (checks, no commit)

- [x] `ruff check`, `ruff format --check`, `pytest` green (56 tests)
- [x] Every Mermaid block renders (40 blocks across the four languages, rendered with mermaid-cli)
- [x] Every relative Markdown link resolves in all four languages
- [x] No secret values in any file that would be committed
- [x] `langgraph dev` loads both graphs
- [x] Commit series verified: every file in exactly one commit, in the order above (72 files, 16 commits)

### Publish

- [ ] Commits created one by one from this checklist, after approval
- [ ] Pushed to `origin/main` in order. **v0.1 ready**
