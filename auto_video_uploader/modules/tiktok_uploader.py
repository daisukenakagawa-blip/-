"""TikTok Content Posting API によるアップロード。

事前準備 (README の「TikTok に自動投稿する」参照):
  1. https://developers.tiktok.com/ でアプリを作成し、
     Content Posting API (video.upload / video.publish スコープ) を有効化
  2. OAuth 認可を一度行い、リフレッシュトークンを取得
  3. .env / GitHub Secrets に TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET /
     TIKTOK_REFRESH_TOKEN を設定

投稿モード (TIKTOK_POST_MODE):
  inbox  (既定) … 下書きとしてアップロード。スマホの TikTok アプリに通知が
                  届き、受信箱から数タップで投稿できる。未監査アプリでも
                  「公開」投稿にできる唯一の方法なのでこれを既定にする。
  direct         … API から直接投稿。TikTok の監査(audit)を通過した
                  アプリ以外は privacy_level=SELF_ONLY(自分のみ閲覧可)に
                  制限される点に注意。

トークンはリフレッシュのたびに新しい refresh_token が返ることがある。
ローカル実行では tiktok_token.json に自動保存して次回以降も使う。
GitHub Actions ではファイルを永続化できないため、ログに出る案内に従って
Secrets の TIKTOK_REFRESH_TOKEN を更新すること(有効期限は最長365日)。
"""

import json
import time
from pathlib import Path

import requests

import config
from modules.logger import get_logger
from modules.platform_base import BaseUploader, UploadResult

API_BASE = "https://open.tiktokapis.com/v2"
CHUNK_LIMIT = 64 * 1024 * 1024  # 64MB までは 1 チャンクで送れる
CHUNK_SIZE = 50 * 1024 * 1024
CAPTION_MAX = 2200
STATUS_POLL_SEC = 5
STATUS_POLL_MAX = 36  # 最大3分待つ


class TikTokUploader(BaseUploader):
    PLATFORM = "tiktok"

    def __init__(self):
        self.logger = get_logger()

    # ------------------------------------------------------------------
    # 認証 (リフレッシュトークン → アクセストークン)
    # ------------------------------------------------------------------
    def _load_refresh_token(self) -> str:
        token_file = Path(config.TIKTOK_TOKEN_FILE)
        if token_file.exists():
            try:
                saved = json.loads(token_file.read_text(encoding="utf-8"))
                if saved.get("refresh_token"):
                    return saved["refresh_token"]
            except Exception:
                pass
        if config.TIKTOK_REFRESH_TOKEN:
            return config.TIKTOK_REFRESH_TOKEN
        raise RuntimeError(
            "TikTok のリフレッシュトークンがありません。README の"
            "「TikTok に自動投稿する」に従って TIKTOK_REFRESH_TOKEN を設定してください。"
        )

    def get_access_token(self) -> str:
        if not (config.TIKTOK_CLIENT_KEY and config.TIKTOK_CLIENT_SECRET):
            raise RuntimeError(
                "TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET が未設定です。"
            )
        refresh_token = self._load_refresh_token()
        resp = requests.post(
            f"{API_BASE}/oauth/token/",
            data={
                "client_key": config.TIKTOK_CLIENT_KEY,
                "client_secret": config.TIKTOK_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200 or "access_token" not in data:
            raise RuntimeError(f"TikTok トークン更新に失敗: {resp.status_code} {data}")

        new_refresh = data.get("refresh_token", "")
        if new_refresh and new_refresh != refresh_token:
            token_file = Path(config.TIKTOK_TOKEN_FILE)
            token_file.write_text(
                json.dumps({"refresh_token": new_refresh}, ensure_ascii=False),
                encoding="utf-8",
            )
            self.logger.warning(
                "TikTok のリフレッシュトークンが更新されました。GitHub Actions で"
                "運用している場合は Secrets の TIKTOK_REFRESH_TOKEN を"
                " tiktok_token.json の値に更新してください"
            )
        return data["access_token"]

    # ------------------------------------------------------------------
    # アップロード
    # ------------------------------------------------------------------
    def _init_upload(self, access_token: str, caption: str, video_size: int) -> dict:
        if video_size <= CHUNK_LIMIT:
            chunk_size, total_chunks = video_size, 1
        else:
            chunk_size = CHUNK_SIZE
            total_chunks = video_size // chunk_size

        source_info = {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        }
        if config.TIKTOK_POST_MODE == "direct":
            endpoint = f"{API_BASE}/post/publish/video/init/"
            body = {
                "post_info": {
                    "title": caption,
                    "privacy_level": config.TIKTOK_PRIVACY,
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": source_info,
            }
        else:  # inbox (下書き)
            endpoint = f"{API_BASE}/post/publish/inbox/video/init/"
            body = {"source_info": source_info}

        resp = requests.post(
            endpoint,
            json=body,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            timeout=30,
        )
        data = resp.json()
        if resp.status_code != 200 or data.get("error", {}).get("code") not in ("ok", None):
            raise RuntimeError(f"TikTok 初期化に失敗: {resp.status_code} {data}")
        result = data["data"]
        result["_chunk_size"] = chunk_size
        result["_total_chunks"] = total_chunks
        return result

    def _put_chunks(self, upload_url: str, video_path: Path, video_size: int,
                    chunk_size: int, total_chunks: int) -> None:
        with open(video_path, "rb") as f:
            for i in range(total_chunks):
                start = i * chunk_size
                # 最終チャンクは残り全部 (端数を吸収する仕様)
                end = video_size - 1 if i == total_chunks - 1 else start + chunk_size - 1
                length = end - start + 1
                f.seek(start)
                data = f.read(length)
                resp = requests.put(
                    upload_url,
                    data=data,
                    headers={
                        "Content-Type": "video/mp4",
                        "Content-Length": str(length),
                        "Content-Range": f"bytes {start}-{end}/{video_size}",
                    },
                    timeout=600,
                )
                if resp.status_code not in (200, 201, 206):
                    raise RuntimeError(
                        f"TikTok 動画チャンク送信に失敗: {resp.status_code} {resp.text[:300]}"
                    )
                self.logger.info("TikTok 送信進捗 %d/%d", i + 1, total_chunks)

    def _wait_status(self, access_token: str, publish_id: str) -> str:
        for _ in range(STATUS_POLL_MAX):
            resp = requests.post(
                f"{API_BASE}/post/publish/status/fetch/",
                json={"publish_id": publish_id},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                },
                timeout=30,
            )
            data = resp.json().get("data", {})
            status = data.get("status", "")
            if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                return status
            if status == "FAILED":
                raise RuntimeError(f"TikTok 投稿処理が失敗: {data}")
            time.sleep(STATUS_POLL_SEC)
        self.logger.warning("TikTok の処理完了を確認できませんでした (タイムアウト)。"
                            "アプリの受信箱を確認してください")
        return "TIMEOUT"

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
            self.logger.info("TikTok は予約投稿に未対応のため即時処理します")

        hashtags = " ".join(f"#{t}" for t in tags[:8])
        caption = f"{title}\n{hashtags}"[:CAPTION_MAX]

        access_token = self.get_access_token()
        video_size = video_path.stat().st_size
        init = self._init_upload(access_token, caption, video_size)
        self._put_chunks(
            init["upload_url"], video_path, video_size,
            init["_chunk_size"], init["_total_chunks"],
        )
        status = self._wait_status(access_token, init["publish_id"])

        if config.TIKTOK_POST_MODE == "direct":
            self.logger.info("TikTok へ直接投稿しました (status=%s)", status)
        else:
            self.logger.info(
                "TikTok の受信箱に下書きを送りました (status=%s)。"
                "スマホの TikTok アプリの通知から数タップで公開できます", status
            )
        return UploadResult(
            video_id=init["publish_id"],
            video_url="https://www.tiktok.com/ (アプリの受信箱/プロフィールを確認)",
        )
