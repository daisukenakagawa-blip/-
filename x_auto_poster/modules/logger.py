"""ログ設定と投稿履歴 (posted_log.csv) の管理。"""

import csv
import logging
import sys
from datetime import datetime

import config

POSTED_FIELDS = [
    "posted_at",
    "topic",
    "text",
    "tweet_id",
    "tweet_url",
    "image",
]

_logger = None


def get_logger() -> logging.Logger:
    """アプリ共通ロガー。logs/app.log と標準出力へ出す。"""
    global _logger
    if _logger is not None:
        return _logger

    config.ensure_dirs()
    logger = logging.getLogger("x_auto_poster")
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
# posted_log.csv
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return " ".join((text or "").split()).strip()


def load_posted_topics() -> set:
    """投稿済みテーマの集合を返す。重複投稿防止に使う。"""
    posted = set()
    if not config.POSTED_LOG_CSV.exists():
        return posted
    # Excel で開いて保存されても読めるよう両対応
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(config.POSTED_LOG_CSV, encoding=enc, newline="") as f:
                for row in csv.DictReader(f):
                    topic = _normalize(row.get("topic", ""))
                    if topic:
                        posted.add(topic)
            return posted
        except UnicodeDecodeError:
            continue
    return posted


def is_already_posted(topic: str) -> bool:
    return _normalize(topic) in load_posted_topics()


def append_posted_log(record: dict) -> None:
    """投稿結果を posted_log.csv に追記する。"""
    record = dict(record)
    record.setdefault("posted_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    is_new = not config.POSTED_LOG_CSV.exists()
    with open(config.POSTED_LOG_CSV, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=POSTED_FIELDS, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(record)


def reset_posted_log() -> None:
    """投稿履歴を消す(テーマを最初から使い回すとき用)。"""
    if config.POSTED_LOG_CSV.exists():
        config.POSTED_LOG_CSV.unlink()
