"""X (旧 Twitter) への動画投稿。

X API v2 でツイートを作成し、動画は v1.1 のチャンクアップロード
(INIT → APPEND → FINALIZE → STATUS) でアップロードする。
認証は OAuth 1.0a (ユーザーコンテキスト)。以下の 4 つのキーが必要:

  X_API_KEY              … Consumer Key (API Key)
  X_API_SECRET           … Consumer Secret (API Key Secret)
  X_ACCESS_TOKEN         … Access Token
  X_ACCESS_TOKEN_SECRET  … Access Token Secret

いずれも https://developer.x.com のアプリ設定で発行する。アプリの権限は
「Read and write」にしておくこと(読み取り専用だと投稿で 403 になる)。

※ X API には公式の予約投稿エンドポイントが無い(予約は Ads API のみ)。
   publish_at が指定されても即時投稿し、警告ログを残す。
"""

import time
from pathlib import Path

import config
from modules.logger import get_logger
from modules.platform_base import BaseUploader, UploadResult

MEDIA_ENDPOINT = "https://upload.twitter.com/1.1/media/upload.json"
TWEET_ENDPOINT = "https://api.twitter.com/2/tweets"

# 動画 1 チャンクのサイズ (X の上限は 5MB/チャンク)
CHUNK_SIZE = 4 * 1024 * 1024
MAX_RETRIES = 4


class XUploader(BaseUploader):
    PLATFORM = "x"

    def __init__(self):
        self.logger = get_logger()
        self._auth = None

    # ------------------------------------------------------------------
    # 認証
    # ------------------------------------------------------------------
    def _get_auth(self):
        if self._auth is None:
            from requests_oauthlib import OAuth1

            missing = [
                name
                for name, val in (
                    ("X_API_KEY", config.X_API_KEY),
                    ("X_API_SECRET", config.X_API_SECRET),
                    ("X_ACCESS_TOKEN", config.X_ACCESS_TOKEN),
                    ("X_ACCESS_TOKEN_SECRET", config.X_ACCESS_TOKEN_SECRET),
                )
                if not val
            ]
            if missing:
                raise ValueError(
                    "X の認証情報が未設定です: " + ", ".join(missing) + "\n"
                    "README の「X (Twitter) 投稿の設定」に従って .env / Secrets に登録してください。"
                )
            self._auth = OAuth1(
                config.X_API_KEY,
                config.X_API_SECRET,
                config.X_ACCESS_TOKEN,
                config.X_ACCESS_TOKEN_SECRET,
            )
        return self._auth

    def authenticate(self) -> None:
        """投稿せず認証だけ確認する (main.py --auth-only 用)。"""
        import requests

        resp = requests.get(
            "https://api.twitter.com/2/users/me", auth=self._get_auth(), timeout=30
        )
        if resp.status_code != 200:
            raise RuntimeError(f"X 認証に失敗しました: HTTP {resp.status_code} {resp.text}")
        username = resp.json().get("data", {}).get("username", "")
        self.logger.info("X 認証 OK (@%s)", username)

    # ------------------------------------------------------------------
    # 動画のチャンクアップロード
    # ------------------------------------------------------------------
    def _upload_media(self, video_path: Path) -> str:
        import requests

        auth = self._get_auth()
        total_bytes = video_path.stat().st_size

        # INIT
        init = requests.post(
            MEDIA_ENDPOINT,
            auth=auth,
            data={
                "command": "INIT",
                "total_bytes": total_bytes,
                "media_type": "video/mp4",
                "media_category": "tweet_video",
            },
            timeout=60,
        )
        init.raise_for_status()
        media_id = init.json()["media_id_string"]
        self.logger.info("X メディア INIT 完了 (media_id=%s, %d bytes)", media_id, total_bytes)

        # APPEND (チャンク送信)
        with open(video_path, "rb") as f:
            segment_index = 0
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                for retry in range(MAX_RETRIES):
                    resp = requests.post(
                        MEDIA_ENDPOINT,
                        auth=auth,
                        data={
                            "command": "APPEND",
                            "media_id": media_id,
                            "segment_index": segment_index,
                        },
                        files={"media": chunk},
                        timeout=120,
                    )
                    if resp.status_code in (200, 201, 204):
                        break
                    if retry < MAX_RETRIES - 1:
                        wait = 2 ** (retry + 1)
                        self.logger.warning(
                            "APPEND 失敗 (HTTP %s)。%d 秒後にリトライ", resp.status_code, wait
                        )
                        time.sleep(wait)
                    else:
                        resp.raise_for_status()
                self.logger.info("X メディア APPEND 完了 (segment=%d)", segment_index)
                segment_index += 1

        # FINALIZE
        finalize = requests.post(
            MEDIA_ENDPOINT,
            auth=auth,
            data={"command": "FINALIZE", "media_id": media_id},
            timeout=60,
        )
        finalize.raise_for_status()
        info = finalize.json().get("processing_info")

        # 動画はサーバ側でエンコードされるため、完了までポーリングする
        while info and info.get("state") in ("pending", "in_progress"):
            wait = int(info.get("check_after_secs", 5))
            self.logger.info("X メディア処理中... %d 秒待機", wait)
            time.sleep(wait)
            status = requests.get(
                MEDIA_ENDPOINT,
                auth=auth,
                params={"command": "STATUS", "media_id": media_id},
                timeout=60,
            )
            status.raise_for_status()
            info = status.json().get("processing_info")

        if info and info.get("state") == "failed":
            raise RuntimeError(f"X の動画処理に失敗しました: {info.get('error')}")

        self.logger.info("X メディア処理完了 (media_id=%s)", media_id)
        return media_id

    # ------------------------------------------------------------------
    # 投稿
    # ------------------------------------------------------------------
    def _build_text(self, title: str, description: str, tags: list) -> str:
        """280 文字に収まるよう本文を組み立てる。"""
        hashtags = " ".join(
            "#" + t.strip().lstrip("#").replace(" ", "")
            for t in (tags or [])
            if t.strip()
        )
        # タイトルを優先し、残り文字数にハッシュタグを詰める
        text = title.strip()
        if hashtags:
            candidate = f"{text}\n{hashtags}"
            if len(candidate) <= 280:
                text = candidate
            else:
                # ハッシュタグを 1 つずつ削って収める
                tag_list = hashtags.split()
                while tag_list:
                    tag_list.pop()
                    candidate = f"{text}\n{' '.join(tag_list)}".strip()
                    if len(candidate) <= 280:
                        text = candidate
                        break
        return text[:280]

    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list,
        thumbnail_path: Path | None = None,
        publish_at: str | None = None,
    ) -> UploadResult:
        import requests

        if publish_at:
            self.logger.warning(
                "X API は予約投稿に対応していないため即時投稿します (指定: %s)", publish_at
            )

        self.logger.info("X へアップロード中: %s", video_path.name)
        media_id = self._upload_media(video_path)

        text = self._build_text(title, description, tags)
        resp = requests.post(
            TWEET_ENDPOINT,
            auth=self._get_auth(),
            json={"text": text, "media": {"media_ids": [media_id]}},
            timeout=60,
        )
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"ツイート投稿に失敗しました: HTTP {resp.status_code} {resp.text}")

        tweet_id = resp.json()["data"]["id"]
        tweet_url = f"https://x.com/i/web/status/{tweet_id}"
        self.logger.info("X 投稿完了: %s", tweet_url)
        return UploadResult(video_id=tweet_id, video_url=tweet_url, publish_at="")
