"""X (旧 Twitter) への動画投稿。

事前準備 (README の「X に自動投稿する」参照):
  1. https://developer.x.com/ で Free プランに登録しアプリを作成
  2. アプリの権限を「Read and write」にし、
     API Key / API Key Secret / Access Token / Access Token Secret を発行
  3. .env / GitHub Secrets に X_API_KEY / X_API_SECRET /
     X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET を設定

動画はチャンクアップロード (INIT → APPEND → FINALIZE → STATUS) 後、
v2 の POST /2/tweets で本文と一緒に投稿する。v2 のメディアアップロード
エンドポイントを優先し、未提供環境では v1.1 に自動フォールバックする。
"""

import time
from pathlib import Path

import requests

import config
from modules.logger import get_logger
from modules.platform_base import BaseUploader, UploadResult

MEDIA_V2 = "https://api.x.com/2/media/upload"
MEDIA_V11 = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_URL = "https://api.x.com/2/tweets"
APPEND_CHUNK = 4 * 1024 * 1024
TEXT_MAX = 280


class XUploader(BaseUploader):
    PLATFORM = "x"

    def __init__(self):
        self.logger = get_logger()
        self._auth = None
        self._media_url = MEDIA_V2

    def _get_auth(self):
        if self._auth is None:
            keys = (config.X_API_KEY, config.X_API_SECRET,
                    config.X_ACCESS_TOKEN, config.X_ACCESS_TOKEN_SECRET)
            if not all(keys):
                raise RuntimeError(
                    "X の認証情報 (X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / "
                    "X_ACCESS_TOKEN_SECRET) が未設定です。"
                )
            from requests_oauthlib import OAuth1

            self._auth = OAuth1(*keys)
        return self._auth

    def _media_request(self, method: str, **kwargs):
        """v2 を試し、404/410 なら v1.1 にフォールバックして再送する。"""
        resp = requests.request(method, self._media_url, auth=self._get_auth(),
                                timeout=600, **kwargs)
        if resp.status_code in (404, 410) and self._media_url == MEDIA_V2:
            self.logger.info("v2 メディアアップロードが使えないため v1.1 を使用します")
            self._media_url = MEDIA_V11
            resp = requests.request(method, self._media_url, auth=self._get_auth(),
                                    timeout=600, **kwargs)
        return resp

    @staticmethod
    def _media_data(resp) -> dict:
        data = resp.json()
        return data.get("data", data)  # v2 は {"data": {...}}, v1.1 はトップレベル

    @staticmethod
    def _media_id(data: dict) -> str:
        return str(data.get("id") or data.get("media_id_string") or data.get("media_id"))

    def _upload_media(self, video_path: Path) -> str:
        size = video_path.stat().st_size

        resp = self._media_request("POST", data={
            "command": "INIT",
            "total_bytes": size,
            "media_type": "video/mp4",
            "media_category": "tweet_video",
        })
        if resp.status_code >= 300:
            raise RuntimeError(f"X メディア INIT に失敗: {resp.status_code} {resp.text[:300]}")
        media_id = self._media_id(self._media_data(resp))

        with open(video_path, "rb") as f:
            index = 0
            while True:
                chunk = f.read(APPEND_CHUNK)
                if not chunk:
                    break
                resp = self._media_request(
                    "POST",
                    data={"command": "APPEND", "media_id": media_id, "segment_index": index},
                    files={"media": chunk},
                )
                if resp.status_code >= 300:
                    raise RuntimeError(
                        f"X メディア APPEND に失敗: {resp.status_code} {resp.text[:300]}"
                    )
                index += 1
                self.logger.info("X 送信進捗 %d チャンク", index)

        resp = self._media_request("POST", data={"command": "FINALIZE", "media_id": media_id})
        if resp.status_code >= 300:
            raise RuntimeError(f"X メディア FINALIZE に失敗: {resp.status_code} {resp.text[:300]}")
        info = self._media_data(resp).get("processing_info")

        # 動画はサーバー側の変換完了を待つ
        while info and info.get("state") in ("pending", "in_progress"):
            wait = info.get("check_after_secs", 5)
            self.logger.info("X 動画処理中… %d 秒待機", wait)
            time.sleep(wait)
            resp = self._media_request(
                "GET", params={"command": "STATUS", "media_id": media_id}
            )
            if resp.status_code >= 300:
                raise RuntimeError(f"X STATUS 取得に失敗: {resp.status_code} {resp.text[:300]}")
            info = self._media_data(resp).get("processing_info")
        if info and info.get("state") == "failed":
            raise RuntimeError(f"X の動画処理が失敗しました: {info}")
        return media_id

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list,
        thumbnail_path: Path | None = None,
        publish_at: str | None = None,
    ) -> UploadResult:
        if publish_at:
            self.logger.info("X は予約投稿に未対応のため即時投稿します")

        hashtags = " ".join(f"#{t}" for t in tags[:3])
        text = f"{title}\n{hashtags}"
        if len(text) > TEXT_MAX:
            text = title[: TEXT_MAX - len(hashtags) - 2] + "\n" + hashtags

        media_id = self._upload_media(video_path)

        resp = requests.post(
            TWEET_URL,
            json={"text": text, "media": {"media_ids": [media_id]}},
            auth=self._get_auth(),
            timeout=60,
        )
        data = resp.json()
        if resp.status_code >= 300 or "data" not in data:
            raise RuntimeError(f"X 投稿に失敗: {resp.status_code} {data}")

        tweet_id = data["data"]["id"]
        url = f"https://x.com/i/status/{tweet_id}"
        self.logger.info("X 投稿完了: %s", url)
        return UploadResult(video_id=tweet_id, video_url=url)
