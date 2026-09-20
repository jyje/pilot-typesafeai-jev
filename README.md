<div align="center">

# jyje/pilot-typesafeai-jev

<img width="280" src="https://raw.githubusercontent.com/jyje/pilot-typesafeai-jev/main/docs/images/typesafe-logo-light.png#gh-light-mode-only" alt="TypeSafe AI" title="TypeSafe AI"/>
<img width="280" src="https://raw.githubusercontent.com/jyje/pilot-typesafeai-jev/main/docs/images/typesafe-logo-dark.png#gh-dark-mode-only" alt="TypeSafe AI" title="TypeSafe AI"/>

🚀 Pilot project for TypeSafe AI **Jev** in LangGraph and Deep Agents, on ChatGPT, NVIDIA NIM, or LM Studio

[![GitHub Repo stars](https://img.shields.io/github/stars/jyje/pilot-typesafeai-jev?style=social)](https://github.com/jyje/pilot-typesafeai-jev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org)
[![TypeSafe AI](https://img.shields.io/badge/Model-TypeSafe%20AI%20Jev-black)](https://docs.typesafe.ai/introduction/quickstart)
[![ChatGPT](https://img.shields.io/badge/Inference-ChatGPT-10A37F)](docs/02-inference-layer.md)
[![NVIDIA NIM](https://img.shields.io/badge/Inference-NVIDIA%20NIM-76B900)](https://build.nvidia.com)
[![LM Studio](https://img.shields.io/badge/Inference-LM%20Studio-5B5BD6)](https://lmstudio.ai)

[English](README.md) / [한국어](README-ko.md) / [日本語](README-ja.md) / [简体中文](README-zh-CN.md) / [Docs](docs/README.md)

---

**Found this useful? Please give it a ⭐. It helps others find it.**

</div>

## What is this

[Jev](https://docs.typesafe.ai/concepts/system-one) reads text and returns **typed answers with
probabilities**, not generated text. Code keeps control of the workflow, Jev makes the fast
judgment calls, and a chat model still writes the replies.

This repo puts Jev in two places and records what happens:

```mermaid
flowchart LR
    subgraph C1["Case 01 · LangGraph router"]
        direction LR
        m1([message]) --> t["triage<br/>one Jev call"]
        t -->|clear and calm| a["answer<br/>chat model"]
        t -->|urgent| e[escalate]
        t -->|unclear| r[review]
        t -->|injection| f[refuse]
    end
```

```mermaid
flowchart LR
    subgraph C2["Case 02 · Deep Agent"]
        direction LR
        m2([message]) --> g{"Jev guardrail"}
        g -->|blocked| f2[refuse]
        g -->|ok| ag["agent + chat model"]
        ag <-->|verify_claim| j["Jev verdict"]
    end
```

The chat model runs on your **ChatGPT subscription** (1), **NVIDIA NIM** (2), or **LM Studio** (3).
Set `LLM_PROVIDER`, or leave it unset to use the first one that is configured.

## Quick start

```bash
cp .env.sample .env        # add TYPESAFE_API_KEY, and NVIDIA_API_KEY for NIM
cd src && uv sync

uv run python doctor.py                    # check keys, Jev, and the chat model
uv run python -m case01_routing.main       # Case 01 on sample messages
uv run python -m case02_deepagents.main    # Case 02 on sample requests
uv run pytest                              # offline tests, no keys needed
```

## Docs

| Guide | What it covers |
| --- | --- |
| [Jev overview](docs/01-jev-overview.md) | what it returns and how to ask it |
| [Inference layer](docs/02-inference-layer.md) | ChatGPT, NVIDIA NIM, and LM Studio behind one factory |
| [Cases](docs/03-cases.md) | graph and sequence diagrams for both cases |
| [Getting started](docs/04-getting-started.md) | setup, environment, notebooks, LangGraph Studio |
| [Verification](docs/05-verification.md) | what was tested, results, and caveats |

Progress and scope: [PLAN.md](PLAN.md). Agent context: [AGENTS.md](AGENTS.md).

## License

[MIT](LICENSE)
