"""動画ファイルを一時的に公開 URL 化する。

Instagram Reels の Graph API は「公開 URL から動画を取得する」方式のため、
ローカルの mp4 をそのまま渡せない。ここでは無料の一時ホスティングに
アップロードして URL を得る(Instagram がダウンロードした後は不要になる
ので、24 時間で自動削除されるサービスを優先する)。

自前のサーバーやストレージがある場合は、環境変数 PUBLIC_VIDEO_BASE_URL に
「動画ファイル名を付けるとアクセスできる URL」を設定すれば、そちらに
アップロード済みという前提で URL 組み立てのみ行う。
"""

from pathlib import Path

import requests

import config
from modules.logger import get_logger

TIMEOUT = 300  # 大きめの動画でも耐えられるように


def _upload_litterbox(path: Path) -> str:
    """litterbox.catbox.moe (24時間で自動削除・無料・1GBまで)。"""
    with open(path, "rb") as f:
        resp = requests.post(
            "https://litterbox.catbox.moe/resources/internals/api.php",
            data={"reqtype": "fileupload", "time": "24h"},
            files={"fileToUpload": (path.name, f, "video/mp4")},
            timeout=TIMEOUT,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"litterbox の応答が不正です: {url[:200]}")
    return url


def _upload_0x0(path: Path) -> str:
    """0x0.st (フォールバック)。expires 指定で自動削除。"""
    with open(path, "rb") as f:
        resp = requests.post(
            "https://0x0.st",
            data={"expires": "24"},
            files={"file": (path.name, f, "video/mp4")},
            headers={"User-Agent": "auto-video-uploader/1.0"},
            timeout=TIMEOUT,
        )
    resp.raise_for_status()
    url = resp.text.strip()
    if not url.startswith("http"):
        raise RuntimeError(f"0x0.st の応答が不正です: {url[:200]}")
    return url


def publish_temporarily(path: Path) -> str:
    """動画を一時公開 URL 化して返す。失敗したら例外を投げる。"""
    logger = get_logger()
    if config.PUBLIC_VIDEO_BASE_URL:
        url = config.PUBLIC_VIDEO_BASE_URL.rstrip("/") + "/" + path.name
        logger.info("PUBLIC_VIDEO_BASE_URL を使用: %s", url)
        return url

    errors = []
    for name, fn in (("litterbox", _upload_litterbox), ("0x0.st", _upload_0x0)):
        try:
            logger.info("一時公開ホスト (%s) へアップロード中: %s", name, path.name)
            url = fn(path)
            logger.info("一時公開 URL: %s (24時間で自動削除)", url)
            return url
        except Exception as e:
            errors.append(f"{name}: {e}")
            logger.warning("一時公開ホスト %s が失敗。次を試します: %s", name, e)
    raise RuntimeError("動画の一時公開に失敗しました: " + " / ".join(errors))
