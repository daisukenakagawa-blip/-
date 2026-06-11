"""YouTube Data API v3 によるアップロード。

初回実行時にブラウザで OAuth 認証を行い、token.json に認証情報を保存する。
2回目以降は token.json を自動でリフレッシュして使う。
"""

import time
from pathlib import Path

import config
from modules.logger import get_logger
from modules.platform_base import BaseUploader, UploadResult

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

RETRYABLE_STATUS = (500, 502, 503, 504)
MAX_RETRIES = 4


class YouTubeUploader(BaseUploader):
    PLATFORM = "youtube"

    def __init__(self):
        self.logger = get_logger()
        self._service = None

    # ------------------------------------------------------------------
    # 認証
    # ------------------------------------------------------------------
    def get_credentials(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow

        creds = None
        token_file = Path(config.YOUTUBE_TOKEN_FILE)
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                self.logger.warning("トークンのリフレッシュに失敗。再認証します: %s", e)
                creds = None

        if not creds or not creds.valid:
            secret_file = Path(config.YOUTUBE_CLIENT_SECRET_FILE)
            if not secret_file.exists():
                raise FileNotFoundError(
                    f"client_secret.json が見つかりません: {secret_file}\n"
                    "README の「YouTube API 認証の手順」に従って配置してください。"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(secret_file), SCOPES)
            creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
            self.logger.info("認証情報を保存しました: %s", token_file)

        return creds

    def _get_service(self):
        if self._service is None:
            from googleapiclient.discovery import build

            self._service = build(
                "youtube", "v3", credentials=self.get_credentials(), cache_discovery=False
            )
        return self._service

    def authenticate(self) -> None:
        """アップロードせず認証だけ行う (main.py --auth-only 用)。"""
        self.get_credentials()
        self.logger.info("YouTube 認証 OK")

    # ------------------------------------------------------------------
    # アップロード
    # ------------------------------------------------------------------
    def upload(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list,
        thumbnail_path: Path | None = None,
        publish_at: str | None = None,
    ) -> UploadResult:
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload

        service = self._get_service()

        status = {"selfDeclaredMadeForKids": False}
        if publish_at:
            # 予約投稿は privacyStatus=private + publishAt の組み合わせが必須
            status["privacyStatus"] = "private"
            status["publishAt"] = publish_at
        else:
            status["privacyStatus"] = config.PRIVACY_STATUS

        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:4900],
                "tags": tags[:30],
                "categoryId": config.YOUTUBE_CATEGORY_ID,
            },
            "status": status,
        }

        media = MediaFileUpload(
            str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True
        )
        request = service.videos().insert(
            part="snippet,status", body=body, media_body=media
        )

        self.logger.info("YouTube へアップロード中: %s", video_path.name)
        response = None
        retry = 0
        while response is None:
            try:
                progress, response = request.next_chunk()
                if progress:
                    self.logger.info("進捗 %d%%", int(progress.progress() * 100))
                retry = 0
            except HttpError as e:
                if e.resp.status in RETRYABLE_STATUS and retry < MAX_RETRIES:
                    retry += 1
                    wait = 2 ** retry
                    self.logger.warning(
                        "HTTP %s。%d 秒後にリトライ (%d/%d)",
                        e.resp.status, wait, retry, MAX_RETRIES,
                    )
                    time.sleep(wait)
                else:
                    raise

        video_id = response["id"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        self.logger.info("アップロード完了: %s", video_url)

        if thumbnail_path and thumbnail_path.exists():
            try:
                service.thumbnails().set(
                    videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
                ).execute()
                self.logger.info("サムネイルを設定しました")
            except HttpError as e:
                # サムネイル設定にはチャンネルの電話番号認証が必要。失敗しても動画は残す。
                self.logger.warning(
                    "サムネイル設定に失敗しました(動画自体はアップロード済み): %s", e
                )

        return UploadResult(video_id=video_id, video_url=video_url, publish_at=publish_at or "")
