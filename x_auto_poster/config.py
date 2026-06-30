"""アプリ全体の設定。.env から読み込み、コードへの直書きを避ける。"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# .env を読み込む(存在しなくてもエラーにしない)
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# ディレクトリ / ファイル
# ---------------------------------------------------------------------------
IMAGES_DIR = BASE_DIR / "assets" / "images"
GENERATED_DIR = BASE_DIR / "generated"
LOGS_DIR = BASE_DIR / "logs"

TOPICS_CSV = BASE_DIR / "topics.csv"
POSTED_LOG_CSV = BASE_DIR / "posted_log.csv"
ERROR_LOG_TXT = LOGS_DIR / "error_log.txt"
APP_LOG_TXT = LOGS_DIR / "app.log"

# Google スプレッドシートの「ウェブに公開 (CSV)」URL。設定すると実行時に
# シートの内容を topics.csv へ自動で取り込む(スマホからのテーマ追加用)
TOPICS_SHEET_URL = os.getenv("TOPICS_SHEET_URL", "").strip()


def ensure_dirs() -> None:
    for d in (IMAGES_DIR, GENERATED_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# X (Twitter) API 認証 (OAuth 1.0a User Context)
#   https://developer.x.com/ でアプリを作成し「Read and write」権限で発行する
# ---------------------------------------------------------------------------
X_API_KEY = os.getenv("X_API_KEY", "").strip()
X_API_SECRET = os.getenv("X_API_SECRET", "").strip()
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "").strip()
X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "").strip()


def x_credentials_ready() -> bool:
    return all(
        [X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET]
    )


# ---------------------------------------------------------------------------
# 投稿文の生成 (Claude API)
#   未設定でも動作する(テンプレート文にフォールバック)
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

# 投稿のテイスト(プロンプトに渡す前提)。業種に合わせて自由に変更可能。
POST_PERSONA = os.getenv(
    "POST_PERSONA",
    "パチスロ・ジャグラー予想系の情報を発信するアカウント",
)
# X の本文上限は全角でおよそ140文字。安全側でこの文字数に収める。
MAX_TWEET_CHARS = int(os.getenv("MAX_TWEET_CHARS", "130"))

# ---------------------------------------------------------------------------
# 投稿の動作設定
# ---------------------------------------------------------------------------
# 1回の実行で投稿する本数
POSTS_PER_RUN = int(os.getenv("POSTS_PER_RUN", "1"))
# 画像を添付するか (1=添付する / 0=テキストのみ)
ATTACH_IMAGE = os.getenv("ATTACH_IMAGE", "1").strip() != "0"
# 同じテーマを使い切ったら、ログをリセットして最初から使い回すか
RECYCLE_TOPICS = os.getenv("RECYCLE_TOPICS", "1").strip() != "0"
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
# 実際には投稿せず、生成内容のプレビューだけ行う (1=プレビューのみ)
DRY_RUN = os.getenv("DRY_RUN", "0").strip() == "1"
