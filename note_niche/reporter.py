# -*- coding: utf-8 -*-
"""採点結果をCSV・Markdownレポートに出力。任意で上位ニッチにAIの攻略案を付ける。"""
import csv
import os
from datetime import datetime


def write_csv(results, path):
    fields = ["keyword", "verdict", "opportunity", "n_total", "n_paid",
              "demand_engagement", "paid_top_likes", "big_author_followers",
              "price_median", "demand_score", "competition_score", "specificity"]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(r)


ANALYSIS_SYSTEM = """\
あなたは note の販売戦略家です。データ上「狙い目」と判定されたニッチについて、
無名の個人が最初の1本で売るための具体策を簡潔に示します。
各ニッチについて: ①なぜ穴なのかの一言 ②刺さるタイトル案2つ ③推奨価格 ④記事の核になる切り口1つ。
誇大表現は使わない。簡潔に。
"""


def ai_analysis(top, model, logger=None):
    if not os.environ.get("ANTHROPIC_API_KEY") or not top:
        return ""
    try:
        import anthropic
    except ImportError:
        return ""
    lines = []
    for r in top:
        lines.append(f"- {r['keyword']}（需要スキ中央{r['demand_engagement']} / "
                     f"有料最強スキ{r['paid_top_likes']} / 有料{r['n_paid']}本 / "
                     f"想定価格¥{r['price_median']}）")
    user = ("次の『狙い目ニッチ』それぞれに、攻略案（穴の理由・タイトル2案・価格・切り口）を"
            "つけてください。\n\n" + "\n".join(lines))
    try:
        client = anthropic.Anthropic()
        with client.messages.stream(
            model=model, max_tokens=2500,
            system=[{"type": "text", "text": ANALYSIS_SYSTEM,
                     "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=[{"role": "user", "content": user}],
        ) as stream:
            msg = stream.get_final_message()
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
    except Exception as e:
        if logger:
            logger.warn(f"AI攻略案の生成に失敗: {e}")
        return ""


def build_markdown(results, cfg, ai_text=""):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    good = [r for r in results if r["verdict"] == "狙い目"]
    maybe = [r for r in results if r["verdict"] == "条件付き"]

    md = [f"# note 勝てるニッチ発掘レポート", f"\n生成: {now}　/　調査キーワード {len(results)}件\n"]
    md.append(f"**狙い目: {len(good)}件** ／ 条件付き: {len(maybe)}件\n")

    def table(rows):
        out = ["| ニッチ(キーワード) | スコア | 需要(スキ中央) | 有料最強 | 有料数 | 想定価格 | 理由 |",
               "|---|---|---|---|---|---|---|"]
        for r in rows:
            out.append(
                f"| {r['keyword']} | {r['opportunity']} | {r['demand_engagement']} | "
                f"{r['paid_top_likes']} | {r['n_paid']} | ¥{r['price_median']} | "
                f"{ '／'.join(r['reasons'][:2]) } |"
            )
        return "\n".join(out)

    md.append("## 🎯 狙い目ニッチ（需要あり × 有料競合が弱い）\n")
    md.append(table(good) if good else "_該当なし。candidates/seeds を増やすか閾値を見直してください。_")
    md.append("")
    if ai_text:
        md.append("## 攻略案（AI：狙い目ニッチの切り口・タイトル・価格）\n")
        md.append(ai_text)
        md.append("")
    md.append("## 条件付き（need vs 競合が拮抗）\n")
    md.append(table(maybe) if maybe else "_なし_")
    md.append("")
    md.append("---")
    md.append("_スコア = 需要(0〜50) − 有料競合(0〜) + 具体性ボーナス。"
              "『狙い目』を選び、note_factory で記事化 → note_publisher で投稿、の流れに繋げられます。_")
    return "\n".join(md)
