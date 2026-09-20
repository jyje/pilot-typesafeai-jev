---
name: make-pilot-agent-project
description: Bootstrap a pilot repo that follows the agreed conventions and studies one AI model or product and shows how it fits into LangGraph and Deep Agents, with a switchable inference layer (ChatGPT subscription, NVIDIA NIM, LM Studio). Covers the initial requirements checklist, project init recipe, skills to install, private temp notes, PLAN/TASK checkbox tracking, three-tier verification (pytest, scripts, notebooks), and secrets handling. Use when asked to start a new pilot around a model, SDK, or vendor product with langgraph, deepagents, NIM, or LM Studio, or to reproduce how pilot-typesafeai-jev was set up. Triggers: "pilot-... 만들어줘", "이 모델을 langgraph/deepagents에 적용하는 파일럿", "초기 설정 해줘", "make-pilot-agent-project".
---

# make-pilot-agent-project

Recipe distilled from `pilot-typesafeai-jev`. It extends `make-pilot-python` (repo, README, uv
basics) with the agent-project parts: skills, inference layer, verification tiers, and secrets.
Use `make-pilot-python` first if it is available, then follow this for everything else.

Templates and pointers:
- [`references/initial-requirements.md`](references/initial-requirements.md): the checklist to
  fill in with the user before doing anything
- [`references/reference-projects.md`](references/reference-projects.md): sibling pilots to read

## 1. Capture requirements first

Fill in the checklist in `references/initial-requirements.md`. Ask the user only about what the
request and the code cannot settle. In the original run these were: Python version, how to install
the vendor skill so other agents see it, case scope, and where the new skill should live. Pick
sensible defaults for the rest and say so.

## 2. Read local before fetching

- Sibling repos and your own skills repo usually exist as local checkouts (for example under `~/repo/<owner>/`). Read them there.
  **Never clone what is already local.** If one is missing, fetch single files with
  `gh api repos/<owner>/<repo>/contents/<path> --jq .content | base64 -d`.
- Read the vendor's official docs live (`<docs>/llms.txt`, append `.md` to page paths) and obey the
  vendor skill's own instructions.
- Write what you learn to `temp/NN-*.md`. `temp/` is gitignored, accumulates, and is never
  published. Do not put reference analysis into READMEs, docs, or skills.

## 3. Scaffold

```bash
cd ~/repo/<owner>/<repo>                    # repo may already exist with a remote; do not recreate it
printf 'temp/\n.env\n' >> .gitignore      # then expand to a full Python .gitignore

# Skills: real files in .claude/skills, symlink for other agents
mkdir -p .claude/skills
cp -R <skills-repo>/centered-readme <skills-repo>/git-commit-helper .claude/skills/
ln -s .claude .agents                     # Codex, Hermes, Copilot read .agents
npx -y skills add <vendor>/skills --skill <skill> --agent claude-code --copy -y
```

Use **one** install method for the vendor skill. `--copy` puts real files in `.claude/skills/` and
avoids a conflict with the `.agents` symlink. If a plugin was installed first, uninstall it
(`claude plugin uninstall ... --scope project`, `claude plugin marketplace remove ...`).

```bash
mkdir -p src && cd src
uv init --name <repo> --python ">=3.13,<3.14" --no-readme
uv python pin 3.13
uv add <vendor-sdk> deepagents langgraph langchain-nvidia-ai-endpoints langchain-openai python-dotenv
rm -rf src                                # drop the packaged layout uv init creates
# rewrite pyproject.toml as a flat app: no [build-system], no [project.scripts]
# add optional extras: studio (langgraph-cli[inmem]) and notebook (jupyter, ipykernel, nbformat, nbconvert)
uv add --dev pytest pytest-asyncio ruff
```

Layout: flat uv app in `src/`, shared code in `src/<pkg>/`, one folder per case
(`case01_<name>/`, `case02_<name>/`) each with `graph.py` and `main.py`, plus `tests/`,
`notebooks/`, `doctor.py`, `langgraph.json`. Set pytest `pythonpath = ["."]` and run cases with
`python -m caseNN_x.main`.

## 4. Inference layer

One factory, `LLM_PROVIDER=openai|nim|lmstudio`, in that priority order. With the variable unset the
first configured provider wins: ChatGPT sign-in, then an NVIDIA key or base URL, then LM Studio.

- `openai` (ChatGPT subscription): `langchain-openai` ships experimental `chatgpt_oauth.login_chatgpt`
  (browser PKCE) and `login_chatgpt_device` (headless), plus `chat_models.codex._ChatOpenAICodex`.
  It talks to the ChatGPT Codex backend, **not** `api.openai.com`, so `ChatOpenAI` with an OAuth
  token does not work and `OPENAI_API_KEY` is not used. The token lives in
  `~/.langchain/chatgpt-auth.json`. **Never read or copy `~/.codex/auth.json`**: rotating the Codex CLI
  token can break the user's CLI sessions. Keep the "experimental, unofficial, check your terms"
  warning in the docs and in the login helper. Signing in is interactive, so ask the user to run it
  (`! uv run python -m pilot_jev.chatgpt_login`, browser flow) and verify afterwards. The device-code
  flow of `langchain-openai` 1.6.2 fails with HTTP 400 (form body where the endpoint wants JSON), so
  start the browser flow yourself in the background and hand the user the sign-in URL. Model names
  differ per account and some are rejected for ChatGPT accounts (HTTP 400): discover them with the
  Codex `models` endpoint (`GET https://chatgpt.com/backend-api/codex/models?client_version=1.0.0`
  with the Bearer token and `ChatGPT-Account-Id` header, printing IDs only). A plan near its limit
  returns HTTP 429, so try one cheap model with a tiny prompt before running anything longer.

- NIM: package `langchain-nvidia-ai-endpoints`, class `ChatNVIDIA`. **`langchain-nvidia-nim` does not
  exist.** Pass `api_key`, optional `base_url` for self-hosted NIM.
- LM Studio: `ChatOpenAI(base_url="http://127.0.0.1:1234/v1", api_key="lm-studio")`. The `lms` CLI
  (`~/.cache/lm-studio/bin/lms`) can `ls`, `ps`, `load <model> --context-length 32768 -y`, and
  `unload`. Loading a model uses several GB of RAM, so ask before doing it, and unload afterwards.
- Set a generous `timeout` (`LLM_TIMEOUT`, default 180). Hosted NIM took 6 to 160 s per call, while LM Studio with gemma-4-e4b answered a Deep Agent run in about a minute.
- Test model ids by calling them. A model in the catalog list can return `410 Gone` (end of life)
  or `403`.
- LM Studio needs context length of 16k or more for Deep Agents (about 5,800 tokens of system prompt).
- NIM reasoning models can leak their thinking into the reply. Offer `LLM_ENABLE_THINKING=false`, sent as
  `model_kwargs={"chat_template_kwargs": {"enable_thinking": False}}`.
- The hosted endpoint sometimes resets connections mid-run and `ChatNVIDIA` has no retry setting.
  Retry the chat model *call* (in the node, or in an agent middleware's `awrap_model_call`), never a
  whole graph or agent run: a replay calls and bills the vendor again. Do not retry 401, 403, or 404.
- Put vendor calls behind one gateway class with `ask` and `aask` so tests can inject a fake that
  returns the SDK's real response type.

## 5. Track work with checkboxes

Create one `PLAN.md`: goal, decisions table, verification strategy, constraints, and a checklist.
**One checklist item is one meaningful piece of work and one commit**, with the commit title after
it. Tick an item only after it has run. Add items as work turns up, and backfill items for work that
was done before it had one. No separate `TASK.md`. When every box is ticked the release is ready.
Add `AGENTS.md` plus a `CLAUDE.md` that starts with `@AGENTS.md`.
**At release, delete `PLAN.md`** (git history keeps it), remove its links from the README and
`AGENTS.md`, and tag `v0.1.0`.

## 6. Verify in three tiers

1. **Unit**: follow the `python-lint` skill (`ruff check --fix`, `ruff format`, `ty check`, `pytest`, dev
   deps `ruff ty pytest`; put `nbformat` in the dev group too if tests touch notebooks, and lint the
   notebooks). Type the vendor gateway as a `Protocol` so fakes type-check. `pytest` offline with fakes. Routes that must not call the model use a model that
   raises when touched.
2. **Scripts**: `doctor.py` (env, vendor API, chat model) and each case's `main.py`, live.
3. **Notebooks**: `src/notebooks/NN-*.ipynb`, generated with `nbformat`, executed with
   `uv run jupyter nbconvert --to notebook --execute --inplace`, outputs kept. Do not stop at single
   runs: repeat each experiment (10 runs for cheap vendor calls with `asyncio.gather`, 3 to 5 for slow
   chat-model runs), add a hand-written scenario sweep with expected outcomes, and print the results as
   Markdown tables (`IPython.display.Markdown`) with agreement counts and mean (min to max), so trends
   show. A translated twin (for example `*-ko.ipynb`) should copy code and outputs from the English
   notebook and translate only the Markdown, via a sync script plus a `--check` test.

Do simple, long-running work in the background too. Run slow live calls in the background (a `nohup` script, one at a time, since hosted NIM slows under
concurrent load) and write docs meanwhile. Say plainly what was not verified.

After the work is done, get a **code review from a read-only subagent**, triage each finding by
reading the code yourself, apply the valid ones, add tests for them, and re-run the tiers. Findings
that paid off here: model construction doing blocking I/O inside the event loop, a retry that also
replayed billed vendor calls, NaN slipping through threshold comparisons, empty input reaching the
vendor, a tool failure aborting a whole agent run, and dead code.

## 7. Secrets

- Keys live in the repo-root `.env` (gitignored). `.env.sample` holds format only with obvious
  placeholders. Never print, log, or commit a key. Check `.env` by variable name with values masked.
- macOS keychain: convention is service = key type, account = project. **Add a new item for the
  project; do not overwrite another project's item.** Pass the value over stdin so it never appears
  in `ps`:
  `printf 'add-generic-password -a "<project>" -s "<Service>" -w "%s" -U\n' "$key" | security -i`
  Read back with `security find-generic-password -s "<Service>" -a "<project>" -w` and compare
  without printing.

## 8. Docs and hand-off

- Keep the README short and visual (what it is, one diagram, quick start, links). Put detail in `docs/`
  (overview, inference layer, cases, getting started, verification) with **Mermaid** graphs for
  structure and sequence diagrams for flows. Render every block with
  `npx -y -p @mermaid-js/mermaid-cli mmdc -i x.mmd -o x.svg` before publishing; extract blocks with a
  small script so a single syntax slip is caught.
- `README.md`, `README-ko.md`, `README-ja.md`, `README-zh-CN.md` with the `centered-readme` hero and the navigator
  `[English](README.md) / [한국어](README-ko.md) / [日本語](README-ja.md) / [简体中文](README-zh-CN.md) / [Docs](docs/README.md)`. Download the vendor's official
  logo (light and dark) into `docs/images/` and reference it through `raw.githubusercontent.com`
  with `#gh-light-mode-only` and `#gh-dark-mode-only`.
- `docs/` guides in English, then `-ko`, `-ja`, `-zh-CN` twins (this order everywhere: navigators, indexes, commits), `LICENSE` (MIT).
  Translate in the main session, not with subagents (each subagent re-reads sources and rewrites whole
  files, which is costly): edit only the changed sections, keep code, URLs, identifiers, and Mermaid
  syntax intact, then check that headings, code blocks, table rows, and URLs match the English page.
  Use a subagent only when a genuinely clean context is needed, such as an independent code review.
- Commits follow `git-commit-helper`: English, `<gitmoji> <type>(<domain>): <title>`, propose and
  wait for approval, never include session IDs or URLs, never add co-author trailers. Push only
  after explicit approval.

## Gotchas seen

- `find_dotenv()` fails when called from stdin scripts; pass the `.env` path explicitly there.
- Vendor response models may need `model_validate_json` for fixtures (integer dict keys).
- In zsh, `echo =====` errors; quote separators.
- `uv init` creates a packaged layout; remove it or the build fails after you delete `src/`.
- Deep Agents factories that build the chat model must be functions (`make_agent`) so importing the
  module needs no credentials; `langgraph.json` can point at a factory. `langgraph dev` rejects a
  factory with more than two parameters, so expose a zero-argument `make_graph()` for it.
- Run `langgraph dev --no-browser --no-reload` and query `/assistants/search` to prove the graphs load,
  then run one cheap path (an injection refusal) through `/runs/wait`. Factories may be `async`, which
  lets you build the chat model with `asyncio.to_thread`.
- Give notebook agent cells their own time budget. One slow hosted NIM turn can outlast the default
  cell timeout, so set `--ExecutePreprocessor.timeout` and run notebooks one at a time, not in parallel.
