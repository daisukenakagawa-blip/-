"""Instagram への動画投稿 (リール)。

Instagram Graph API でリールを公開する。手順は 3 段階:
  1. メディアコンテナを作成 (公開 URL の動画を指定)
  2. コンテナの処理完了をポーリング
  3. コンテナを公開 (media_publish)

必要なもの:
  - Instagram の「プロアカウント (ビジネス / クリエイター)」
  - それに連携した Facebook ページ
  - 長期アクセストークン (instagram_basic, instagram_content_publish 権限)
  - Instagram ビジネスアカウント ID

  INSTAGRAM_ACCESS_TOKEN          … 長期アクセストークン
  INSTAGRAM_BUSINESS_ACCOUNT_ID   … IG ビジネスアカウント ID

重要: Graph API は**公開 URL からしか動画を取得できない**(ローカルファイルを
直接送れない)。このため、以下のいずれかで動画を公開 URL にする:

  - PUBLIC_MEDIA_BASE_URL を設定し、videos/ をその URL で公開しておく
    → 動画は {PUBLIC_MEDIA_BASE_URL}/{ファイル名} で取得される
  - 上記が無い場合は匿名アップローダ (catbox.moe) に一時アップロードして
    その直リンクを使う (フォールバック)

※ Instagram Graph API には予約投稿エンドポイントが無いため、publish_at が
   指定されても即時公開し、警告ログを残す。
"""

import time
from pathlib import Path

import config
from modules.logger import get_logger
from modules.platform_base import BaseUploader, UploadResult

GRAPH_API_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# コンテナ処理の最大待機 (5秒 x 60回 = 5分)
STATUS_POLL_INTERVAL = 5
STATUS_MAX_POLLS = 60


class InstagramUploader(BaseUploader):
    PLATFORM = "instagram"

    def __init__(self):
        self.logger = get_logger()

    # ------------------------------------------------------------------
    # 認証確認
    # ------------------------------------------------------------------
    def _check_config(self) -> None:
        missing = [
            name
            for name, val in (
                ("INSTAGRAM_ACCESS_TOKEN", config.INSTAGRAM_ACCESS_TOKEN),
                ("INSTAGRAM_BUSINESS_ACCOUNT_ID", config.INSTAGRAM_BUSINESS_ACCOUNT_ID),
            )
            if not val
        ]
        if missing:
            raise ValueError(
                "Instagram の認証情報が未設定です: " + ", ".join(missing) + "\n"
                "README の「Instagram 投稿の設定」に従って .env / Secrets に登録してください。"
            )

    def authenticate(self) -> None:
        """投稿せず設定とトークンの有効性だけ確認する (main.py --auth-only 用)。"""
        import requests

        self._check_config()
        resp = requests.get(
            f"{GRAPH_BASE}/{config.INSTAGRAM_BUSINESS_ACCOUNT_ID}",
            params={"fields": "username", "access_token": config.INSTAGRAM_ACCESS_TOKEN},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Instagram 認証に失敗しました: HTTP {resp.status_code} {resp.text}"
            )
        username = resp.json().get("username", "")
        self.logger.info("Instagram 認証 OK (@%s)", username)

    # ------------------------------------------------------------------
    # 動画を公開 URL にする
    # ------------------------------------------------------------------
    def _to_public_url(self, video_path: Path) -> str:
        if config.PUBLIC_MEDIA_BASE_URL:
            base = config.PUBLIC_MEDIA_BASE_URL.rstrip("/")
            url = f"{base}/{video_path.name}"
            self.logger.info("Instagram: 公開 URL を使用します: %s", url)
            return url

        # フォールバック: 匿名アップローダ (catbox.moe) に一時アップロード
        import requests

        self.logger.info(
            "PUBLIC_MEDIA_BASE_URL 未設定のため catbox.moe に一時アップロードします"
        )
        with open(video_path, "rb") as f:
            resp = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload"},
                files={"fileToUpload": (video_path.name, f, "video/mp4")},
                timeout=300,
            )
        resp.raise_for_status()
        url = resp.text.strip()
        if not url.startswith("http"):
            raise RuntimeError(f"動画の一時アップロードに失敗しました: {url}")
        self.logger.info("Instagram: 一時公開 URL を取得しました: %s", url)
        return url

    # ------------------------------------------------------------------
    # 投稿
    # ------------------------------------------------------------------
    def _build_caption(self, title: str, description: str, tags: list) -> str:
        hashtags = " ".join(
            "#" + t.strip().lstrip("#").replace(" ", "")
            for t in (tags or [])
            if t.strip()
        )
        parts = [title.strip()]
        if description and description.strip():
            parts.append(description.strip())
        if hashtags:
            parts.append(hashtags)
        return "\n\n".join(parts)[:2200]

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

        self._check_config()
        if publish_at:
            self.logger.warning(
                "Instagram Graph API は予約投稿に対応していないため即時公開します (指定: %s)",
                publish_at,
            )

        ig_id = config.INSTAGRAM_BUSINESS_ACCOUNT_ID
        token = config.INSTAGRAM_ACCESS_TOKEN
        caption = self._build_caption(title, description, tags)
        video_url = self._to_public_url(video_path)

        # 1. メディアコンテナ作成 (リール)
        self.logger.info("Instagram: メディアコンテナを作成中")
        create = requests.post(
            f"{GRAPH_BASE}/{ig_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "share_to_feed": "true" if config.INSTAGRAM_SHARE_TO_FEED else "false",
                "access_token": token,
            },
            timeout=120,
        )
        if create.status_code != 200:
            raise RuntimeError(
                f"コンテナ作成に失敗しました: HTTP {create.status_code} {create.text}"
            )
        container_id = create.json()["id"]
        self.logger.info("Instagram: コンテナ作成完了 (id=%s)", container_id)

        # 2. 処理完了までポーリング (動画のダウンロード&エンコード待ち)
        for _ in range(STATUS_MAX_POLLS):
            status = requests.get(
                f"{GRAPH_BASE}/{container_id}",
                params={"fields": "status_code,status", "access_token": token},
                timeout=60,
            )
            status.raise_for_status()
            code = status.json().get("status_code")
            if code == "FINISHED":
                break
            if code == "ERROR":
                raise RuntimeError(
                    f"コンテナ処理に失敗しました: {status.json().get('status')}"
                )
            self.logger.info("Instagram: コンテナ処理中 (%s)... 待機", code)
            time.sleep(STATUS_POLL_INTERVAL)
        else:
            raise RuntimeError("Instagram のコンテナ処理がタイムアウトしました")

        # 3. 公開
        self.logger.info("Instagram: 公開中")
        publish = requests.post(
            f"{GRAPH_BASE}/{ig_id}/media_publish",
            data={"creation_id": container_id, "access_token": token},
            timeout=120,
        )
        if publish.status_code != 200:
            raise RuntimeError(
                f"公開に失敗しました: HTTP {publish.status_code} {publish.text}"
            )
        media_id = publish.json()["id"]

        # 公開後のパーマリンクを取得 (失敗してもアップロード自体は成功扱い)
        permalink = ""
        try:
            perm = requests.get(
                f"{GRAPH_BASE}/{media_id}",
                params={"fields": "permalink", "access_token": token},
                timeout=30,
            )
            if perm.status_code == 200:
                permalink = perm.json().get("permalink", "")
        except Exception as e:
            self.logger.warning("パーマリンクの取得に失敗しました: %s", e)

        self.logger.info("Instagram 投稿完了: %s", permalink or media_id)
        return UploadResult(video_id=media_id, video_url=permalink, publish_at="")
