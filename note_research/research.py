# -*- coding: utf-8 -*-
"""
note 売れる記事リサーチツール ── メイン

keywords.csv に書いたキーワードごとに note を検索し、
「売れている記事(有料 × 人気)」を収集・分析して
output/ に CSV と Markdown レポートを出力します。

使い方:
    python research.py
    python research.py キーワード1 キーワード2 ...   ← keywords.csv の代わりに直接指定
"""
import sys
import csv
from datetime import datetime

import config
from modules.logger import Logger
from modules.note_client import NoteClient
from modules import analyzer, reporter


def load_keywords(args) -> list:
    """コマンドライン引数優先、なければ keywords.csv から読む。"""
    if args:
        return [a.strip() for a in args if a.strip()]
    keywords = []
    if config.KEYWORDS_FILE.exists():
        with open(config.KEYWORDS_FILE, encoding="utf-8-sig") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                kw = row[0].strip()
                if kw and not kw.startswith("#") and kw.lower() != "keyword":
                    keywords.append(kw)
    return keywords


def main():
    # .env があれば読み込む(任意)
    try:
        from dotenv import load_dotenv
        load_dotenv(config.BASE_DIR / ".env")
    except ImportError:
        pass

    log = Logger(config.LOG_DIR)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    keywords = load_keywords(sys.argv[1:])
    if not keywords:
        log.error("リサーチするキーワードがありません。keywords.csv に1行ずつ書いてください。")
        sys.exit(1)

    log.info(f"リサーチ開始: {len(keywords)} キーワード -> {keywords}")

    client = NoteClient(
        user_agent=config.USER_AGENT,
        timeout=config.REQUEST_TIMEOUT,
        interval=config.REQUEST_INTERVAL,
        max_retries=config.MAX_RETRIES,
        logger=log,
    )

    all_items = []
    for kw in keywords:
        log.info(f"  検索中: '{kw}' ...")
        items = client.search(kw, config.MAX_ITEMS_PER_KEYWORD, config.PAGE_SIZE)
        log.info(f"    -> {len(items)} 件取得")
        if not config.INCLUDE_FREE_NOTES:
            items = [it for it in items if it.is_paid]
        all_items.extend(items)

    # キーごとに重複排除(複数キーワードで同じ記事がヒットする場合)
    uniq = {}
    for it in all_items:
        if it.key not in uniq:
            uniq[it.key] = it
    all_items = list(uniq.values())

    if not all_items:
        log.error(
            "記事を取得できませんでした。ネットワーク接続、または note API の仕様変更の"
            "可能性があります。時間をおいて再実行してください。"
        )
        sys.exit(1)

    log.info(f"合計 {len(all_items)} 件(重複除去後)を分析します。")
    result = analyzer.analyze(all_items, config.TOP_N, config.MIN_LIKE_COUNT)

    # AI 考察(任意)
    ai_insight = ""
    if config.USE_AI_INSIGHT:
        log.info("AI 考察を生成中...")
        ai_insight = reporter.generate_ai_insight(result, config.AI_MODEL, log)

    # 出力
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = config.OUTPUT_DIR / f"note_research_{stamp}.csv"
    md_path = config.OUTPUT_DIR / f"note_research_{stamp}.md"

    reporter.write_csv(all_items, csv_path)
    md = reporter.build_markdown(result, ai_insight)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    log.info("─" * 50)
    log.info(f"✅ 完了しました。")
    log.info(f"   レポート: {md_path}")
    log.info(f"   データ  : {csv_path}")
    log.info(f"   有料記事 {result['paid_count']}件 / 分析 {result['analyzed']}件")
    log.info("─" * 50)


if __name__ == "__main__":
    main()
