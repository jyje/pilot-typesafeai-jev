<div align="center">

# jyje/pilot-typesafeai-jev

<img width="280" src="https://raw.githubusercontent.com/jyje/pilot-typesafeai-jev/main/docs/images/typesafe-logo-light.png#gh-light-mode-only" alt="TypeSafe AI" title="TypeSafe AI"/>
<img width="280" src="https://raw.githubusercontent.com/jyje/pilot-typesafeai-jev/main/docs/images/typesafe-logo-dark.png#gh-dark-mode-only" alt="TypeSafe AI" title="TypeSafe AI"/>

🚀 TypeSafe AI の **Jev** を LangGraph と Deep Agents に組み込むパイロットプロジェクト（ChatGPT、NVIDIA NIM、LM Studio に対応）

[![GitHub Repo stars](https://img.shields.io/github/stars/jyje/pilot-typesafeai-jev?style=social)](https://github.com/jyje/pilot-typesafeai-jev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.13-blue)](https://www.python.org)
[![TypeSafe AI](https://img.shields.io/badge/Model-TypeSafe%20AI%20Jev-black)](https://docs.typesafe.ai/introduction/quickstart)
[![ChatGPT](https://img.shields.io/badge/Inference-ChatGPT-10A37F)](docs/02-inference-layer-ja.md)
[![NVIDIA NIM](https://img.shields.io/badge/Inference-NVIDIA%20NIM-76B900)](https://build.nvidia.com)
[![LM Studio](https://img.shields.io/badge/Inference-LM%20Studio-5B5BD6)](https://lmstudio.ai)

[English](README.md) / [한국어](README-ko.md) / [日本語](README-ja.md) / [简体中文](README-zh-CN.md) / [Docs](docs/README.md)

---

**お役に立てたら、ぜひ ⭐ をお願いします。ほかの方が見つけやすくなります。**

</div>

## このパイロットの目標

TypeSafe AI の [Jev](https://docs.typesafe.ai/concepts/system-one) を LangGraph と Deep Agents に実際に組み込み、
何ができて何ができないかを記録します。

1. **Jev を理解する。** 生成テキストの代わりに、確率付きの型付きの答え（`Choice`、`Score`、`Noul`）を返し、
   すべての答えに信頼度が付きます。[Jev の概要](docs/01-jev-overview-ja.md)を参照してください。
2. **役割分担を示す。** ワークフローはコードが握り、素早い判断は Jev が担当し、返信の文章は引き続きチャットモデルが書きます。
3. **LangGraph で Jev を使ってルーティングする（Case 01）。** 1 回のリクエストで 3 つの質問を投げ、コードがルートを決め、
   `answer` ルートだけがチャットモデルのトークンを使います。
4. **Deep Agents で Jev を使って守り、検証する（Case 02）。** ガードレールのミドルウェアがエージェント開始前にメッセージを選別し、
   `verify_claim` ツールが信頼度付きの判定を返します。[ケース](docs/03-cases-ja.md)を参照してください。
5. **検証する。** 単体テスト、実サービスに対するスクリプト、実行済みノートブックで確認し、測定結果、失敗例、注意点を公開します。
   [検証](docs/05-verification-ja.md)を参照してください。

このパイロットが目指さないもの:

- Jev の精度を測るベンチマーク。しきい値は調整していない出発点です。
- 本番用コード。
- ChatGPT サブスクリプションのプロバイダは実験的で非公式のため、安定した統合ではありません。

## 2 つのケース

Case 01 と Case 02 を一目で確認します。

```mermaid
flowchart LR
    subgraph C1["Case 01 · LangGraph ルーター"]
        direction LR
        m1([メッセージ]) --> t["triage<br/>Jev を 1 回呼び出し"]
        t -->|明確で穏やか| a["answer<br/>チャットモデル"]
        t -->|緊急| e[escalate]
        t -->|不明確| r[review]
        t -->|インジェクション| f[refuse]
    end
```

```mermaid
flowchart LR
    subgraph C2["Case 02 · Deep Agent"]
        direction LR
        m2([メッセージ]) --> g{"Jev ガードレール"}
        g -->|ブロック| f2[refuse]
        g -->|OK| ag["エージェント + チャットモデル"]
        ag <-->|verify_claim| j["Jev の判定"]
    end
```

チャットモデルは **ChatGPT サブスクリプション**（1）、**NVIDIA NIM**（2）、**LM Studio**（3）のいずれかで動作します。`LLM_PROVIDER` を設定するか、未設定のままにすると、設定済みのもののうち先頭のものが使われます。

## クイックスタート

```bash
cp .env.sample .env        # TYPESAFE_API_KEY を追加。NIM を使う場合は NVIDIA_API_KEY も追加
cd src && uv sync

uv run python doctor.py                    # キー、Jev、チャットモデルを確認
uv run python -m case01_routing.main       # サンプルメッセージで Case 01 を実行
uv run python -m case02_deepagents.main    # サンプルリクエストで Case 02 を実行
uv run pytest                              # オフラインテスト（キー不要）
```

## ドキュメント

| ドキュメント | 内容 |
| --- | --- |
| [Jev の概要](docs/01-jev-overview-ja.md) | Jev が何を返すか、どう問い合わせるか |
| [推論レイヤー](docs/02-inference-layer-ja.md) | ChatGPT、NVIDIA NIM、LM Studio を 1 つのファクトリーで切り替え |
| [ケース](docs/03-cases-ja.md) | 2 つのケースのグラフ図とシーケンス図 |
| [はじめに](docs/04-getting-started-ja.md) | セットアップ、環境変数、ノートブック、LangGraph Studio |
| [検証](docs/05-verification-ja.md) | テスト内容、結果、注意点 |

進捗とスコープは [PLAN.md](PLAN.md)、エージェント向けコンテキストは [AGENTS.md](AGENTS.md) をご覧ください。

## ライセンス

[MIT](LICENSE)
