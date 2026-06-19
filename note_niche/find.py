# -*- coding: utf-8 -*-
"""
note 勝てるニッチ発掘ツール ── メイン

候補キーワードごとに note の実データを集め、「需要はあるのに有料競合が弱い」
=無名でも売れる“すき間”をスコア化してレポートします。

使い方:
  python find.py                          # seeds.csv → (AIで候補展開) → 採点
  python find.py "経理 在宅 副業" "保育士 復職 不安"   # キーワードを直接採点
"""
import sys
import time
from datetime import datetime

import config
import note_client
import scorer
import candidates as cand
import reporter
from logger import Logger


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(config.BASE_DIR / ".env")
    except ImportError:
        pass

    log = Logger(config.LOG_DIR)
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    keywords = cand.build_candidates(sys.argv[1:], config, log)
    if not keywords:
        log.error("候補キーワードがありません。seeds.csv に興味を書くか、引数で指定してください。")
        sys.exit(1)
    log.info(f"採点対象 {len(keywords)} キーワード")

    results = []
    for i, kw in enumerate(keywords, 1):
        log.info(f"[{i}/{len(keywords)}] note調査: '{kw}'")
        items = note_client.fetch_top_notes(
            kw, config.NOTES_PER_KEYWORD, config.REQUEST_INTERVAL, log)
        r = scorer.score_niche(kw, items, config)
        results.append(r)
        log.info(f"    → {r['verdict']}（スコア{r['opportunity']} / 需要{r['demand_engagement']} "
                 f"/ 有料最強{r['paid_top_likes']} / 有料{r['n_paid']}本）")
        time.sleep(config.REQUEST_INTERVAL)

    if all(r["n_total"] == 0 for r in results):
        log.error("noteからデータを取得できませんでした（ネット制限/仕様変更）。時間をおいて再実行してください。")
        sys.exit(1)

    results.sort(key=lambda x: x["opportunity"], reverse=True)
    top = [r for r in results if r["verdict"] == "狙い目"][: config.TOP_N_REPORT]

    ai_text = ""
    if config.USE_AI_ANALYSIS and top:
        log.info("狙い目ニッチにAIで攻略案を付与中…")
        ai_text = reporter.ai_analysis(top, config.AI_MODEL, log)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = config.OUTPUT_DIR / f"niche_{stamp}.csv"
    md_path = config.OUTPUT_DIR / f"niche_{stamp}.md"
    reporter.write_csv(results, csv_path)
    md_path.write_text(reporter.build_markdown(results, config, ai_text), encoding="utf-8")

    n_good = sum(1 for r in results if r["verdict"] == "狙い目")
    log.info("─" * 50)
    log.info(f"✅ 完了。狙い目 {n_good}件 / 調査 {len(results)}件")
    log.info(f"   レポート: {md_path}")
    log.info(f"   データ  : {csv_path}")
    log.info("─" * 50)


if __name__ == "__main__":
    main()
