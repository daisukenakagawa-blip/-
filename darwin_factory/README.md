# 🧬 Darwin Factory — 事業に自然選択をかける工場

構想は [`../DARWIN_FACTORY.md`](../DARWIN_FACTORY.md) を参照。
このディレクトリはその実装です。

## 仕組み

```
[LP公開]  sites/ の事前登録LPが GitHub Pages で公開される
    ↓
[観測]    Google フォームへの事前登録数を毎週自動集計
    ↓
[判定]    30日観測して基準未達なら「撤退勧告」、達成なら「生存(倍賭け)」
    ↓
[成績表]  毎週月曜 09:00 JST、reports/ に自動コミットされる
```

- **`ventures.json`** — 事業台帳。全事業の状態・観測基準・フォームURLを管理
- **`factory.py`** — 観測・淘汰エンジン(report / launch / cull / promote)
- **`build_sites.py`** — LP にフォーム URL を注入して公開用にビルド
- **`sites/`** — 第1期生のLP(agent-tools / jdm-export / cancel-watch)
- **`reports/`** — 週次成績表(自動生成)

## セットアップ(あなたがやること、合計30分・1回だけ)

### ① Google フォームを3つ作る(各3分)

各事業の事前登録フォーム。質問は最小限でいい:

| 事業 | 質問 |
|---|---|
| agent-tools | メールアドレス / 何のエージェントを作っているか(任意) |
| jdm-export | Email / What chassis are you hunting?(任意) |
| cancel-watch | メールアドレス / どの施設を監視してほしいか(必須・自由記述) |

作ったら「送信」ボタン → リンクをコピー。

### ② 回答シートを「ウェブに公開(CSV)」にする(各2分)

1. フォームの「回答」タブ → スプレッドシートに出力
2. スプレッドシートの「ファイル」→「共有」→「ウェブに公開」
3. 対象シートを選び、形式を **CSV** にして公開 → URL をコピー

(topics.csv のスプレッドシート連携と同じ手順です)

### ③ `ventures.json` に URL を貼って観測開始

各事業の `form_url`(①のリンク)と `signup_csv_url`(②のURL)を埋めてコミット。
その後:

```bash
python darwin_factory/factory.py launch agent-tools
python darwin_factory/factory.py launch jdm-export
python darwin_factory/factory.py launch cancel-watch
```

### ④ GitHub Pages を有効化(2分)

リポジトリの **Settings → Pages → Source を「GitHub Actions」** に設定。
以後、LP の変更は自動で公開される。

### ⑤ 週次レポートの cron について

`.github/workflows/darwin_factory_report.yml` の schedule は
**デフォルトブランチでのみ動きます**。このブランチをマージするか、
それまでは Actions タブから手動実行(Run workflow)してください。

## 運用(あなたの仕事は月1回・5分)

毎週月曜に `reports/report-YYYY-MM-DD.md` が自動コミットされる。月1回それを見て:

- **撤退勧告** が出ていたら → `python factory.py cull <id> --reason "..."`(感情は挟まない)
- **生存判定** が出ていたら → `python factory.py promote <id>` して、その事業の実装を本格化
- 空いた枠には次の種(新事業のLP)をまく

## 工場の掟

1. 撤退は機械的に。人間が事業に情をかけた時点で工場は壊れる。
2. 観測期間中はLPをいじらない。数字の比較ができなくなる。
3. 集客ゼロでは観測にならない。LP公開後、`auto_video_uploader` での動画導線や
   SNS投稿など、最低限のトラフィックを流すこと(各事業とも月100アクセスが目安)。
