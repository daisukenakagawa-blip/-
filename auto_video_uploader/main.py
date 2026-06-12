"""自動動画生成 & YouTube アップロード パイプライン。

実行例:
    python main.py                  # 投稿対象 (status=pending) の先頭 1 件を処理
    python main.py --all            # pending を全件処理
    python main.py --no-upload      # 動画生成まで(アップロードしない)
    python main.py --auth-only      # YouTube の OAuth 認証だけ行う
    python main.py --topic "..."    # topics.csv を使わず単発で生成

途中で失敗しても、生成済みの台本 / 音声 / 動画はファイルとして残るため、
再実行すればその続きから処理される(冪等)。
"""

import argparse
import csv
import hashlib
import re
import sys
import traceback
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import config
from modules import script_generator, voice_generator, video_editor, thumbnail_generator
from modules.logger import append_uploaded_log, get_logger, is_already_uploaded, log_error
from modules.platform_base import get_uploader

TOPIC_FIELDS = ["date", "topic", "platform", "status", "background", "script"]


# ---------------------------------------------------------------------------
# topics.csv
# ---------------------------------------------------------------------------

def load_topics() -> list:
    if not config.TOPICS_CSV.exists():
        raise FileNotFoundError(f"topics.csv が見つかりません: {config.TOPICS_CSV}")
    # Excel で編集・保存されると Shift-JIS になることがあるため両対応で読む
    for enc in ("utf-8-sig", "cp932"):
        try:
            with open(config.TOPICS_CSV, encoding=enc, newline="") as f:
                return [row for row in csv.DictReader(f)]
        except UnicodeDecodeError:
            continue
    raise ValueError("topics.csv の文字コードを判別できませんでした")


def save_topics(rows: list) -> None:
    # BOM 付き UTF-8 で保存すると Excel でも文字化けせずに開ける
    with open(config.TOPICS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=TOPIC_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def mark_topic_done(topic: str, platform: str) -> None:
    rows = load_topics()
    for row in rows:
        if row.get("topic", "").strip() == topic and (
            row.get("platform", "youtube").strip().lower() == platform
        ):
            row["status"] = "done"
    save_topics(rows)


def _sheet_csv_url(url: str) -> str:
    """スプレッドシートの URL を CSV 取得用 URL に正規化する。

    「ウェブに公開(CSV)」の URL はそのまま、普通の共有リンク
    (…/spreadsheets/d/<ID>/edit?usp=sharing) は export?format=csv に変換する。
    共有リンクの場合、シートの共有設定が「リンクを知っている全員」である必要がある。
    """
    url = url.strip()
    # 公開済みURL (…/d/e/2PACX-…/pub?output=csv) はそのまま使う
    m = re.search(r"docs\.google\.com/spreadsheets/d/(?!e/)([\w-]+)", url)
    if m and "/export" not in url and "output=csv" not in url:
        return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=csv"
    return url


def sync_topics_from_sheet() -> None:
    """Google スプレッドシート(ウェブに公開した CSV)から topics.csv へ取り込む。

    スマホでシートに行を足すだけでテーマ追加できるようにする仕組み。
    既存の (topic, platform) は上書きせず、新しい行だけ pending で追加する。
    取得に失敗してもローカルの topics.csv だけで処理を続行する。
    """
    if not config.TOPICS_SHEET_URL:
        return
    logger = get_logger()
    try:
        import io

        import requests

        resp = requests.get(_sheet_csv_url(config.TOPICS_SHEET_URL), timeout=30)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        sheet_rows = []
        for row in csv.DictReader(io.StringIO(resp.text)):
            row = {
                (k or "").strip().lower().lstrip("\ufeff"): (v or "").strip()
                for k, v in row.items()
            }
            topic = row.get("topic", "")
            if not topic:
                continue
            sheet_rows.append(
                {
                    "date": row.get("date", ""),
                    "topic": topic,
                    "platform": (row.get("platform") or "youtube").lower(),
                    "status": (row.get("status") or "pending").lower(),
                    "background": row.get("background", ""),
                    "script": row.get("script", ""),
                }
            )
    except Exception as e:
        logger.warning("スプレッドシートの取得に失敗。topics.csv のみで続行します: %s", e)
        return

    rows = load_topics() if config.TOPICS_CSV.exists() else []
    by_key = {
        (r.get("topic", "").strip(), (r.get("platform") or "youtube").strip().lower()): r
        for r in rows
    }
    added = updated = 0
    for s in sheet_rows:
        key = (s["topic"], s["platform"])
        if key in by_key:
            # 既存行でも、シート側で background / script が追記・変更されたら反映する
            r = by_key[key]
            for field in ("background", "script"):
                if s[field] and (r.get(field) or "") != s[field]:
                    r[field] = s[field]
                    updated += 1
            continue
        rows.append(s)
        by_key[key] = s
        added += 1
    if added or updated:
        save_topics(rows)
        logger.info("スプレッドシートから取り込み: 追加 %d 件 / 更新 %d 件", added, updated)


def resolve_background(rows: list, target_row: dict) -> str:
    """対象行に適用する背景URLを決める。

    シートの background 列は「一度貼ればそれ以降の行にも適用」される仕様。
    対象行までの行を順に見て、最後に指定された URL を引き継ぐ。
    """
    bg = ""
    for r in rows:
        if (r.get("background") or "").strip():
            bg = r["background"].strip()
        if r is target_row:
            break
    return bg


def pending_topics(rows: list) -> list:
    result = []
    for row in rows:
        if (row.get("status") or "").strip().lower() != "pending":
            continue
        if not (row.get("topic") or "").strip():
            continue
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# 予約投稿時刻
# ---------------------------------------------------------------------------

def _get_timezone():
    """設定されたタイムゾーンを返す。tzdata 未導入の Windows でも止まらないよう
    取得に失敗した場合は日本時間 (+09:00) にフォールバックする。"""
    try:
        return ZoneInfo(config.TIMEZONE)
    except Exception:
        get_logger().warning(
            "タイムゾーン情報 (%s) を取得できないため日本時間(+09:00)を使用します。"
            "`pip install tzdata` で解消できます", config.TIMEZONE,
        )
        return timezone(timedelta(hours=9), "JST")


def compute_publish_at(date_str: str) -> str | None:
    """topics.csv の date が未来日なら RFC3339 の予約投稿時刻を返す。

    過去日・当日・パース不能の場合は None(即時投稿)。
    """
    date_str = (date_str or "").strip()
    if not date_str:
        return None
    # スプレッドシートからは 2026/06/18 形式で来ることもあるため両対応
    target = None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            target = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue
    if target is None:
        get_logger().warning("date のパースに失敗したため即時投稿します: %s", date_str)
        return None
    if target <= date.today():
        return None
    hour, minute = (int(x) for x in config.PUBLISH_TIME.split(":"))
    dt = datetime(target.year, target.month, target.day, hour, minute,
                  tzinfo=_get_timezone())
    return dt.isoformat()


# ---------------------------------------------------------------------------
# 1テーマぶんのパイプライン
# ---------------------------------------------------------------------------

def make_stem(date_str: str, topic: str) -> str:
    digest = hashlib.md5(topic.strip().encode("utf-8")).hexdigest()[:10]
    date_part = (date_str or "nodate").strip() or "nodate"
    return f"{date_part}_{digest}"


def process_topic(row: dict, no_upload: bool = False, background_url: str = "") -> bool:
    """1テーマを 台本→音声→動画→サムネ→アップロード まで処理する。

    成功時 True。失敗時は error_log.txt に記録して False(status は pending のまま
    残るため、次回実行時にリトライされる)。
    """
    logger = get_logger()
    topic = row["topic"].strip()
    platform = (row.get("platform") or "youtube").strip().lower()
    date_str = (row.get("date") or "").strip()
    stem = make_stem(date_str, topic)

    logger.info("=" * 60)
    logger.info("テーマ処理開始: %s (platform=%s, stem=%s)", topic, platform, stem)

    try:
        # --- 重複投稿防止 -------------------------------------------------
        if is_already_uploaded(topic, platform):
            logger.info("アップロード済みのためスキップします: %s", topic)
            mark_topic_done(topic, platform)
            return True

        # --- 1. 台本 (シート持ち込み > 生成済み再利用 > 新規生成) ----------
        script_path = config.SCRIPTS_DIR / f"{stem}.json"
        user_script = (row.get("script") or "").strip()
        if script_path.exists():
            logger.info("生成済みの台本を再利用します: %s", script_path)
            content = script_generator.load_script(script_path)
        elif user_script:
            logger.info("シートの script 列の台本をそのまま使用します")
            content = script_generator.build_from_user_script(topic, user_script)
            script_generator.save_script(content, script_path)
        else:
            content = script_generator.generate(topic)
            script_generator.save_script(content, script_path)
            logger.info("台本を保存しました: %s", script_path)

        # --- 2. ナレーション音声 ------------------------------------------
        audio_path = voice_generator.find_existing_audio(stem)
        if audio_path:
            logger.info("生成済みの音声を再利用します: %s", audio_path)
        else:
            audio_path = voice_generator.generate(content["script_lines"], stem)
            logger.info("音声を保存しました: %s", audio_path)

        # --- 3. 動画合成 ---------------------------------------------------
        video_path = config.VIDEOS_DIR / f"{stem}.mp4"
        if video_path.exists() and video_path.stat().st_size > 0:
            logger.info("生成済みの動画を再利用します: %s", video_path)
        else:
            video_path = video_editor.create_video(
                content["title"], content["script_lines"], audio_path, stem,
                background_url=background_url,
            )

        # --- 4. サムネイル -------------------------------------------------
        thumb_path = config.THUMBNAILS_DIR / f"{stem}.jpg"
        if not thumb_path.exists():
            thumb_path = thumbnail_generator.create_thumbnail(content["title"], stem)

        # --- 5. アップロード -----------------------------------------------
        if no_upload:
            logger.info("--no-upload 指定のためアップロードをスキップしました")
            return True

        publish_at = compute_publish_at(date_str)
        if publish_at:
            logger.info("予約投稿: %s", publish_at)

        uploader = get_uploader(platform)
        result = uploader.upload(
            video_path=video_path,
            title=content["title"],
            description=content["description"],
            tags=content["tags"],
            thumbnail_path=thumb_path,
            publish_at=publish_at,
        )

        # --- 6. ログ保存 & ステータス更新 ----------------------------------
        append_uploaded_log(
            {
                "date": date_str,
                "topic": topic,
                "platform": platform,
                "video_id": result.video_id,
                "video_url": result.video_url,
                "title": content["title"],
                "publish_at": result.publish_at,
            }
        )
        mark_topic_done(topic, platform)
        logger.info("テーマ処理完了: %s", topic)
        return True

    except Exception as e:
        log_error(f"テーマ「{topic}」の処理に失敗: {e}\n{traceback.format_exc()}")
        return False


# ---------------------------------------------------------------------------
# エントリポイント
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="動画自動生成 & YouTube アップロード")
    parser.add_argument("--all", action="store_true", help="pending のテーマを全件処理する")
    parser.add_argument("--no-upload", action="store_true", help="動画生成まで行い、アップロードしない")
    parser.add_argument("--auth-only", action="store_true", help="YouTube の OAuth 認証のみ行う")
    parser.add_argument("--topic", help="topics.csv を使わず、このテーマを単発処理する")
    parser.add_argument("--date", help="--topic 使用時の投稿予定日 (YYYY-MM-DD)")
    args = parser.parse_args()

    config.ensure_dirs()
    logger = get_logger()

    if args.auth_only:
        from modules.youtube_uploader import YouTubeUploader

        YouTubeUploader().authenticate()
        return 0

    if args.topic:
        row = {
            "date": args.date or "",
            "topic": args.topic,
            "platform": "youtube",
            "status": "pending",
        }
        return 0 if process_topic(row, no_upload=args.no_upload) else 1

    # スプレッドシート連携が設定されていれば、最新テーマを取り込んでから処理する
    sync_topics_from_sheet()

    all_rows = load_topics()
    targets = pending_topics(all_rows)
    if not targets:
        logger.info("処理対象 (status=pending) のテーマがありません")
        return 0

    if not args.all:
        targets = targets[:1]

    failed = 0
    for row in targets:
        background_url = resolve_background(all_rows, row)
        if not process_topic(row, no_upload=args.no_upload, background_url=background_url):
            failed += 1

    logger.info("完了: %d 件処理 / %d 件失敗", len(targets), failed)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
