# -*- coding: utf-8 -*-
"""
分析結果を CSV と Markdown レポートに書き出す。
任意で Anthropic API による「売れる理由・狙い目」の考察も付ける。
"""
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List

from .note_client import NoteItem


def write_csv(items: List[NoteItem], path: Path):
    """収集した全記事を CSV 保存(次の記事生成ツールの入力にも使えます)。"""
    fields = [
        "keyword", "title", "is_paid", "price", "like_count", "comment_count",
        "author_name", "author_followers", "published_at", "url",
    ]
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for it in items:
            writer.writerow(it.as_dict())


def _table(items: List[NoteItem], limit: int) -> str:
    lines = [
        "| # | スキ | 価格 | タイトル | 著者(フォロワー) |",
        "|---|------|------|----------|------------------|",
    ]
    for i, it in enumerate(items[:limit], 1):
        price = f"¥{it.price}" if it.is_paid else "無料"
        title = it.title.replace("|", "｜")
        link = f"[{title}]({it.url})" if it.url else title
        author = f"{it.author_name}({it.author_followers:,})"
        lines.append(f"| {i} | {it.like_count:,} | {price} | {link} | {author} |")
    return "\n".join(lines)


def build_markdown(result: dict, ai_insight: str = "") -> str:
    ps = result["price_stats"]
    tp = result["title_patterns"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    md = []
    md.append(f"# note 売れる記事リサーチレポート")
    md.append(f"\n生成日時: {now}\n")

    md.append("## サマリー\n")
    md.append(f"- 収集記事数: **{result['total_collected']}件**(分析対象 {result['analyzed']}件)")
    md.append(f"- うち有料記事: **{result['paid_count']}件** / 無料記事: {result['free_count']}件")
    if ps["count"]:
        md.append(
            f"- 有料記事の価格帯: 最安 ¥{ps['min']:,} / "
            f"**中央値 ¥{ps['median']:,}** / 最高 ¥{ps['max']:,}"
        )
    md.append(
        f"- タイトル傾向: 平均 {tp['avg_len']}文字 / "
        f"数字入り {int(tp['num_ratio']*100)}% / 【】等の装飾 {int(tp['bracket_ratio']*100)}%"
    )
    md.append("")

    if ai_insight:
        md.append("## AI による考察(売れる理由・狙い目)\n")
        md.append(ai_insight)
        md.append("")

    md.append("## 売れている有料記事 ランキング(スキ数順)\n")
    if result["paid_ranked"]:
        md.append(_table(result["paid_ranked"], len(result["paid_ranked"])))
    else:
        md.append("_条件に合う有料記事が見つかりませんでした。keywords.csv や MIN_LIKE_COUNT を見直してください。_")
    md.append("")

    md.append("## 人気記事ランキング(無料含む・タイトル参考用)\n")
    md.append(_table(result["all_ranked"], len(result["all_ranked"])))
    md.append("")

    md.append("## 価格帯の分布\n")
    if ps["buckets"]:
        md.append("| 価格帯 | 件数 |")
        md.append("|--------|------|")
        for k, v in ps["buckets"].items():
            md.append(f"| {k} | {v} |")
    else:
        md.append("_有料記事のデータがありません。_")
    md.append("")

    md.append("## タイトルに頻出するキーワード(売れるワード候補)\n")
    if result["top_words"]:
        md.append("| キーワード | 出現回数 |")
        md.append("|------------|----------|")
        for w, c in result["top_words"]:
            md.append(f"| {w} | {c} |")
    else:
        md.append("_データがありません。_")
    md.append("")

    md.append("---")
    md.append("_このレポートは note の公開検索結果をもとに自動生成しています。次のステップ"
              "(記事の自動生成)では、上記の売れ筋ワード・価格帯・タイトルの型を入力に使えます。_")
    return "\n".join(md)


def generate_ai_insight(result: dict, model: str, logger) -> str:
    """Anthropic API があれば、売れる理由の考察を生成。なければ空文字。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY 未設定のため AI 考察はスキップします。")
        return ""
    try:
        import anthropic
    except ImportError:
        logger.warn("anthropic 未インストールのため AI 考察はスキップします。")
        return ""

    # 上位記事のタイトル一覧を渡す
    top_titles = [
        f"- {it.title}(スキ{it.like_count} / ¥{it.price if it.is_paid else 0})"
        for it in (result["paid_ranked"] or result["all_ranked"])[:20]
    ]
    top_words = ", ".join(w for w, _ in result["top_words"][:15])
    ps = result["price_stats"]
    prompt = (
        "あなたは note の販売・コンテンツマーケティングの専門家です。\n"
        "以下は note で実際に売れている/人気の記事データです。\n\n"
        f"【売れている記事タイトル(上位)】\n" + "\n".join(top_titles) + "\n\n"
        f"【頻出キーワード】{top_words}\n"
        f"【有料価格帯】中央値 ¥{ps['median']} / 範囲 ¥{ps['min']}〜¥{ps['max']}\n\n"
        "これらを踏まえ、次の3点を日本語で簡潔にまとめてください。\n"
        "1. 売れている記事に共通する『型』や訴求の特徴(箇条書き)\n"
        "2. これから書くなら狙い目のテーマ・タイトル例(3〜5個)\n"
        "3. 推奨価格設定とその理由\n"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        logger.warn(f"AI 考察の生成に失敗しました: {e}")
        return ""
