# -*- coding: utf-8 -*-
"""
note 編集部 ── オーケストレーター

plan.csv（または引数）の各テーマについて、編集部の4役が連携して記事を作ります:

  ① 話題スカウト   note の売れ筋を集めて戦略ブリーフを作る
  ② Webリサーチャー web_search で一次情報・具体を集める
  ③ ライター        ①②を材料に、人間らしく価値ある記事を書く
  ④ 部長            精査して合否判定。NGならライターが書き直す（最大N回）

合格した記事だけを output/ に保存します。

使い方:
  python run.py                      # plan.csv の全テーマ
  python run.py "副業 在宅 始め方"     # テーマを直接指定（価格は任意で2列目）
  python run.py "新NISA" --price 680
"""
import csv
import re
import sys
from datetime import datetime

import config
from logger import Logger
from agents.llm import LLM
from agents.trend_scout import TrendScout
from agents.web_researcher import WebResearcher
from agents.writer import Writer
from agents.editor import Editor, is_pass


def load_plan(argv):
    """引数優先。なければ plan.csv（列: theme, price, genre）"""
    args = [a for a in argv if not a.startswith("--")]
    price = ""
    if "--price" in argv:
        i = argv.index("--price")
        if i + 1 < len(argv):
            price = argv[i + 1]
    if args:
        theme = " ".join(a for a in args if a != price).strip()
        return [{"theme": theme, "price": price, "genre": theme}]
    rows = []
    if config.PLAN_FILE.exists():
        with open(config.PLAN_FILE, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                theme = (row.get("theme") or "").strip()
                if theme and not theme.startswith("#"):
                    rows.append({
                        "theme": theme,
                        "price": (row.get("price") or "").strip(),
                        "genre": (row.get("genre") or theme).strip(),
                    })
    return rows


def slugify(text):
    text = re.sub(r"\s+", "_", text.strip())
    return re.sub(r'[\\/:*?"<>|]', "", text)[:40] or "article"


def make_one(theme, genre, price, agents, log):
    scout, researcher, writer, editor = agents

    # ① スカウト
    scouted = scout.scout(genre)
    # ② リサーチ
    research = researcher.research(theme, angle_hint=scouted["brief"][:500])
    # ③④ 執筆 → 精査 → 書き直しループ
    feedback, draft, verdict = None, None, None
    for rnd in range(1, config.MAX_REVISION_ROUNDS + 1):
        log.info(f"  --- ラウンド {rnd}/{config.MAX_REVISION_ROUNDS} ---")
        draft = writer.write(theme, scouted["brief"], research, price, feedback)
        verdict = editor.review(theme, draft)
        log.info(f"  [部長] 総合 {verdict.get('overall')}/10  判定: {verdict.get('verdict')}"
                 f"  一言: {verdict.get('one_line', '')}")
        if is_pass(verdict):
            log.info("  ✅ 合格")
            return {"ok": True, "draft": draft, "verdict": verdict,
                    "rounds": rnd, "brief": scouted["brief"], "research": research}
        feedback = editor.feedback_text(verdict)

    log.warn("  ⚠ 規定回数で合格に至らず。最終稿を『要確認』として保存します。")
    return {"ok": False, "draft": draft, "verdict": verdict,
            "rounds": config.MAX_REVISION_ROUNDS, "brief": scouted["brief"], "research": research}


def save(theme, price, result, log):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = slugify(theme)
    status = "" if result["ok"] else "_要確認"
    v = result["verdict"] or {}
    header = (
        f"<!-- テーマ: {theme} / 推奨価格: {price or '提案'} / "
        f"部長評価: {v.get('overall')}/10 / 書き直し{result['rounds']}回 / "
        f"{'合格' if result['ok'] else '未達'} -->\n\n"
    )
    path = config.OUTPUT_DIR / f"{slug}_{stamp}{status}.md"
    path.write_text(header + (result["draft"] or ""), encoding="utf-8")
    log.info(f"  📝 保存: {path.name}")

    if config.SAVE_BRIEFS:
        bpath = config.BRIEFS_DIR / f"{slug}_{stamp}_brief.md"
        bpath.write_text(
            f"# 戦略ブリーフ\n{result['brief']}\n\n"
            f"# リサーチ\n{result['research']}\n\n"
            f"# 部長の講評\n{v.get('one_line','')}\n"
            f"必須修正: {v.get('must_fix')}\nAI臭: {v.get('ai_smell')}\n",
            encoding="utf-8",
        )
    return path


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(config.BASE_DIR / ".env")
    except ImportError:
        pass
    log = Logger(config.LOG_DIR)
    for d in (config.OUTPUT_DIR, config.BRIEFS_DIR):
        d.mkdir(parents=True, exist_ok=True)

    plan = load_plan(sys.argv[1:])
    if not plan:
        log.error("テーマがありません。plan.csv に書くか、引数で指定してください。")
        sys.exit(1)

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY が未設定です。.env に設定してください（README参照）。")
        sys.exit(1)

    # 各役のLLM（モデルは config で切替可能）
    agents = (
        TrendScout(LLM(config.MODEL_SCOUT, log), log, config.NOTE_SCOUT_ITEMS),
        WebResearcher(LLM(config.MODEL_RESEARCH, log), log),
        Writer(LLM(config.MODEL_WRITER, log), log),
        Editor(LLM(config.MODEL_EDITOR, log), log),
    )

    log.info("=" * 55)
    log.info(f"note編集部 稼働: {len(plan)}テーマ")
    log.info("=" * 55)
    passed = 0
    for i, item in enumerate(plan, 1):
        log.info(f"\n[{i}/{len(plan)}] テーマ: {item['theme']}")
        try:
            result = make_one(item["theme"], item["genre"], item["price"], agents, log)
            save(item["theme"], item["price"], result, log)
            if result["ok"]:
                passed += 1
        except Exception as e:
            log.error(f"  生成中にエラー: {e}")

    log.info("\n" + "=" * 55)
    log.info(f"完了: 合格 {passed} / {len(plan)} 本（output/ を確認してください）")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
