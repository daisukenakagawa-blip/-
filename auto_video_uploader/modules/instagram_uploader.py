"""Instagram Reels (Graph API) によるアップロード。

事前準備 (README の「Instagram Reels に自動投稿する」参照):
  1. Instagram アカウントを「プロアカウント」に切り替え、Facebook ページと連携
  2. https://developers.facebook.com/ でアプリを作成し、
     instagram_content_publish 等の権限で長期アクセストークンを取得
  3. .env / GitHub Secrets に IG_USER_ID / IG_ACCESS_TOKEN を設定

Graph API は「公開 URL から動画を取得する」方式のため、modules/public_host.py
で動画を一時公開 URL 化してから渡す (24時間で自動削除される)。
"""

import time
from pathlib import Path

import requests

import config
from modules.logger import get_logger
from modules.platform_base import BaseUploader, UploadResult
from modules import public_host

CAPTION_MAX = 2200
POLL_SEC = 10
POLL_MAX = 30  # 最大5分待つ


class InstagramUploader(BaseUploader):
    PLATFORM = "instagram"

    def __init__(self):
        self.logger = get_logger()
        self.base = f"https://graph.facebook.com/{config.IG_API_VERSION}"

    def _check(self, resp) -> dict:
        data = resp.json()
        if resp.status_code != 200 or "error" in data:
            raise RuntimeError(f"Instagram API エラー: {resp.status_code} {data}")
        return data

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list,
        thumbnail_path: Path | None = None,
        publish_at: str | None = None,
    ) -> UploadResult:
        if not (config.IG_USER_ID and config.IG_ACCESS_TOKEN):
            raise RuntimeError(
                "IG_USER_ID / IG_ACCESS_TOKEN が未設定です。README の"
                "「Instagram Reels に自動投稿する」を参照してください。"
            )
        if publish_at:
            self.logger.info("Instagram は予約投稿に未対応のため即時投稿します")

        hashtags = " ".join(f"#{t}" for t in tags[:15])
        caption = f"{title}\n\n{hashtags}"[:CAPTION_MAX]

        # 1. 動画を一時公開 URL 化
        video_url = public_host.publish_temporarily(video_path)

        # 2. メディアコンテナ作成
        self.logger.info("Instagram Reels コンテナを作成中")
        data = self._check(requests.post(
            f"{self.base}/{config.IG_USER_ID}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true",
                "access_token": config.IG_ACCESS_TOKEN,
            },
            timeout=60,
        ))
        container_id = data["id"]

        # 3. 動画の取り込み完了を待つ
        for _ in range(POLL_MAX):
            data = self._check(requests.get(
                f"{self.base}/{container_id}",
                params={"fields": "status_code", "access_token": config.IG_ACCESS_TOKEN},
                timeout=30,
            ))
            status = data.get("status_code", "")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise RuntimeError(f"Instagram の動画処理が失敗しました: {data}")
            self.logger.info("Instagram 動画処理中 (%s)…", status or "IN_PROGRESS")
            time.sleep(POLL_SEC)
        else:
            raise RuntimeError("Instagram の動画処理がタイムアウトしました")

        # 4. 公開
        data = self._check(requests.post(
            f"{self.base}/{config.IG_USER_ID}/media_publish",
            data={"creation_id": container_id, "access_token": config.IG_ACCESS_TOKEN},
            timeout=60,
        ))
        media_id = data["id"]

        # 5. 投稿 URL を取得 (失敗しても投稿自体は完了している)
        permalink = "https://www.instagram.com/"
        try:
            data = self._check(requests.get(
                f"{self.base}/{media_id}",
                params={"fields": "permalink", "access_token": config.IG_ACCESS_TOKEN},
                timeout=30,
            ))
            permalink = data.get("permalink", permalink)
        except Exception as e:
            self.logger.warning("permalink の取得に失敗 (投稿は完了済み): %s", e)

        self.logger.info("Instagram Reels 投稿完了: %s", permalink)
        return UploadResult(video_id=media_id, video_url=permalink)
