<div align="center">

# jyje/pilot-typesafeai-jev

<img width="280" src="https://raw.githubusercontent.com/jyje/pilot-typesafeai-jev/main/docs/images/typesafe-logo-light.png#gh-light-mode-only" alt="TypeSafe AI" title="TypeSafe AI"/>
<img width="280" src="https://raw.githubusercontent.com/jyje/pilot-typesafeai-jev/main/docs/images/typesafe-logo-dark.png#gh-dark-mode-only" alt="TypeSafe AI" title="TypeSafe AI"/>

🚀 LangGraph와 Deep Agents에서 TypeSafe AI **Jev**를 ChatGPT, NVIDIA NIM, LM Studio 위에서 시험해 보는 파일럿 프로젝트

[![GitHub Repo stars](https://img.shields.io/github/stars/jyje/pilot-typesafeai-jev?style=social)](https://github.com/jyje/pilot-typesafeai-jev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org)
[![TypeSafe AI](https://img.shields.io/badge/Model-TypeSafe%20AI%20Jev-black)](https://docs.typesafe.ai/introduction/quickstart)
[![ChatGPT](https://img.shields.io/badge/Inference-ChatGPT-10A37F)](docs/02-inference-layer-ko.md)
[![NVIDIA NIM](https://img.shields.io/badge/Inference-NVIDIA%20NIM-76B900)](https://build.nvidia.com)
[![LM Studio](https://img.shields.io/badge/Inference-LM%20Studio-5B5BD6)](https://lmstudio.ai)

[English](README.md) / [한국어](README-ko.md) / [日本語](README-ja.md) / [简体中文](README-zh-CN.md) / [Docs](docs/README.md)

---

**도움이 되셨나요? ⭐를 눌러 주세요. 다른 분들이 이 프로젝트를 찾는 데 도움이 됩니다.**

</div>

## 소개

[Jev](https://docs.typesafe.ai/concepts/system-one)는 텍스트를 읽고 생성된 글이 아니라 **확률이 붙은 타입 있는 답**을 돌려줍니다. 워크플로 제어는 코드가 맡고, 빠른 판단은 Jev가 내리며, 답변 작성은 여전히 채팅 모델이 담당합니다.

이 저장소는 Jev를 두 곳에 적용하고 그 결과를 기록합니다.

```mermaid
flowchart LR
    subgraph C1["Case 01 · LangGraph 라우터"]
        direction LR
        m1([메시지]) --> t["triage<br/>Jev 호출 1회"]
        t -->|명확하고 차분함| a["answer<br/>채팅 모델"]
        t -->|긴급| e[escalate]
        t -->|불분명| r[review]
        t -->|인젝션| f[refuse]
    end
    subgraph C2["Case 02 · Deep Agent"]
        direction LR
        m2([메시지]) --> g{"Jev 가드레일"}
        g -->|차단| f2[refuse]
        g -->|통과| ag["에이전트 + 채팅 모델"]
        ag <-->|verify_claim| j["Jev 판정"]
    end
```

채팅 모델은 **ChatGPT 구독**(1), **NVIDIA NIM**(2), **LM Studio**(3) 중 하나에서 실행됩니다. `LLM_PROVIDER`를 설정하거나, 설정하지 않으면 구성된 항목 중 가장 먼저 발견되는 것을 사용합니다.

## 빠른 시작

```bash
cp .env.sample .env        # TYPESAFE_API_KEY를 추가하고, NIM을 쓴다면 NVIDIA_API_KEY도 추가
cd src && uv sync

uv run python doctor.py                    # 키, Jev, 채팅 모델 점검
uv run python -m case01_routing.main       # 샘플 메시지로 Case 01 실행
uv run python -m case02_deepagents.main    # 샘플 요청으로 Case 02 실행
uv run pytest                              # 오프라인 테스트, 키 불필요
```

## 문서

| | |
| --- | --- |
| [Jev 개요](docs/01-jev-overview-ko.md) | Jev가 무엇을 반환하는지, 어떻게 질문하는지 |
| [추론 계층](docs/02-inference-layer-ko.md) | 하나의 팩토리 뒤에 있는 ChatGPT, NVIDIA NIM, LM Studio |
| [케이스](docs/03-cases-ko.md) | 두 케이스의 그래프와 시퀀스 다이어그램 |
| [시작하기](docs/04-getting-started-ko.md) | 설정, 환경 변수, 노트북, LangGraph Studio |
| [검증](docs/05-verification-ko.md) | 무엇을 테스트했는지, 결과, 주의 사항 |

진행 상황과 범위는 [PLAN.md](PLAN.md), 에이전트용 컨텍스트는 [AGENTS.md](AGENTS.md)를 참고하세요.

## 라이선스

[MIT](LICENSE)
