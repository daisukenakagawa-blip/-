# auto_video_uploader

テーマ一覧 (topics.csv) から **動画生成 → サムネイル生成 → YouTube アップロード → 投稿ログ保存** までを完全自動で行うツールです。

- YouTube Shorts 用の縦動画 **1080x1920 / 30〜60秒**
- 日本語ナレーション + 日本語テロップ + BGM(任意)
- 予約投稿対応(topics.csv の date が未来日なら自動で予約投稿)
- 同じテーマの重複投稿防止(uploaded_log.csv を参照)
- 途中で失敗しても再実行で続きから処理(台本・音声・動画はファイル単位で再利用)
- TikTok / Instagram Reels / X へ拡張できる抽象設計(`modules/platform_base.py`)

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

- `date` … 投稿予定日。**未来日なら自動的に予約投稿**(`PUBLISH_TIME` の時刻、`privacyStatus=private` + `publishAt`)。当日・過去日なら即時投稿。
- `platform` … 現状は `youtube`。将来 `tiktok` / `instagram` / `x` を追加予定。
- `status` … `pending` のものだけ処理され、成功すると `done` に自動更新。

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

## 7. TikTok / Instagram / X への拡張方法

アップロード処理は `modules/platform_base.py` の `BaseUploader` で抽象化されています。拡張は3ステップ:

1. `modules/tiktok_uploader.py` を作成し、`BaseUploader` を継承して `upload()` を実装
   - TikTok: [Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started/)(Direct Post)
   - Instagram Reels: [Instagram Graph API](https://developers.facebook.com/docs/instagram-api/guides/content-publishing)(ビジネスアカウント必須・動画は公開URL経由)
   - X: [v2 media upload + POST /2/tweets](https://docs.x.com/x-api)
2. `platform_base.py` の `get_uploader()` に分岐を1行追加
3. `topics.csv` の `platform` 列に `tiktok` 等を指定

動画生成部分(台本・音声・合成・サムネ)はそのまま共通で使えます。プラットフォームごとに尺やアスペクト比を変えたい場合は `.env` の `VIDEO_WIDTH` / `VIDEO_HEIGHT` / `TARGET_MAX_SEC` を切り替えてください。

---

## 免責

本ツールが生成する動画は予想・考察コンテンツです。生成される説明文には自動で免責文言が挿入されますが、各プラットフォームの規約・法令(景品表示法等)の遵守は利用者の責任で行ってください。
