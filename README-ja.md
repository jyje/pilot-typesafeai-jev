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

## これは何か

[Jev](https://docs.typesafe.ai/concepts/system-one) はテキストを読み取り、生成したテキストではなく**確率付きの型付きの答え**を返します。ワークフローの制御はコードが握り、素早い判断は Jev が担当し、返信の文章は引き続きチャットモデルが書きます。

このリポジトリでは Jev を次の 2 か所に組み込み、その結果を記録しています。

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

| | |
| --- | --- |
| [Jev の概要](docs/01-jev-overview-ja.md) | Jev が何を返すか、どう問い合わせるか |
| [推論レイヤー](docs/02-inference-layer-ja.md) | ChatGPT、NVIDIA NIM、LM Studio を 1 つのファクトリーで切り替え |
| [ケース](docs/03-cases-ja.md) | 2 つのケースのグラフ図とシーケンス図 |
| [はじめに](docs/04-getting-started-ja.md) | セットアップ、環境変数、ノートブック、LangGraph Studio |
| [検証](docs/05-verification-ja.md) | テスト内容、結果、注意点 |

進捗とスコープは [PLAN.md](PLAN.md)、エージェント向けコンテキストは [AGENTS.md](AGENTS.md) をご覧ください。

## ライセンス

[MIT](LICENSE)
