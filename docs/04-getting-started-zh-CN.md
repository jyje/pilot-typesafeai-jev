# 快速上手

## 前置条件

- [uv](https://docs.astral.sh/uv/)（它会替你安装 Python 3.13）
- TypeSafe API 密钥：https://console.typesafe.ai/keys
- 一个聊天模型后端，按优先级依次为：（1）ChatGPT 订阅、（2）来自 https://build.nvidia.com 的 NVIDIA 密钥，或（3）在本地运行的 LM Studio

## 安装配置

```bash
cp .env.sample .env      # 填入 TYPESAFE_API_KEY；使用 NIM 时还需填入 NVIDIA_API_KEY
cd src
uv sync

# 仅在使用 OpenAI 订阅提供方时，执行一次：
uv run python -m pilot_jev.chatgpt_login
```

`.env` 位于仓库根目录，并已被 gitignore。`.env.sample` 用占位符展示了它的格式。

## 环境变量

| 变量 | 是否必需 | 说明 |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | 是 | 由 TypeSafe SDK 读取 |
| `LLM_PROVIDER` | 否 | `openai`、`nim` 或 `lmstudio`。未设置时，按此顺序选择第一个已配置的 |
| `LLM_MODEL` | 否 | 默认值：`gpt-5.5`（openai）、`nvidia/nemotron-3.5-lightning-30b-a3b`（nim）、`google/gemma-4-e4b`（lmstudio） |
| `LLM_TIMEOUT` | 否 | 单位为秒，默认 180 |
| `LLM_ENABLE_THINKING` | 否 | `false` 表示对 NIM 推理模型关闭思考 |
| `NVIDIA_API_KEY` | nim 时必需 | 托管目录 |
| `NVIDIA_BASE_URL` | 否 | 自托管 NIM |
| `LMSTUDIO_BASE_URL` | 否 | 默认 `http://127.0.0.1:1234/v1` |
| `JEV_MODEL` | 否 | 默认 `jev-latest` |

## 运行

命令都在 `src/` 目录下运行。

```bash
uv run python doctor.py                    # 检查密钥、Jev、聊天模型
uv run python -m case01_routing.main       # 五条示例消息
uv run python -m case01_routing.main "Where is my invoice?"     # 你自己的消息
uv run python -m case02_deepagents.main    # 一个正常请求和一次注入尝试
uv run pytest                              # 离线单元测试
uv run ruff check --fix . && uv run ruff format . && uv run ty check .   # lint, format, types
```

无需修改 `.env`，即可为每条命令单独切换聊天模型：

```bash
LLM_PROVIDER=lmstudio uv run python -m case01_routing.main
```

## Notebook

```bash
uv sync --extra notebook
uv run jupyter lab notebooks/
```

`notebooks/01-case01-routing.ipynb` 和 `notebooks/02-case02-deepagents.ipynb` 会针对在线服务运行各个用例。请逐个运行：并发负载下，托管的 NIM 会变慢。每个 notebook 先运行单个示例，再重复运行这些示例，因此在本地模型上需要好几分钟。韩语版本（`*-ko.ipynb`）的代码和结果与英文版相同，只是说明文字为韩语。重新运行某个英文 notebook 之后，用 `uv run python sync_notebooks_ko.py` 刷新它们。如果英文的 Markdown 单元格有改动，请先把对应的韩语文本添加到 `notebooks/ko.json`。当韩语 notebook 与英文 notebook 不一致时，`pytest` 会失败。

若要以无头方式执行其中一个并保留输出：

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01-case01-routing.ipynb
```

## LangGraph Studio

```bash
uv sync --extra studio
uv run langgraph dev --no-browser
```

`langgraph.json` 注册了两个图：`routing`（Case 01）和 `deepagent`（Case 02）。服务器会读取 `../.env`。

## 使用编码智能体

Skills 位于 `.claude/skills/`。`.agents` 是指向 `.claude` 的符号链接，因此 Claude Code、Codex、Hermes 和 Copilot 看到的是同一套 skills。编写调用 Jev 的代码之前，请先阅读 `typesafe-ai` skill。

## 故障排查

| 现象 | 原因与解决办法 |
| --- | --- |
| `Not signed in to ChatGPT: ...` | 运行一次 `uv run python -m pilot_jev.chatgpt_login`。消息会说明令牌文件是缺失、为空、已损坏还是不完整，此时自动选择会回退到 NIM 或 LM Studio |
| `doctor.py`：`TYPESAFE_API_KEY` 未设置 | 把它写进仓库根目录的 `.env`，而不是 `src/` 下 |
| NIM 返回 `410 Gone` | 该模型已下线。用 `LLM_MODEL` 换一个 |
| NIM 返回 `403 Forbidden` | 该密钥无法运行推理。请在 build.nvidia.com 创建新密钥 |
| `ReadTimeout` 或 `SocketTimeoutError` | 托管服务延迟所致。调大 `LLM_TIMEOUT`（例如 600） |
| 回复以 `Here's a thinking process` 开头 | 设置 `LLM_ENABLE_THINKING=false` |
| LM Studio `n_keep >= n_ctx` | 加载模型时，上下文长度至少设为 16384 |
| LM Studio 列表中没有该模型 | 先加载它：`lms load <model> --context-length 32768` |
