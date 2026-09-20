# 시작하기

## 사전 준비

- [uv](https://docs.astral.sh/uv/) (Python 3.13은 uv가 설치해 줍니다)
- TypeSafe API 키: https://console.typesafe.ai/keys
- 채팅 모델 백엔드 하나. 우선순위 순으로 ChatGPT 구독, https://build.nvidia.com 에서 발급한 NVIDIA 키, 로컬에서 실행 중인 LM Studio 중에서 고릅니다

## 설정

```bash
cp .env.sample .env      # TYPESAFE_API_KEY를 채우고, NIM을 쓴다면 NVIDIA_API_KEY도 채웁니다
cd src
uv sync

# OpenAI 구독 프로바이더를 쓸 때만, 한 번 실행합니다:
uv run python -m pilot_jev.chatgpt_login
```

`.env`는 저장소 루트에 두며 gitignore 대상입니다. `.env.sample`에서 자리표시자로 채워진 형식을 볼 수 있습니다.

## 환경 변수

| 변수 | 필수 | 비고 |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | 예 | TypeSafe SDK가 읽습니다 |
| `LLM_PROVIDER` | 아니요 | `openai`, `nim`, `lmstudio` 중 하나. 미설정이면 이 순서대로 구성된 첫 항목을 선택합니다 |
| `LLM_MODEL` | 아니요 | 기본값: `gpt-5.5` (openai), `nvidia/nemotron-3.5-lightning-30b-a3b` (nim), `google/gemma-4-e4b` (lmstudio) |
| `LLM_TIMEOUT` | 아니요 | 초 단위, 기본값 180 |
| `LLM_ENABLE_THINKING` | 아니요 | `false`이면 NIM 추론 모델의 thinking을 끕니다 |
| `NVIDIA_API_KEY` | nim | 호스팅 카탈로그용 |
| `NVIDIA_BASE_URL` | 아니요 | 자체 호스팅 NIM |
| `LMSTUDIO_BASE_URL` | 아니요 | 기본값 `http://127.0.0.1:1234/v1` |
| `JEV_MODEL` | 아니요 | 기본값 `jev-latest` |

## 실행하기

명령은 `src/`에서 실행합니다.

```bash
uv run python doctor.py                    # 키, Jev, 채팅 모델
uv run python -m case01_routing.main       # 샘플 메시지 다섯 개
uv run python -m case01_routing.main "Where is my invoice?"     # 직접 입력한 메시지
uv run python -m case02_deepagents.main    # 정상 요청 하나와 인젝션 시도 하나
uv run pytest                              # 오프라인 단위 테스트
uv run ruff check . && uv run ruff format --check .
```

`.env`를 수정하지 않고 명령마다 채팅 모델을 바꿀 수 있습니다.

```bash
LLM_PROVIDER=lmstudio uv run python -m case01_routing.main
```

## 노트북

```bash
uv sync --extra notebook
uv run jupyter lab notebooks/
```

`notebooks/01-case01-routing.ipynb`와 `notebooks/02-case02-deepagents.ipynb`는 각 케이스를 실제 서비스에 대해 실행합니다. 하나씩 실행하세요. 호스팅 NIM은 동시 부하가 걸리면 느려집니다. 하나를 헤드리스로 실행하고 출력을 남기려면 다음과 같이 합니다.

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01-case01-routing.ipynb
```

## LangGraph Studio

```bash
uv sync --extra studio
uv run langgraph dev --no-browser
```

`langgraph.json`에는 그래프 두 개가 등록되어 있습니다. `routing`(Case 01)과 `deepagent`(Case 02)입니다. 서버는 `../.env`를 읽습니다.

## 코딩 에이전트 사용하기

스킬은 `.claude/skills/`에 있습니다. `.agents`는 `.claude`를 가리키는 심볼릭 링크이므로 Claude Code, Codex, Hermes, Copilot이 같은 스킬을 봅니다. Jev를 호출하는 코드를 작성하기 전에 `typesafe-ai` 스킬을 먼저 읽으세요.

## 문제 해결

| 증상 | 원인과 해결 |
| --- | --- |
| `Not signed in to ChatGPT` | `uv run python -m pilot_jev.chatgpt_login`을 한 번 실행합니다 |
| `doctor.py`: `TYPESAFE_API_KEY` not set | `src/`가 아니라 저장소 루트의 `.env`에 넣습니다 |
| NIM에서 `410 Gone` | 모델이 지원 종료되었습니다. `LLM_MODEL`로 다른 모델을 고릅니다 |
| NIM에서 `403 Forbidden` | 해당 키로는 추론을 실행할 수 없습니다. build.nvidia.com 에서 새 키를 만듭니다 |
| `ReadTimeout` 또는 `SocketTimeoutError` | 호스팅 지연 때문입니다. `LLM_TIMEOUT`을 올립니다(예: 600) |
| 응답이 `Here's a thinking process`로 시작함 | `LLM_ENABLE_THINKING=false`를 설정합니다 |
| LM Studio `n_keep >= n_ctx` | 컨텍스트 길이를 16384 이상으로 설정해 모델을 로드합니다 |
| LM Studio에 모델이 표시되지 않음 | 모델을 로드합니다: `lms load <model> --context-length 32768` |
