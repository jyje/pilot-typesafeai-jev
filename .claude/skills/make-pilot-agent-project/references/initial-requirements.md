# Initial requirements checklist

Copy this into `PLAN.md` decisions and fill it in. The right column shows what the original
`pilot-typesafeai-jev` request said, as a worked example.

| # | Requirement | Example (pilot-typesafeai-jev) |
| --- | --- | --- |
| 1 | Subject: the model or product to study | TypeSafe AI **Jev** (System One model) |
| 2 | Purpose | Understand Jev, and show use cases with LangGraph and Deep Agents |
| 3 | Official docs (user-designated) | https://docs.typesafe.ai/introduction/quickstart |
| 4 | Vendor skill and install method | `typesafe-ai` from `typesafe-ai/skills`, one method only; Claude Code plugin or `npx skills add` |
| 5 | Personal skills to add | `centered-readme`, `git-commit-helper` from `jyje/skills`, under `.claude/skills/` |
| 6 | Multi-agent visibility | `ln -s .claude .agents` so Codex, Hermes, Copilot read the same skills |
| 7 | Inference layers, in priority order | 1 ChatGPT subscription (Codex OAuth), 2 NVIDIA NIM (`langchain-nvidia-ai-endpoints`), 3 LM Studio (OpenAI-compatible) |
| 8 | Reference projects | see `reference-projects.md`; already local, do not clone |
| 9 | Reference analysis handling | keep private in a gitignored `temp/`, accumulate, never expose |
| 10 | Vendor logo | include the official logo in the README |
| 11 | Plan and tasks | one `PLAN.md` with a checkbox list; one item is one commit; backfill items for finished work; finished PLAN means release ready |
| 12 | Verification | scripts and Jupyter notebooks both |
| 13 | Secrets | `.env` at repo root, `.env.sample` format only, key also in the macOS keychain |
| 14 | Python | 3.13 |
| 14a | Doc languages and order | English (default), Korean, Japanese, Simplified Chinese |
| 14b | Long-running work | run in the background or with subagents, keep working meanwhile |
| 14c | Push preparation | commit per checklist item in order, propose messages, wait for approval |
| 14d | Docs style | short README, detail in `docs/`, Mermaid graphs and sequence diagrams |
| 14e | Quality | code review and optimization after everything works |
| 15 | Case scope | Case 01 LangGraph routing, Case 02 Deep Agents middleware and tool |
| 16 | Skill for this recipe | this skill, in the repo and copied to `~/repo/jyje/skills` |
| 17 | Ask about | anything ambiguous, before building |

## Questions worth asking (and only these kinds)

- Choices that change the result and have no obvious default: Python version, case scope, where to
  install or put a skill, whether a key may be reused from the keychain.
- Not worth asking: package layout, test framework, doc structure. Follow this skill and say so.

## Mid-run changes to expect

Users refine as work proceeds: a renamed environment variable, a new key, extra models to test, a
request for notebooks or a checkbox plan. Fold each into `PLAN.md` and `TASK.md` rather than
restarting.
