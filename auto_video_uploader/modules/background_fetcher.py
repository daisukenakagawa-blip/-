"""Pexels (無料素材サイト) から縦型の背景動画を自動取得する。

PEXELS_API_KEY が設定されている場合のみ動作する。
取得済みファイルがあれば再利用し、API を無駄に叩かない。
"""

import random
from pathlib import Path

import requests

import config
from modules.logger import get_logger

SEARCH_URL = "https://api.pexels.com/videos/search"


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
