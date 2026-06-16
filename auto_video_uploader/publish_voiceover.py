"""アフレコ動画(drafts/voiceover_story)を本番音声でレンダリングして
YouTube に予約投稿する。GitHub Actions 上で VOICEVOX を使って実行する想定。

公開時刻は環境変数 PUBLISH_AT_JST (例: "2026-06-18 12:00") で指定。
未指定なら即時公開(PRIVACY_STATUS)。
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import config
from make_voiceover_video import main as build_video
from modules.logger import get_logger
from modules.youtube_uploader import YouTubeUploader

TITLE = "この台6確定レベルだったのに…まさかの結末【ジャグラー】#shorts"
DESCRIPTION = (
    "ぶどう4.8分の1、1ゲーム連まで…6確定レベルだと思ったジャグラーの実戦結果。\n"
    "あなたならどう打つ?コメントで教えてください。\n\n"
    "※本動画は予想・考察であり、結果を保証するものではありません。\n\n"
    "#Shorts #ジャグラー #マイジャグラー #パチスロ #スロット #実戦"
)
TAGS = [
    "Shorts", "ジャグラー", "マイジャグラー", "パチスロ", "スロット",
    "実戦", "ジャグラーマン", "設定6", "スランプグラフ",
]


def _compute_publish_at() -> str | None:
    jst = os.getenv("PUBLISH_AT_JST", "").strip()
    if not jst:
        return None
    dt = datetime.strptime(jst, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Tokyo"))
    # YouTube は RFC3339(UTC)を要求
    return dt.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    logger = get_logger()

    if build_video() != 0:
        logger.error("動画のレンダリングに失敗しました")
        return 1
    video = config.VIDEOS_DIR / "voiceover_story.mp4"
    if not video.exists():
        logger.error("レンダリング済み動画が見つかりません: %s", video)
        return 1

    publish_at = _compute_publish_at()
    logger.info("アップロード開始 (publish_at=%s)", publish_at or "即時")

    uploader = YouTubeUploader()
    result = uploader.upload(
        video_path=video,
        title=TITLE,
        description=DESCRIPTION,
        tags=TAGS,
        thumbnail_path=None,  # 電話番号認証が無いためサムネは設定しない
        publish_at=publish_at,
    )
    logger.info("完了: %s (publish_at=%s)", result.video_url, result.publish_at or "即時公開")
    print(f"VIDEO_URL={result.video_url}")
    print(f"PUBLISH_AT={result.publish_at}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
