"""ログ設定とアップロード履歴 (uploaded_log.csv) の管理。"""

import csv
import logging
import sys
from datetime import datetime

import config

UPLOADED_FIELDS = [
    "uploaded_at",
    "date",
    "topic",
    "platform",
    "video_id",
    "video_url",
    "title",
    "publish_at",
]

_logger = None


def get_logger() -> logging.Logger:
    """アプリ共通ロガー。logs/app.log と標準出力へ出す。"""
    global _logger
    if _logger is not None:
        return _logger

    config.ensure_dirs()
    logger = logging.getLogger("auto_video_uploader")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    fh = logging.FileHandler(config.APP_LOG_TXT, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    _logger = logger
    return logger


def log_error(message: str) -> None:
    """エラーを logs/error_log.txt に追記し、通常ログにも残す。"""
    config.ensure_dirs()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(config.ERROR_LOG_TXT, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")
    get_logger().error(message)


# ---------------------------------------------------------------------------
# uploaded_log.csv
# ---------------------------------------------------------------------------

def _normalize_topic(topic: str) -> str:
    return " ".join(topic.split()).strip()


def load_uploaded_topics() -> set:
    """アップロード済みの (topic, platform) の集合を返す。重複投稿防止に使う。"""
    uploaded = set()
    if not config.UPLOADED_LOG_CSV.exists():
        return uploaded
    # Excel で開いて保存されても読めるよう両対応
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(config.UPLOADED_LOG_CSV, encoding=enc, newline="") as f:
                for row in csv.DictReader(f):
                    topic = _normalize_topic(row.get("topic", ""))
                    platform = (row.get("platform") or "youtube").strip().lower()
                    if topic:
                        uploaded.add((topic, platform))
            return uploaded
        except UnicodeDecodeError:
            continue
    return uploaded


def is_already_uploaded(topic: str, platform: str) -> bool:
    return (_normalize_topic(topic), platform.strip().lower()) in load_uploaded_topics()


def append_uploaded_log(record: dict) -> None:
    """アップロード結果を uploaded_log.csv に追記する。"""
    record = dict(record)
    record.setdefault("uploaded_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    is_new = not config.UPLOADED_LOG_CSV.exists()
    with open(config.UPLOADED_LOG_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=UPLOADED_FIELDS, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(record)
