"""X 自動投稿ツールのエントリポイント。

フロー:
  1) (任意) Google スプレッドシートから topics.csv を更新
  2) まだ投稿していないテーマを選ぶ
  3) Claude API で投稿文を生成(未設定ならテンプレート)
  4) assets/images からランダムに画像を選んで添付
  5) X へ投稿し、posted_log.csv に記録

使い方:
  python main.py            # 通常実行(設定本数だけ投稿)
  python main.py --test     # X への接続テストだけ行う
  python main.py --dry-run  # 投稿せず生成内容のプレビューだけ
"""

import argparse
import csv
import io
import random
import sys

import config
from modules import tweet_generator, x_client
from modules.logger import (
    append_posted_log,
    get_logger,
    is_already_posted,
    load_posted_topics,
    log_error,
    reset_posted_log,
)

log = get_logger()

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


# ---------------------------------------------------------------------------
# テーマ (topics.csv)
# ---------------------------------------------------------------------------

def _read_csv_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def sync_topics_from_sheet() -> None:
    """TOPICS_SHEET_URL があれば、その内容を topics.csv に取り込む。"""
    if not config.TOPICS_SHEET_URL:
        return
    try:
        import requests

        resp = requests.get(config.TOPICS_SHEET_URL, timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        rows = _read_csv_rows(resp.text)
        topics = [(r.get("topic") or "").strip() for r in rows]
        topics = [t for t in topics if t]
        if topics:
            with open(config.TOPICS_CSV, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["topic"])
                for t in topics:
                    writer.writerow([t])
            log.info("スプレッドシートから %d 件のテーマを取り込みました", len(topics))
    except Exception as e:  # noqa: BLE001
        log_error(f"スプレッドシートの取り込みに失敗(topics.csv を使用): {e}")


def load_topics() -> list[str]:
    """topics.csv からテーマ一覧を読む。topic 列、または1列目を使う。"""
    if not config.TOPICS_CSV.exists():
        return []
    for enc in ("utf-8-sig", "utf-8", "cp932"):
        try:
            with open(config.TOPICS_CSV, encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            break
        except UnicodeDecodeError:
            continue
    else:
        return []

    if not rows:
        return []

    header = [c.strip().lower() for c in rows[0]]
    topics: list[str] = []
    if "topic" in header:
        idx = header.index("topic")
        for r in rows[1:]:
            if len(r) > idx and r[idx].strip():
                topics.append(r[idx].strip())
    else:
        # ヘッダ無し: 1列目をテーマとして扱う
        for r in rows:
            if r and r[0].strip():
                topics.append(r[0].strip())
    return topics


def pick_pending_topics(count: int) -> list[str]:
    """未投稿のテーマを最大 count 件選ぶ。全部投稿済みなら設定次第でリセット。"""
    topics = load_topics()
    if not topics:
        return []

    pending = [t for t in topics if not is_already_posted(t)]
    if not pending and config.RECYCLE_TOPICS:
        log.info("全テーマ投稿済みのため履歴をリセットして最初から使います")
        reset_posted_log()
        pending = topics

    # 重複を除きつつ順序を保つ
    seen = set()
    unique = []
    for t in pending:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:count]


# ---------------------------------------------------------------------------
# 画像
# ---------------------------------------------------------------------------

def pick_image() -> str | None:
    """assets/images からランダムに1枚選ぶ。無ければ None。"""
    if not config.ATTACH_IMAGE:
        return None
    if not config.IMAGES_DIR.exists():
        return None
    images = [
        p for p in config.IMAGES_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    ]
    if not images:
        log.info("assets/images に画像が無いためテキストのみで投稿します")
        return None
    return str(random.choice(images))


# ---------------------------------------------------------------------------
# 実行
# ---------------------------------------------------------------------------

def run_once(topic: str, dry_run: bool) -> bool:
    text = tweet_generator.generate_post(topic)
    image_path = pick_image()

    print("-" * 50)
    print(f"テーマ: {topic}")
    print(f"画像  : {image_path or '(なし)'}")
    print("本文  :")
    print(text)
    print("-" * 50)

    if dry_run:
        log.info("[DRY-RUN] 投稿はスキップしました")
        return True

    try:
        result = x_client.post(text, image_path)
    except Exception as e:  # noqa: BLE001
        log_error(f"投稿に失敗: {topic}: {e}")
        return False

    append_posted_log(
        {
            "topic": topic,
            "text": text.replace("\n", " "),
            "tweet_id": result["tweet_id"],
            "tweet_url": result["tweet_url"],
            "image": image_path or "",
        }
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="X 自動投稿ツール")
    parser.add_argument("--test", action="store_true", help="X への接続テストのみ")
    parser.add_argument("--dry-run", action="store_true", help="投稿せず生成内容のプレビューのみ")
    parser.add_argument("--count", type=int, default=None, help="投稿本数(既定: 設定値)")
    args = parser.parse_args()

    config.ensure_dirs()

    if args.test:
        try:
            username = x_client.verify_credentials()
            print(f"接続成功: @{username} として投稿できます。")
            return 0
        except Exception as e:  # noqa: BLE001
            log_error(f"接続テスト失敗: {e}")
            print(f"接続失敗: {e}")
            return 1

    dry_run = args.dry_run or config.DRY_RUN
    if not dry_run and not config.x_credentials_ready():
        print(
            "X API の認証情報が未設定です。②かんたん設定.bat または .env を設定してください。\n"
            "(設定前に内容を確認したい場合は --dry-run を付けて実行できます)"
        )
        return 1

    count = args.count if args.count is not None else config.POSTS_PER_RUN
    topics = pick_pending_topics(count)
    if not topics:
        log.info("投稿できるテーマがありません。topics.csv にテーマを追加してください。")
        print("topics.csv に投稿テーマを追加してください。")
        return 0

    log.info("今回の投稿テーマ(%d件): %s", len(topics), topics)
    ok = 0
    for topic in topics:
        if run_once(topic, dry_run):
            ok += 1

    log.info("完了: %d/%d 件を処理しました", ok, len(topics))
    return 0 if ok == len(topics) else 1


if __name__ == "__main__":
    sys.exit(main())
