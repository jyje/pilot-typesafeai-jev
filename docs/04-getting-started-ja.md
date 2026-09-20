# はじめに

## 前提条件

- [uv](https://docs.astral.sh/uv/)（Python 3.13 も uv がインストールします）
- TypeSafe の API キー: https://console.typesafe.ai/keys
- チャットモデルのバックエンドを 1 つ（優先順位順）: ChatGPT サブスクリプション、https://build.nvidia.com の NVIDIA キー、またはローカルで動作する LM Studio

## セットアップ

```bash
cp .env.sample .env      # TYPESAFE_API_KEY を入力。NIM を使う場合は NVIDIA_API_KEY も入力
cd src
uv sync

# OpenAI サブスクリプションの provider を使う場合のみ、初回に 1 回実行:
uv run python -m pilot_jev.chatgpt_login
```

`.env` はリポジトリのルートに置き、gitignore 対象です。`.env.sample` にプレースホルダー付きの書式例があります。

## 環境変数

| 変数 | 必須 | 備考 |
| --- | --- | --- |
| `TYPESAFE_API_KEY` | yes | TypeSafe SDK が読み込みます |
| `LLM_PROVIDER` | no | `openai`、`nim`、`lmstudio` のいずれか。未設定の場合は、この順で設定済みの先頭が選ばれます |
| `LLM_MODEL` | no | デフォルト: `gpt-5.5`（openai）、`nvidia/nemotron-3.5-lightning-30b-a3b`（nim）、`google/gemma-4-e4b`（lmstudio） |
| `LLM_TIMEOUT` | no | 秒。デフォルトは 180 |
| `LLM_ENABLE_THINKING` | no | `false` にすると NIM の推論モデルで thinking をオフにします |
| `NVIDIA_API_KEY` | nim | ホスト型カタログ用 |
| `NVIDIA_BASE_URL` | no | セルフホスト NIM |
| `LMSTUDIO_BASE_URL` | no | デフォルトは `http://127.0.0.1:1234/v1` |
| `JEV_MODEL` | no | デフォルトは `jev-latest` |

## 実行する

コマンドは `src/` で実行します。

```bash
uv run python doctor.py                    # キー、Jev、チャットモデル
uv run python -m case01_routing.main       # サンプルメッセージ 5 件
uv run python -m case01_routing.main "Where is my invoice?"     # 自分のメッセージ
uv run python -m case02_deepagents.main    # 問題のないリクエストとインジェクション攻撃の試行
uv run pytest                              # オフラインのユニットテスト
uv run ruff check . && uv run ruff format --check .
```

`.env` を編集せずに、コマンドごとにチャットモデルを切り替えられます。

```bash
LLM_PROVIDER=lmstudio uv run python -m case01_routing.main
```

## ノートブック

```bash
uv sync --extra notebook
uv run jupyter lab notebooks/
```

`notebooks/01-case01-routing.ipynb` と `notebooks/02-case02-deepagents.ipynb` は、それぞれのケースを実際のサービスに対して実行します。1 つずつ実行してください。ホスト型 NIM は同時に負荷がかかると遅くなります。ヘッドレスで実行して出力を残すには、次のようにします。

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01-case01-routing.ipynb
```

## LangGraph Studio

```bash
uv sync --extra studio
uv run langgraph dev --no-browser
```

`langgraph.json` には 2 つのグラフが登録されています。`routing`（Case 01）と `deepagent`（Case 02）です。サーバーは `../.env` を読み込みます。

## コーディングエージェントを使う

スキルは `.claude/skills/` にあります。`.agents` は `.claude` へのシンボリックリンクなので、Claude Code、Codex、Hermes、Copilot は同じスキルを参照します。Jev を呼び出すコードを書く前に、`typesafe-ai` スキルを読んでください。

## トラブルシューティング

| 症状 | 原因と対処 |
| --- | --- |
| `Not signed in to ChatGPT` | `uv run python -m pilot_jev.chatgpt_login` を 1 回実行します |
| `doctor.py`: `TYPESAFE_API_KEY` not set | `src/` ではなく、リポジトリルートの `.env` に記述します |
| NIM から `410 Gone` | モデルが提供終了です。`LLM_MODEL` で別のモデルを選びます |
| NIM から `403 Forbidden` | そのキーでは推論を実行できません。build.nvidia.com で新しいキーを作成します |
| `ReadTimeout` または `SocketTimeoutError` | ホスト型のレイテンシが原因です。`LLM_TIMEOUT` を上げます（例: 600） |
| 返信が `Here's a thinking process` で始まる | `LLM_ENABLE_THINKING=false` を設定します |
| LM Studio の `n_keep >= n_ctx` | コンテキスト長 16384 以上でモデルをロードします |
| LM Studio でモデルが一覧に出ない | ロードします: `lms load <model> --context-length 32768` |
