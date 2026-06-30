# x_auto_poster

テーマ一覧 (topics.csv) から **投稿文をAI生成 → 画像を添付 → X(旧Twitter)へ投稿 → 投稿ログ保存** までを自動で行うツールです。

- 投稿文は **Claude API** で毎回自動生成(未設定でもテンプレートで動く)
- `assets/images` フォルダの画像をランダムに添付
- **毎日決まった時刻に自動投稿**(Windows のタスクスケジューラに登録)
- 同じテーマの重複投稿を防止(`posted_log.csv` を参照)
- スマホから Google スプレッドシートでテーマを追加できる(任意)

ジャンル例: ジャグラー予想、スロット分析、店舗傾向の情報共有など(`POST_PERSONA` で業種を変更可能)

---

## Windows の方へ: ダブルクリックだけで使えます

番号順にダブルクリックするだけです。

| ファイル | やること |
|---|---|
| `①セットアップ.bat` | Python・必要部品を自動インストールし `.env` を用意(最初に1回) |
| `②かんたん設定.bat` | X のキーや Claude API キーを貼り付けるだけで設定 |
| `③X接続テスト.bat` | X と正しく繋がっているか確認(投稿はしない) |
| `④今すぐ投稿テスト.bat` | 投稿せず、生成される下書きをプレビュー表示 |
| `⑤今すぐ1回投稿.bat` | 実際に1回 X へ投稿(本番) |
| `⑥毎日自動投稿を設定.bat` | 毎日決まった時刻に自動投稿(タスクスケジューラ登録) |
| `⑦毎日自動投稿を解除.bat` | ⑥の解除 |

※「WindowsによってPCが保護されました」と出たら「詳細情報」→「実行」を押してください。

おすすめの手順: **① → ② → ③ → ④(下書き確認) → ⑤(試し投稿) → ⑥(毎日自動化)**

---

## X API キーの取得手順(最初に1回)

自動投稿には X の API キーが必要です。

1. https://developer.x.com/ にログインし、開発者アカウントを作成
2. アプリ(Project / App)を作成
3. アプリ設定の **User authentication settings** を開き、権限を
   **「Read and write」** に変更(ここが Read only だと投稿できません)
4. **Keys and tokens** タブで以下の4つを発行・コピー
   - API Key(= Consumer Key)
   - API Key Secret(= Consumer Secret)
   - Access Token
   - Access Token Secret
5. `②かんたん設定.bat` を実行し、4つを順番に貼り付ける

> 注意: 権限を「Read and write」に変えた **後に** Access Token を再発行してください。
> 先に発行したトークンは読み取り専用のままで、投稿が 403 エラーになります。

---

## スマホからテーマを追加する(Google スプレッドシート連携・任意)

1. PC で https://sheets.google.com を開き新しいスプレッドシートを作成
2. 1行目(A1)に見出し `topic` を入力
3. 2行目以降に投稿テーマを入力(例:「今日のジャグラー狙い目の考え方」)
4. メニュー「ファイル」→「共有」→「**ウェブに公開**」
   - 対象シートを選び、形式を「**カンマ区切り形式 (.csv)**」にして「公開」
5. 表示された URL を `②かんたん設定.bat` の最後の項目に貼り付ける

以後はスマホでシートに行を足すだけで、次の自動投稿から反映されます。

---

## 仕組み(処理の流れ)

1. (設定があれば)スプレッドシートから `topics.csv` を更新
2. `topics.csv` のうち、まだ投稿していないテーマを選ぶ
3. Claude API で投稿文を生成(未設定ならテンプレート)
4. `assets/images` から画像を1枚ランダムに選んで添付
5. X へ投稿し、結果を `posted_log.csv` に記録

テーマを全部使い切ると、`RECYCLE_TOPICS=1` の場合は履歴をリセットして最初から使い回します。

---

## ファイル構成

```
x_auto_poster/
  main.py                 … 実行の入口
  config.py               … 設定(.env から読み込み)
  modules/
    tweet_generator.py    … 投稿文の生成(Claude API / テンプレート)
    x_client.py           … X への投稿(tweepy)
    logger.py             … ログと投稿履歴
  topics.csv              … 投稿テーマ一覧(ここを編集 or スマホ連携)
  assets/images/          … 添付したい画像を入れるフォルダ
  posted_log.csv          … 投稿履歴(自動生成)
  logs/                   … 動作ログ
  .env.example            … 設定の見本(②かんたん設定.bat が .env を作成)
```

---

## 主な設定項目(.env)

| 項目 | 説明 |
|---|---|
| `X_API_KEY` ほか3つ | X の API 認証情報(必須) |
| `ANTHROPIC_API_KEY` | Claude API キー。未設定でもテンプレートで動作 |
| `POST_PERSONA` | 発信アカウントのテイスト(プロンプトに反映) |
| `MAX_TWEET_CHARS` | 本文の文字数上限(全角換算の目安。既定130) |
| `POSTS_PER_RUN` | 1回の実行で投稿する本数(既定1) |
| `ATTACH_IMAGE` | 画像を添付するか(1=する / 0=テキストのみ) |
| `RECYCLE_TOPICS` | テーマを使い切ったら使い回すか(1=する) |
| `TOPICS_SHEET_URL` | スマホ連携用スプレッドシートの公開CSV URL |
| `DRY_RUN` | 1にすると投稿せずプレビューのみ |

---

## コマンドで使う場合(上級者向け)

```bash
pip install -r requirements.txt
cp .env.example .env   # 値を埋める

python main.py             # 設定本数だけ投稿
python main.py --dry-run   # 投稿せず内容だけ確認
python main.py --test      # X への接続テスト
python main.py --count 2   # 本数を指定して投稿
```

---

## 注意

- 投稿内容はあくまで予想・考察・情報共有としてください。結果を保証する表現は避けます。
- X のAPI無料枠には投稿数の上限があります。短時間の大量投稿は避けてください。
- `.env` と `posted_log.csv`、`assets/images` の中身は Git にコミットされません(`.gitignore` 済み)。
