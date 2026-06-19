# -*- coding: utf-8 -*-
"""
note 自動投稿ツールの設定。

note には公式の投稿APIが無いため、ブラウザ自動操作(Playwright)で
あなた自身のアカウントを操作します。ここの設定を変えるだけで動作を調整できます。
"""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATE_DIR = BASE_DIR / "state"            # ログインセッション(cookie)保存先
SESSION_FILE = STATE_DIR / "note_session.json"
SCREENSHOT_DIR = BASE_DIR / "screenshots"  # 各ステップのスクショ(不具合調査用)
LOG_DIR = BASE_DIR / "logs"
POSTED_LOG = BASE_DIR / "posted_log.csv"   # 投稿済み記録(重複防止)

# 投稿する記事(Markdown)の置き場所。既定は note_writer/articles を読む。
ARTICLES_DIR = BASE_DIR.parent / "note_writer" / "articles"

# ── 投稿モード ──────────────────────────────────────────────
# "draft"    : 下書き保存のみ(既定・最も安全。公開はnoteの画面で自分で行う)
# "publish"  : そのまま公開する(上級者向け・自己責任)
# "schedule" : 予約投稿する(SCHEDULE_AT を使用)
PUBLISH_MODE = "draft"

# PUBLISH_MODE="schedule" のときの予約日時(各記事のfront matterで上書き可)
# 例: "2026-07-01 19:00"
SCHEDULE_AT = ""

# 投稿が終わったら LINE に通知する(環境変数 LINE_CHANNEL_ACCESS_TOKEN が必要)
# 未設定なら自動でスキップします。
NOTIFY_LINE = True

# 1回の実行で投稿する最大本数(連投しすぎない安全弁)
MAX_POSTS_PER_RUN = 3
# 投稿と投稿の間隔(秒)。短時間の連続操作を避ける
INTERVAL_BETWEEN_POSTS = 30

# ── ブラウザ設定 ────────────────────────────────────────────
HEADLESS = False              # False で画面を見ながら実行(最初は False 推奨)
SLOW_MO_MS = 80               # 操作をゆっくりに(挙動確認・安定化)
TYPE_DELAY_MS = 8             # 1文字ごとの入力遅延(マークダウン自動変換を効かせる)
NAV_TIMEOUT_MS = 60000        # ページ遷移のタイムアウト

# ── note の URL / セレクタ(仕様変更時はここを直す) ─────────
NOTE_TOP = "https://note.com/"
NOTE_LOGIN = "https://note.com/login"
# 新規テキスト記事エディタ。開けない場合は README の手順でURLを差し替えてください。
EDITOR_URL = "https://note.com/notes/new"

# セレクタは複数候補を順に試す(仕様変更に強くするため)
SELECTORS = {
    # ログイン済み判定に使う要素(投稿ボタン等)
    "logged_in": [
        "a[href*='/notes/new']",
        "button:has-text('投稿')",
        "[data-testid='header-avatar']",
    ],
    # タイトル入力欄
    "title": [
        "textarea[placeholder*='タイトル']",
        "textarea[placeholder*='記事タイトル']",
        "[contenteditable][data-placeholder*='タイトル']",
    ],
    # 本文入力欄(ProseMirror系)
    "body": [
        "div.ProseMirror",
        "[contenteditable='true'][role='textbox']",
        "[contenteditable='true']",
    ],
    # 公開設定へ進むボタン
    "to_publish": [
        "button:has-text('公開設定')",
        "button:has-text('公開に進む')",
    ],
    # 公開(投稿)ボタン
    "publish": [
        "button:has-text('投稿する')",
        "button:has-text('公開する')",
    ],
}
