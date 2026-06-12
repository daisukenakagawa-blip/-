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
    """Google ドライブの共有リンクを直接ダウンロード URL に変換する。"""
    m = re.search(r"drive\.google\.com/file/d/([\w-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    m = re.search(r"drive\.google\.com/open\?id=([\w-]+)", url)
    if m:
        return f"https://drive.google.com/uc?export=download&id={m.group(1)}"
    return url


def download_custom(url: str) -> Path | None:
    """シートで指定された背景動画 URL をダウンロードしてパスを返す。失敗時は None。"""
    logger = get_logger()
    url = url.strip()
    if not url:
        return None

    cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
    out_path = config.ASSETS_DIR / f"background_custom_{cache_key}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    try:
        resp = requests.get(_to_direct_url(url), timeout=300, allow_redirects=True)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "text/html" in ctype:
            logger.warning(
                "背景URLが動画ではなくWebページを返しました。Google ドライブの場合は"
                "共有設定を「リンクを知っている全員」にしてください: %s", url,
            )
            return None
        out_path.write_bytes(resp.content)
        logger.info("指定された背景動画を取得しました (%d KB)", out_path.stat().st_size // 1024)
        return out_path
    except Exception as e:
        logger.warning("背景URLの取得に失敗。既定の背景で続行します: %s", e)
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
