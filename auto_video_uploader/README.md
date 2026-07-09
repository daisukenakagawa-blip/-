# auto_video_uploader

テーマ一覧 (topics.csv) から **動画生成 → サムネイル生成 → YouTube アップロード → 投稿ログ保存** までを完全自動で行うツールです。

- YouTube Shorts 用の縦動画 **1080x1920 / 30〜60秒**
- 日本語ナレーション + 日本語テロップ + BGM(任意)
- 予約投稿対応(topics.csv の date が未来日なら自動で予約投稿)
- 同じテーマの重複投稿防止(uploaded_log.csv を参照)
- 途中で失敗しても再実行で続きから処理(台本・音声・動画はファイル単位で再利用)
- **TikTok / Instagram Reels / X への同時クロス投稿に対応**(1本の動画を4媒体へ)
- **説明欄への収益リンク自動挿入**(アフィリエイト・LINE 誘導など。PR 表記も自動)

ジャンル例: ジャグラー予想、スロット分析、店舗傾向分析(「明日の狙い台TOP5」など)

---

## Windows の方へ: ダブルクリックだけで使えます

コマンド操作が不要な自動セットアップ用の bat ファイルを同梱しています。番号順にダブルクリックするだけです。

| ファイル | やること |
|---|---|
| `①セットアップ.bat` | Python・FFmpeg・必要部品を全部自動インストール(最初に1回) |
| `②動画を作る.bat` | 動画を1本自動生成して videos フォルダを開く(アップロードなし) |
| `③YouTube認証.bat` | YouTube との連携認証(最初に1回。事前に client_secret.json が必要 → 下の「YouTube API 認証の手順」参照) |
| `④アップロード実行.bat` | 動画作成 → YouTube 投稿まで全自動 |
| `⑤かんたん設定.bat` | AI台本用APIキー・スマホ連携用スプレッドシートURLを貼るだけで設定 |
| `⑥毎日自動実行を設定.bat` | 毎日決まった時刻に④を自動実行(タスクスケジューラ登録) |
| `⑦毎日自動実行を解除.bat` | ⑥の解除 |

※ 実行時に「WindowsによってPCが保護されました」と出た場合は「詳細情報」→「実行」をクリックしてください。

---

## スマホからテーマを追加する(Google スプレッドシート連携)

1. PC で https://sheets.google.com を開き「新しいスプレッドシート」を作成
2. 1行目に見出しを入力: `date` `topic` `platform` `status`(A1〜D1)
3. 2行目以降にテーマを入力(platform は `youtube`、status は `pending`)
4. メニュー「ファイル」→「共有」→「**ウェブに公開**」
   - 対象シートを選択し、形式を「**カンマ区切り形式 (.csv)**」にして「公開」
   - 表示された URL をコピー
5. `⑤かんたん設定.bat` をダブルクリックして URL を貼り付け

以降は **スマホの Google スプレッドシートアプリでシートに行を足すだけ**。次回実行時に自動で取り込まれ、`⑥毎日自動実行を設定.bat` と組み合わせれば「スマホでネタを書く → PC が毎日自動投稿」が完成します(実行時刻に PC の電源が入っている必要があります)。

## クラウド完全自動運用(PC不要・スマホだけで運用)

GitHub Actions (`.github/workflows/auto_upload.yml`) により、**毎日 08:00 JST にクラウド上で動画生成 → YouTube 投稿**が自動実行されます。PC の電源は不要です。

```
スマホでスプレッドシートにテーマを書く
  → クラウドが 台本AI生成 / VOICEVOX音声 / 背景動画自動取得 / テロップ / 合成 / 投稿
```

### 一度だけ必要な設定

1. GitHub のリポジトリページ → **Settings → Secrets and variables → Actions → New repository secret** で以下を登録:

| Secret 名 | 中身 | 必須 |
|---|---|---|
| `YOUTUBE_CLIENT_SECRET` | client_secret.json をメモ帳で開いた中身(全文) | ✅ |
| `YOUTUBE_TOKEN` | token.json をメモ帳で開いた中身(全文) | ✅ |
| `TOPICS_SHEET_URL` | スプレッドシートの「ウェブに公開(CSV)」URL | 推奨 |
| `ANTHROPIC_API_KEY` | 台本の AI 生成用 | 任意 |
| `PEXELS_API_KEY` | 背景動画の自動取得用 (https://www.pexels.com/api/ で無料発行) | 任意 |

2. **Google Cloud Console → OAuth 同意画面 → 「アプリを公開」**(公開ステータスを「本番環境」に)。
   テスト状態のままだと認証が**7日で失効**し、クラウド実行が止まります。
3. ワークフローはリポジトリの**デフォルトブランチ**に置く必要があります(スケジュール実行の仕様)。

### スマホでの操作

- テーマ追加: Google スプレッドシートアプリで行を足すだけ
- 今すぐ実行: GitHub アプリ → リポジトリ → Actions → auto-video-upload → **Run workflow**
- 結果確認: 同じ画面で実行ログ閲覧可 / 失敗時は GitHub から通知メール

### 背景動画をスマホから変更する(シートの background 列)

シートの 5 列目に `background` という見出しを追加すると、背景動画を指定できます。

1. 縦型の動画ファイルを **Google ドライブ**にアップロード(スマホのドライブアプリでOK)
2. その動画を「共有」→ アクセスを「**リンクを知っている全員**」に変更 → リンクをコピー
3. シートの `background` 列に貼り付け

**一度貼ると、それ以降の行(動画)にも同じ背景が使われます。** 変えたいときは新しい行の `background` 列に別のリンクを貼るだけ。空欄に戻したい場合はリポジトリの `assets/` 運用または Pexels 自動取得が使われます。短い動画でもループ再生されるので 10〜30 秒の素材で十分です。

### BGM もスマホから変更できる(シートの bgm 列)

`bgm` という見出しの列に、音楽ファイル (mp3 等) の Google ドライブ共有リンクを貼ると BGM として動画にミックスされます(background と同じ「一度貼れば以降も適用」方式)。フリーBGMは [DOVA-SYNDROME](https://dova-s.jp/) などからダウンロードし、ドライブに上げて共有リンクを貼ってください。
※YouTube アプリの「音楽を追加」機能は API からは使用できないため、動画への埋め込み方式です。

## 動画クオリティ改善機能 (ランキング構成 + 自動品質チェック)

生成台本は YouTube Shorts 向けの**ランキング構成**でレンダリングされます。

```
0-2秒 フック → 第3位 → 第2位 → 第1位 → 注意台 → まとめ (40〜45秒)
```

- 冒頭2秒に強いフック(中央に大きく表示)
- テロップは短く・大きく・**数字は黄色で自動強調**
- **台番・REG・合算・本命/対抗/見送り**をデータカードで強調表示
- セグメントごとに音声を分割合成し、バナー・テロップ・**切替効果音**をナレーションに正確同期(`assets/se.mp3` で差し替え可)
- BGM はナレーションより必ず小さくミックス
- サムネイルは固定テンプレート(赤帯+タイトル+バッジ+黄帯)
- **完成後に自動品質チェック**(冒頭の強さ/テロップ/情報量/画面変化/音声/サムネの6基準・100点満点)
- `QUALITY_MIN_SCORE`(既定80)未満なら原因を `logs/quality_log.txt` に記録し、課題をAIにフィードバックして**自動で再生成**(上限 `QUALITY_MAX_RETRIES` 回)

※再生成による自動改善は AI 台本生成(`ANTHROPIC_API_KEY`)が有効な場合に働きます。`RANKING_MODE=0` で従来の台本構成に戻せます。

## 動画の品質を上げる

| やること | 効果 |
|---|---|
| `⑤かんたん設定.bat` で Anthropic API キーを設定 | 台本がテンプレートではなく AI 生成になる(効果大) |
| [VOICEVOX](https://voicevox.hiroshiba.jp/) をインストールして起動しておく | ナレーションが自然な声になる(起動中なら自動で使用) |
| `assets/background.mp4` を置く | 背景が実写・動画素材になる(静止画は自動でズーム演出) |
| `assets/bgm.mp3` を置く | BGM が自動でミックスされる |

---

## ファイル構成

```
auto_video_uploader/
├── main.py                  # エントリポイント(パイプライン全体の制御)
├── config.py                # 設定(.env を読み込む)
├── requirements.txt
├── .env.example             # 環境変数のテンプレート(コピーして .env を作る)
├── topics.csv               # 動画テーマ一覧
├── uploaded_log.csv         # アップロード済みログ(自動追記)
├── videos/                  # 完成動画 (mp4)
├── thumbnails/              # サムネイル (jpg)
├── audio/                   # ナレーション音声 (wav/mp3)
├── scripts/                 # 生成した台本 (json)
├── assets/                  # 背景素材 (background.mp4/png/jpg)・BGM (bgm.mp3)
├── logs/                    # app.log / error_log.txt
└── modules/
    ├── script_generator.py    # タイトル・台本・説明文・ハッシュタグ生成 (Claude API / テンプレート)
    ├── voice_generator.py     # 音声合成 (VOICEVOX / gTTS)
    ├── video_editor.py        # FFmpeg で動画合成 (背景+テロップ+ナレーション+BGM)
    ├── thumbnail_generator.py # Pillow でサムネイル生成
    ├── youtube_uploader.py    # YouTube Data API v3 アップロード
    ├── platform_base.py       # プラットフォーム共通の抽象クラス(拡張ポイント)
    └── logger.py              # ログ・アップロード履歴管理
```

---

## 1. セットアップ手順

### 1-1. 必要なもの

- Python 3.10 以上
- FFmpeg(ffprobe 含む)
- 日本語フォント(テロップ・サムネイル用)

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install -y ffmpeg fonts-noto-cjk

# macOS (Homebrew)
brew install ffmpeg
# macOS は FONT_PATH を例えば /System/Library/Fonts/ヒラギノ角ゴシック W6.ttc に変更
```

### 1-2. Python パッケージ

```bash
cd auto_video_uploader
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 1-3. 環境変数

```bash
cp .env.example .env
```

`.env` を編集します。**最小構成では何も設定しなくても動きます**(台本はテンプレート、音声は gTTS)。

| 変数 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | 設定すると Claude API で高品質な台本を自動生成(任意) |
| `TTS_ENGINE` | `gtts`(デフォルト・APIキー不要)or `voicevox`(要ローカルエンジン・高品質) |
| `FONT_PATH` / `FONT_NAME` | 日本語フォント。Ubuntu の `fonts-noto-cjk` ならデフォルトのままでOK |
| `PRIVACY_STATUS` | 即時投稿時の公開設定(`public` / `unlisted` / `private`) |
| `PUBLISH_TIME` / `TIMEZONE` | 予約投稿の時刻(デフォルト 19:00 JST) |

### 1-4. 素材(任意)

- `assets/background.mp4`(または `.png` / `.jpg`)を置くと背景に使用。無ければグラデーション背景を自動生成。
- `assets/bgm.mp3` を置くと自動で BGM をミックス(音量は `BGM_VOLUME`)。

---

## 2. YouTube API 認証の手順

1. [Google Cloud Console](https://console.cloud.google.com/) で新規プロジェクトを作成
2. 「APIとサービス → ライブラリ」で **YouTube Data API v3** を検索して **有効化**
3. 「APIとサービス → OAuth 同意画面」を設定
   - User Type: **外部** → アプリ名・メールを入力して保存
   - スコープは追加不要。「テストユーザー」に自分の Google アカウントを追加
4. 「APIとサービス → 認証情報 → 認証情報を作成 → **OAuth クライアント ID**」
   - アプリケーションの種類: **デスクトップアプリ**
5. 作成したクライアント ID の JSON をダウンロードし、`auto_video_uploader/client_secret.json` として保存
6. 初回認証を実行:

```bash
python main.py --auth-only
```

ブラウザが開くので Google アカウントでログインして許可すると、`token.json` が保存されます。以降は自動でリフレッシュされます。

> **注意**
> - `client_secret.json` / `token.json` / `.env` は `.gitignore` 済み。絶対にコミットしないこと。
> - サムネイル設定にはチャンネルの**電話番号認証**(YouTube Studio → 設定 → チャンネル → 機能の利用資格)が必要です。未認証でも動画アップロード自体は成功します。
> - 未審査の OAuth アプリは `token.json` が7日で失効します(その場合は `--auth-only` で再認証)。

---

## 3. 実行コマンド

```bash
# pending の先頭 1 件を処理(台本→音声→動画→サムネ→アップロード)
python main.py

# pending を全件処理
python main.py --all

# アップロードせず動画生成までテスト(YouTube 認証不要)
python main.py --no-upload

# topics.csv を使わず単発生成
python main.py --topic "明日の狙い台TOP5" --date 2026-06-20

# YouTube の認証のみ
python main.py --auth-only
```

### 毎日自動実行する(cron)

```bash
crontab -e
# 毎日 朝 8:00 に 1 件処理
0 8 * * * cd /path/to/auto_video_uploader && /path/to/.venv/bin/python main.py >> logs/cron.log 2>&1
```

---

## 4. topics.csv のサンプル

```csv
date,topic,platform,status
2026-06-13,エスパス上野本館の明日の狙い台TOP5,youtube,pending
2026-06-14,この店のジャグラーのクセを徹底分析,youtube,pending
2026-06-15,設定が入りやすい末尾の見抜き方,youtube,pending
```

- `date` … 投稿予定日。**未来日なら自動的に予約投稿**(`PUBLISH_TIME` の時刻、`privacyStatus=private` + `publishAt`)。当日・過去日なら即時投稿。予約投稿に対応するのは YouTube のみで、他媒体は処理時に即時投稿される。
- `platform` … `youtube` / `tiktok` / `instagram` / `x`。`youtube+tiktok` のような複数指定や `all`(4媒体全部)も可。`.env` の `CROSS_POST_PLATFORMS` に書けば列に書かなくても毎回クロス投稿される。
- `status` … `pending` のものだけ処理され、全媒体に成功すると `done` に自動更新。一部の媒体だけ失敗した場合は `pending` のまま残り、**再実行すると失敗した媒体だけ**リトライされる。

> Google Sheets を使う場合は「ファイル → ダウンロード → CSV」で `topics.csv` として保存するか、`gspread` 等で同形式の CSV を書き出してください(読み込み口は `main.py` の `load_topics()` に集約してあります)。

---

## 5. 処理の流れと再実行設計

```
topics.csv 読込
  → 重複チェック (uploaded_log.csv)
  → 台本生成    scripts/{date}_{hash}.json   ← 存在すれば再利用
  → 音声生成    audio/{date}_{hash}.mp3/wav  ← 存在すれば再利用
  → 動画合成    videos/{date}_{hash}.mp4     ← 存在すれば再利用
  → サムネ生成  thumbnails/{date}_{hash}.jpg
  → アップロード (YouTube Data API v3, resumable + リトライ)
  → uploaded_log.csv 追記 / topics.csv の status を done に更新
```

- 失敗したテーマは `status=pending` のまま残るため、**再実行すれば自動でリトライ**されます。
- 各中間生成物はテーマごとに一意なファイル名(日付+ハッシュ)で保存され、成功済みステップはスキップされます。

---

## 6. エラー時の対処法

エラーは `logs/error_log.txt` に記録されます。

| 症状 | 原因と対処 |
|---|---|
| `client_secret.json が見つかりません` | 「YouTube API 認証の手順」の 5 を実施 |
| `invalid_grant` / 認証エラー | `token.json` を削除して `python main.py --auth-only` で再認証 |
| `quotaExceeded` | YouTube API の1日クォータ(デフォルト10,000、動画1本=1,600)超過。翌日(太平洋時間 0:00 リセット)に再実行 |
| `uploadLimitExceeded` | チャンネルの1日のアップロード上限。時間を空けて再実行 |
| ffmpeg / ffprobe が見つからない | `sudo apt install ffmpeg` 等でインストールし、PATH を確認 |
| テロップ・サムネの日本語が□(豆腐)になる | 日本語フォント未導入。`sudo apt install fonts-noto-cjk` 後、`.env` の `FONT_PATH` / `FONT_NAME` を確認 |
| gTTS で `Failed to connect` | ネットワーク必須。プロキシ環境なら `HTTPS_PROXY` を設定、または VOICEVOX に切替 |
| VOICEVOX 接続エラー | VOICEVOX エンジンを起動(デフォルト `http://127.0.0.1:50021`)。失敗時は自動で gTTS にフォールバック |
| Claude API エラー | `ANTHROPIC_API_KEY` を確認。失敗時は自動でテンプレート台本にフォールバック |
| サムネイル設定失敗の警告 | チャンネルの電話番号認証が未完了。動画はアップロード済みなので手動設定も可 |
| 同じテーマが再投稿されない | 仕様(重複防止)。再投稿したい場合は `uploaded_log.csv` から該当行を削除 |

---

## 7. 収益を伸ばす: マルチ投稿 & 収益リンク

**同じ1本の動画を YouTube / TikTok / Instagram Reels / X の4媒体に自動投稿**できます。制作コストはそのままで露出とフォロワー獲得のチャンスが4倍になり、各媒体の収益化プログラム(YouTube パートナープログラム、TikTok の報酬プログラム等)への到達も早まります。詳しい戦略は [docs/収益化ガイド.md](docs/収益化ガイド.md) を参照してください。

### 7-1. 説明欄に収益リンクを自動挿入する(最短で収益を作る)

チャンネル収益化の条件(登録者数など)を満たす**前**でも、説明欄のリンクからは収益が発生します。

1. `links.txt.example` をコピーして `links.txt` を作成
2. アフィリエイトリンク(A8.net・もしもアフィリエイト等で無料発行)や LINE 公式アカウントの URL を 1 行 1 件で書く

```
LINEで狙い台情報を配信中|https://lin.ee/xxxxxxx
おすすめポイ活アプリ (無料)|https://px.a8.net/svt/ejp?a8mat=XXXXXXXX
```

以降の投稿すべての説明欄に自動で挿入されます(景表法のステマ規制に対応した PR 表記も自動付与)。GitHub Actions 運用の場合は `links.txt` をコミットするか、Secret `MONETIZE_LINKS` に同じ内容を設定してください。

### 7-2. クロス投稿を有効にする

`.env`(Actions なら Variables)に投稿したい媒体を書くだけです。認証情報が必要なのは使う媒体だけです。

```
CROSS_POST_PLATFORMS=tiktok,instagram,x
```

行単位で指定したい場合は `topics.csv` / スプレッドシートの `platform` 列に `youtube+tiktok` や `all` と書きます。

### 7-3. TikTok に自動投稿する

1. [TikTok for Developers](https://developers.tiktok.com/) でアプリを作成し、**Content Posting API** を追加(`video.upload` スコープ)
2. OAuth 認可を一度行い、リフレッシュトークンを取得
3. `.env` / Secrets に `TIKTOK_CLIENT_KEY` `TIKTOK_CLIENT_SECRET` `TIKTOK_REFRESH_TOKEN` を設定

既定の `TIKTOK_POST_MODE=inbox` では動画がスマホの TikTok アプリの**受信箱に下書きとして届き、通知から数タップで公開**できます(未監査アプリでも公開投稿にできる方式)。TikTok の監査を通過したアプリなら `direct` + `TIKTOK_PRIVACY=PUBLIC_TO_EVERYONE` で完全自動公開も可能です。

### 7-4. Instagram Reels に自動投稿する

1. Instagram アプリで**プロアカウント**(無料)に切り替え、Facebook ページと連携
2. [Meta for Developers](https://developers.facebook.com/) でアプリを作成し、`instagram_content_publish` 権限付きの長期アクセストークンと IG ユーザー ID を取得
3. `.env` / Secrets に `IG_USER_ID` `IG_ACCESS_TOKEN` を設定

Graph API の仕様上、動画は公開 URL 経由で渡す必要があるため、24時間で自動削除される一時ホスティング(litterbox)を経由します。自前のストレージがある場合は `PUBLIC_VIDEO_BASE_URL` を設定してください。

### 7-5. X (旧 Twitter) に自動投稿する

1. [X Developer Portal](https://developer.x.com/) で **Free プラン**に登録しアプリを作成
2. アプリの権限を「Read and write」に変更
3. API Key / API Key Secret / Access Token / Access Token Secret を発行し、`.env` / Secrets に `X_API_KEY` `X_API_SECRET` `X_ACCESS_TOKEN` `X_ACCESS_TOKEN_SECRET` を設定

投稿文はタイトル+ハッシュタグ(280字以内に自動調整)になります。

### 7-6. その他の媒体への拡張

アップロード処理は `modules/platform_base.py` の `BaseUploader` で抽象化されています。新しい媒体は `upload()` を実装したクラスを作り、`get_uploader()` に分岐を1行追加するだけで追加できます。媒体ごとに尺やアスペクト比を変えたい場合は `.env` の `VIDEO_WIDTH` / `VIDEO_HEIGHT` / `TARGET_MAX_SEC` を切り替えてください。

---

## 免責

本ツールが生成する動画は予想・考察コンテンツです。生成される説明文には自動で免責文言が挿入されますが、各プラットフォームの規約・法令(景品表示法等)の遵守は利用者の責任で行ってください。
