"""プラットフォーム共通のアップローダー抽象クラス。

TikTok / Instagram Reels / X へ拡張する場合は BaseUploader を継承し、
PLATFORM 名を付けて upload() を実装、get_uploader() に登録するだけでよい。
"""

from abc import ABC, abstractmethod
from pathlib import Path


class UploadResult:
    def __init__(self, video_id: str, video_url: str, publish_at: str = ""):
        self.video_id = video_id
        self.video_url = video_url
        self.publish_at = publish_at


class BaseUploader(ABC):
    """全プラットフォーム共通のインターフェース。"""

    PLATFORM = "base"

    @abstractmethod
    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list,
        thumbnail_path: Path | None = None,
        publish_at: str | None = None,
    ) -> UploadResult:
        """動画をアップロードし、結果を返す。

        publish_at: RFC3339 形式 (例 "2026-06-13T19:00:00+09:00")。
                    指定された場合は予約投稿として扱う。
        """
        raise NotImplementedError


def get_uploader(platform: str) -> BaseUploader:
    """プラットフォーム名からアップローダーを生成するファクトリ。"""
    platform = platform.strip().lower()
    if platform == "youtube":
        from modules.youtube_uploader import YouTubeUploader

        return YouTubeUploader()
    # 将来の拡張ポイント:
    # if platform == "tiktok": return TikTokUploader()
    # if platform == "instagram": return InstagramUploader()
    # if platform == "x": return XUploader()
    raise ValueError(f"未対応のプラットフォームです: {platform}")
