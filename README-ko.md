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

## 이 파일럿의 목표

TypeSafe AI의 [Jev](https://docs.typesafe.ai/concepts/system-one)를 LangGraph와 Deep Agents에 실제로
적용해 보고, 무엇이 되고 무엇이 안 되는지 기록합니다.

1. **Jev 이해하기.** 생성된 글 대신 확률이 붙은 타입 있는 답(`Choice`, `Score`, `Noul`)을 돌려주며, 모든 답에
   신뢰도가 함께 옵니다. [Jev 개요](docs/01-jev-overview-ko.md)를 참고하세요.
2. **역할 분담 보여주기.** 워크플로는 코드가 맡고, 빠른 판단은 Jev가 내리며, 답변 작성은 여전히 채팅 모델이 합니다.
3. **LangGraph에서 Jev로 라우팅(Case 01).** 요청 한 번에 질문 세 개를 묻고, 코드가 경로를 정하며, `answer` 경로만
   채팅 모델 토큰을 씁니다.
4. **Deep Agents에서 Jev로 방어하고 검증(Case 02).** 가드레일 미들웨어가 에이전트 시작 전에 메시지를 걸러내고,
   `verify_claim` 도구가 신뢰도가 붙은 판정을 돌려줍니다. [케이스](docs/03-cases-ko.md)를 참고하세요.
5. **검증하기.** 단위 테스트, 실서비스 스크립트, 실행된 노트북으로 확인하고 측정 결과, 실패 사례, 주의점을 공개합니다.
   [검증](docs/05-verification-ko.md)을 참고하세요.

이 파일럿이 아닌 것:

- Jev의 정확도를 재는 벤치마크가 아닙니다. 임계값은 튜닝하지 않은 출발점입니다.
- 운영용 코드가 아닙니다.
- ChatGPT 구독 공급자는 실험적이고 비공식이라 안정적인 통합이 아닙니다.

## 두 가지 케이스

Case 01과 Case 02를 한눈에 봅니다.

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
```

```mermaid
flowchart LR
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

| 문서 | 다루는 내용 |
| --- | --- |
| [Jev 개요](docs/01-jev-overview-ko.md) | Jev가 무엇을 반환하는지, 어떻게 질문하는지 |
| [추론 계층](docs/02-inference-layer-ko.md) | 하나의 팩토리 뒤에 있는 ChatGPT, NVIDIA NIM, LM Studio |
| [케이스](docs/03-cases-ko.md) | 두 케이스의 그래프와 시퀀스 다이어그램 |
| [시작하기](docs/04-getting-started-ko.md) | 설정, 환경 변수, 노트북, LangGraph Studio |
| [검증](docs/05-verification-ko.md) | 무엇을 테스트했는지, 결과, 주의 사항 |

진행 상황과 범위는 [PLAN.md](PLAN.md), 에이전트용 컨텍스트는 [AGENTS.md](AGENTS.md)를 참고하세요.

## 라이선스

[MIT](LICENSE)
