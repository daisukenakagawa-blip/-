"""アプリ全体の設定。.env から読み込み、コードへの直書きを避ける。"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# .env を読み込む(存在しなくてもエラーにしない)
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# ディレクトリ
# ---------------------------------------------------------------------------
VIDEOS_DIR = BASE_DIR / "videos"
THUMBNAILS_DIR = BASE_DIR / "thumbnails"
AUDIO_DIR = BASE_DIR / "audio"
SCRIPTS_DIR = BASE_DIR / "scripts"
ASSETS_DIR = BASE_DIR / "assets"
LOGS_DIR = BASE_DIR / "logs"

TOPICS_CSV = BASE_DIR / "topics.csv"
# Google スプレッドシートの「ウェブに公開 (CSV)」URL。設定すると実行時に
# シートの内容を topics.csv へ自動で取り込む(スマホからのテーマ追加用)
TOPICS_SHEET_URL = os.getenv("TOPICS_SHEET_URL", "").strip()
UPLOADED_LOG_CSV = BASE_DIR / "uploaded_log.csv"
ERROR_LOG_TXT = LOGS_DIR / "error_log.txt"
APP_LOG_TXT = LOGS_DIR / "app.log"


def ensure_dirs() -> None:
    for d in (VIDEOS_DIR, THUMBNAILS_DIR, AUDIO_DIR, SCRIPTS_DIR, ASSETS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 動画設定 (YouTube Shorts 縦動画)
# ---------------------------------------------------------------------------
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
# ナレーションがこの秒数を超えた場合は台本側で調整する想定(30〜60秒)
TARGET_MIN_SEC = int(os.getenv("TARGET_MIN_SEC", "30"))
TARGET_MAX_SEC = int(os.getenv("TARGET_MAX_SEC", "60"))

# 背景素材: assets/background.mp4 / background.png / background.jpg を順に探す。
# 無ければ Pillow でグラデーション背景を自動生成する。
BACKGROUND_CANDIDATES = ["background.mp4", "background.png", "background.jpg"]

# Pexels API (任意): 設定すると背景の縦型動画を自動でダウンロードして使う
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "").strip()
BACKGROUND_KEYWORD = os.getenv("BACKGROUND_KEYWORD", "casino neon lights")

# BGM: assets/bgm.mp3 (任意)。BGM_PATH で別パスも指定可能。
BGM_PATH = os.getenv("BGM_PATH", str(ASSETS_DIR / "bgm.mp3"))
BGM_VOLUME = float(os.getenv("BGM_VOLUME", "0.12"))

# 効果音 (ランキング切り替え時)。assets/se.mp3 を置けば差し替え可能。
# 無ければ ffmpeg で電子音を自動合成する。
SE_PATH = os.getenv("SE_PATH", str(ASSETS_DIR / "se.mp3"))
SE_VOLUME = float(os.getenv("SE_VOLUME", "0.45"))

# ランキング構成モード (1=有効)。生成台本を Shorts 向けランキング構成にする
RANKING_MODE = os.getenv("RANKING_MODE", "1").lower() not in ("0", "false", "no")

# ---------------------------------------------------------------------------
# 品質チェック
# ---------------------------------------------------------------------------
QUALITY_MIN_SCORE = int(os.getenv("QUALITY_MIN_SCORE", "80"))
QUALITY_MAX_RETRIES = int(os.getenv("QUALITY_MAX_RETRIES", "2"))
QUALITY_LOG_TXT = LOGS_DIR / "quality_log.txt"

# 日本語フォント (テロップ / サムネイル用)
FONT_PATH = os.getenv(
    "FONT_PATH",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
)
# ASS 字幕で参照するフォント名
FONT_NAME = os.getenv("FONT_NAME", "Noto Sans CJK JP")

# ---------------------------------------------------------------------------
# 台本生成 (Claude API)。キー未設定ならテンプレート生成にフォールバック。
# ---------------------------------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-8")

# ---------------------------------------------------------------------------
# 音声合成 (TTS)
#   TTS_ENGINE: "voicevox" | "gtts"
#   voicevox はローカルで VOICEVOX エンジンが起動している必要あり
# ---------------------------------------------------------------------------
TTS_ENGINE = os.getenv("TTS_ENGINE", "auto").lower()
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://127.0.0.1:50021")
VOICEVOX_SPEAKER = int(os.getenv("VOICEVOX_SPEAKER", "3"))  # 3 = ずんだもん(ノーマル)
GTTS_LANG = os.getenv("GTTS_LANG", "ja")

# ---------------------------------------------------------------------------
# YouTube
# ---------------------------------------------------------------------------
YOUTUBE_CLIENT_SECRET_FILE = os.getenv(
    "YOUTUBE_CLIENT_SECRET_FILE", str(BASE_DIR / "client_secret.json")
)
YOUTUBE_TOKEN_FILE = os.getenv("YOUTUBE_TOKEN_FILE", str(BASE_DIR / "token.json"))
YOUTUBE_CATEGORY_ID = os.getenv("YOUTUBE_CATEGORY_ID", "24")  # 24 = Entertainment
# 予約投稿しない場合の公開設定: public / unlisted / private
PRIVACY_STATUS = os.getenv("PRIVACY_STATUS", "public")
# 予約投稿の時刻 (topics.csv の date が未来日の場合に使用)
PUBLISH_TIME = os.getenv("PUBLISH_TIME", "19:00")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
