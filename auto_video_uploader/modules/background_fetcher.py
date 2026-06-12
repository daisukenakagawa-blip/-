"""背景動画の自動取得。

- download_custom: ユーザーが指定した URL (Google ドライブ共有リンク対応) から取得
- fetch_background: Pexels API から自動取得 (PEXELS_API_KEY 設定時のみ)
"""

import hashlib
import random
import re
from pathlib import Path

import requests

import config
from modules.logger import get_logger

SEARCH_URL = "https://api.pexels.com/videos/search"


def _to_direct_url(url: str) -> str:
    """Google ドライブの共有リンクを直接ダウンロード URL に変換する。

    drive.usercontent.google.com + confirm=t を使うことで、100MB 超の
    ファイルでも「ウイルススキャンできません」の確認ページを回避できる。
    """
    m = re.search(r"drive\.google\.com/file/d/([\w-]+)", url)
    if not m:
        m = re.search(r"drive\.google\.com/open\?id=([\w-]+)", url)
    if m:
        return (
            "https://drive.usercontent.google.com/download"
            f"?id={m.group(1)}&export=download&confirm=t"
        )
    return url


def _guess_extension(content_type: str, data: bytes) -> str:
    """Content-Type と先頭バイトから拡張子を推定する(写真・音声にも対応)。"""
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[8:12] == b"WEBP":
        return ".webp"
    if data[:3] == b"ID3":
        return ".mp3"
    mapping = {
        "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
        "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
        "audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/wav": ".wav",
        "audio/x-wav": ".wav", "audio/ogg": ".ogg", "audio/mp4": ".m4a",
    }
    return mapping.get(content_type.split(";")[0].strip().lower(), ".mp4")


def download_custom(url: str, prefix: str = "background_custom") -> Path | None:
    """シートで指定された素材 (動画/写真/音声) の URL を取得してパスを返す。失敗時は None。"""
    logger = get_logger()
    url = url.strip()
    if not url:
        return None

    cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    cached = list(config.ASSETS_DIR.glob(f"{prefix}_{cache_key}.*"))
    if cached and cached[0].stat().st_size > 0:
        return cached[0]

    max_bytes = int(config.MAX_MEDIA_MB * 1024 * 1024)
    try:
        with requests.get(
            _to_direct_url(url), timeout=300, allow_redirects=True, stream=True
        ) as resp:
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "")
            if "text/html" in ctype:
                logger.warning(
                    "素材URLがファイルではなくWebページを返しました。Google ドライブの場合は"
                    "共有設定を「リンクを知っている全員」にしてください: %s", url,
                )
                return None
            length = int(resp.headers.get("content-length") or 0)
            if length > max_bytes:
                logger.warning(
                    "素材が大きすぎます (%d MB > 上限 %d MB)。"
                    "スマホで30〜60秒にトリミングしてから送ってください: %s",
                    length // (1024 * 1024), config.MAX_MEDIA_MB, url,
                )
                return None

            # 分割ダウンロード (大容量でもメモリを使い切らない)
            tmp_path = config.ASSETS_DIR / f"{prefix}_{cache_key}.part"
            head = b""
            written = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    if len(head) < 16:
                        head += chunk[:16]
                    written += len(chunk)
                    if written > max_bytes:
                        f.close()
                        tmp_path.unlink(missing_ok=True)
                        logger.warning(
                            "素材が上限 %d MB を超えたため中断しました。"
                            "短くトリミングして送り直してください: %s",
                            config.MAX_MEDIA_MB, url,
                        )
                        return None
                    f.write(chunk)

        ext = _guess_extension(ctype, head)
        out_path = config.ASSETS_DIR / f"{prefix}_{cache_key}{ext}"
        tmp_path.rename(out_path)
        logger.info(
            "指定された素材を取得しました (%s, %d KB)",
            ext, out_path.stat().st_size // 1024,
        )
        return out_path
    except Exception as e:
        logger.warning("素材URLの取得に失敗。既定の素材で続行します: %s", e)
        return None


def fetch_background() -> Path | None:
    """縦型動画を assets/ にダウンロードしてパスを返す。失敗時は None。"""
    if not config.PEXELS_API_KEY:
        return None

    logger = get_logger()
    out_path = config.ASSETS_DIR / "background_pexels.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    try:
        resp = requests.get(
            SEARCH_URL,
            headers={"Authorization": config.PEXELS_API_KEY},
            params={
                "query": config.BACKGROUND_KEYWORD,
                "orientation": "portrait",
                "per_page": 20,
            },
            timeout=30,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        random.shuffle(videos)

        for video in videos:
            # 縦型かつ 720p 以上で、なるべく軽いファイルを選ぶ
            candidates = [
                f
                for f in video.get("video_files", [])
                if f.get("height") and f.get("width")
                and f["height"] > f["width"] and f["height"] >= 1280
            ]
            if not candidates:
                continue
            file_info = min(candidates, key=lambda f: f["height"])

            logger.info(
                "Pexels から背景動画を取得します (id=%s, %sx%s)",
                video.get("id"), file_info["width"], file_info["height"],
            )
            data = requests.get(file_info["link"], timeout=180)
            data.raise_for_status()
            out_path.write_bytes(data.content)
            return out_path

        logger.warning("Pexels で条件に合う縦型動画が見つかりませんでした: %s",
                       config.BACKGROUND_KEYWORD)
    except Exception as e:
        logger.warning("Pexels からの背景取得に失敗。既定の背景で続行します: %s", e)
    return None
