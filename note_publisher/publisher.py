# -*- coding: utf-8 -*-
"""
note 自動投稿ツール ── メイン

note_writer/articles の Markdown 記事を読み込み、note に下書き保存(既定)/
公開/予約投稿します。重複投稿は posted_log.csv で防止します。

使い方:
    python publisher.py                 # 既定モード(config.PUBLISH_MODE)で投稿
    python publisher.py --mode draft    # モードを上書き(draft / publish / schedule)
    python publisher.py path/to/article.md  # 特定の1ファイルだけ投稿

※ 先に login.py を1回実行してログインセッションを保存しておいてください。
"""
import sys
import time
from pathlib import Path

import config
from modules.logger import Logger
from modules import article_loader, posted_log
from modules.note_poster import NotePoster


def parse_args(argv):
    mode = config.PUBLISH_MODE
    files = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
            i += 2
            continue
        if a.endswith(".md"):
            files.append(Path(a))
        i += 1
    return mode, files


def main():
    log = Logger(config.LOG_DIR)
    mode, files = parse_args(sys.argv[1:])

    if mode not in ("draft", "publish", "schedule"):
        log.error(f"不明なモード: {mode}（draft / publish / schedule のいずれか）")
        sys.exit(1)

    if not config.SESSION_FILE.exists():
        log.error(
            "ログインセッションがありません。先に『python login.py』を実行して"
            "noteにログインしてください。"
        )
        sys.exit(1)

    # 記事の読み込み
    if files:
        articles = [article_loader.load_article(p) for p in files]
    else:
        articles = article_loader.load_all(config.ARTICLES_DIR)
    if not articles:
        log.error(f"記事が見つかりません: {config.ARTICLES_DIR}")
        sys.exit(1)

    # 重複除外
    done = posted_log.load_posted_files(config.POSTED_LOG)
    queue = [a for a in articles if a.path.name not in done]
    skipped = len(articles) - len(queue)
    if skipped:
        log.info(f"投稿済みを {skipped} 件スキップしました。")
    if not queue:
        log.info("新たに投稿する記事はありません。")
        return

    queue = queue[: config.MAX_POSTS_PER_RUN]
    log.info("─" * 50)
    log.info(f"モード: {mode} / 今回の投稿対象: {len(queue)}件")
    if mode != "draft":
        log.warn("⚠ draft 以外のモードです。内容が自動で公開/予約されます。")
    log.info("─" * 50)

    poster = NotePoster(config, log)
    poster.start(use_session=True)
    success = 0
    posted_titles = []
    try:
        if not poster.is_logged_in():
            log.error(
                "ログイン状態が確認できませんでした。『python login.py』で再ログイン"
                "してください。"
            )
            return

        for idx, art in enumerate(queue, 1):
            log.info(f"[{idx}/{len(queue)}] {art.path.name}")
            log.info(f"  タイトル: {art.title}  / 価格: ¥{art.price}  / 無料部 {art.free_line_count}行")
            res = poster.post_article(art, mode)
            if res["ok"]:
                success += 1
                posted_titles.append(art.title)
                posted_log.record(
                    config.POSTED_LOG, art.path.name, art.title, mode, res["note_url"]
                )
                log.info(f"  ✅ {res['message']}")
                log.info(f"     URL: {res['note_url']}")
            else:
                log.error(f"  ❌ 失敗: {res['message']}")

            if idx < len(queue):
                log.info(f"  次の投稿まで {config.INTERVAL_BETWEEN_POSTS} 秒待機...")
                time.sleep(config.INTERVAL_BETWEEN_POSTS)
    finally:
        poster.stop()

    log.info("─" * 50)
    log.info(f"完了: 成功 {success} / {len(queue)} 件")
    if mode == "draft":
        log.info("note の『下書き一覧』を開いて、内容と有料設定を確認してから公開してください。")
    log.info("─" * 50)

    # LINE 通知(任意)
    if config.NOTIFY_LINE and posted_titles:
        send_line_notification(posted_titles, mode, log)


def send_line_notification(titles, mode, log):
    try:
        from modules import line_notifier
    except ImportError:
        return
    if not line_notifier.is_configured():
        log.info("LINE通知はトークン未設定のためスキップしました。")
        return
    label = {"draft": "下書き保存", "publish": "公開", "schedule": "予約投稿"}.get(mode, mode)
    lines = [f"✅ noteに{len(titles)}本を{label}しました"]
    for i, t in enumerate(titles[:15], 1):
        lines.append(f"{i}. {t}")
    if mode == "draft":
        lines.append("\n▶ noteの下書き一覧で内容と有料設定を確認し、公開してください。")
    line_notifier.notify("\n".join(lines), logger=log)


if __name__ == "__main__":
    main()
