# -*- coding: utf-8 -*-
"""
note 売れる記事ジェネレーター(自動量産エンジン)

article_plan.csv に書いたテーマごとに、note で売れる構成
(強いタイトル → 共感リード → 無料で価値提示 → 有料ライン → 具体ノウハウ → CTA)
の記事を生成し、output/ に Markdown で保存します。

- ANTHROPIC_API_KEY があれば AI が本文を執筆
- 無ければ、構成だけ埋まった「雛形(あなたが書き足す用)」を出力
- リサーチCSV(note_research/output)があれば、頻出ワードや価格中央値を反映

使い方:
    python generator.py                  # article_plan.csv の全テーマを生成
    python generator.py "副業 在宅"        # テーマを直接指定して1本生成
"""
import csv
import os
import re
import sys
import glob
from datetime import datetime

import config

# ── note で売れる記事の「型」(AI への指示にも雛形にも使う) ──
SELLABLE_STRUCTURE = """\
# (ベネフィットが伝わる強いタイトル。数字や【】を使う)

(共感リード:読者の悩みを2〜3行で代弁し、このnoteで解決できると約束する)

## このnoteで分かること
- (得られること1)
- (得られること2)
- (得られること3)
- (得られること4)

## (無料パート:全体の約3割。結論やさわりを見せて信頼を作る)

{paywall}

## 1. (具体ノウハウ・手順)
## 2. (テンプレート/チェックリスト)
## 3. (応用・つまずき対策)

## まとめ
(行動を1つ促すCTAで締める)
"""

SYSTEM_PROMPT = """\
あなたは note で売れる有料記事を量産するプロの編集者兼ライターです。
次の条件を厳守して、日本語の記事を Markdown で執筆してください。

【売れる構成】
1. タイトル: ベネフィットが一目で伝わる。数字や【】を効果的に使う
2. 共感リード: 読者の悩みを代弁し、このnoteで解決できると約束
3. 「このnoteで分かること」を箇条書き
4. 無料パート: 結論やさわりを見せ、価値と信頼を作る(全体の約3割)
5. 有料ライン: 行に「{paywall}」だけを置く
6. 有料パート: 具体的な手順・テンプレート・チェックリスト・表を豊富に
7. まとめ: 行動を1つ促すCTA

【絶対ルール】
- 体験談や個人の実績(月◯万円稼いだ等)をでっち上げない。
  ノウハウ・手順・テンプレートの価値で売ること。
- 投資/健康/お金の話では、利益や効果を保証する断定表現を避け、
  必要に応じて「情報提供であり自己責任/専門家に相談を」と注記する。
- 誇大表現(必ず・絶対・誰でも簡単に)は使わない。
- すぐ使えるテンプレやチェックリストを必ず1つ以上入れる。
"""


def latest_research_csv():
    """note_research の最新出力CSVのパスを返す(無ければ None)。"""
    if not config.RESEARCH_OUTPUT_DIR.exists():
        return None
    files = sorted(glob.glob(str(config.RESEARCH_OUTPUT_DIR / "*.csv")))
    return files[-1] if files else None


def research_hints():
    """リサーチCSVから、価格中央値と頻出ワードのヒントを作る。"""
    path = latest_research_csv()
    hints = {"price": config.DEFAULT_PRICE, "words": []}
    if not path or not os.path.exists(path):
        return hints
    try:
        prices, titles = [], []
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("is_paid", "").lower() in ("true", "1"):
                    try:
                        p = int(float(row.get("price") or 0))
                        if p > 0:
                            prices.append(p)
                    except ValueError:
                        pass
                titles.append(row.get("title", ""))
        if prices:
            prices.sort()
            hints["price"] = prices[len(prices) // 2]  # 中央値
    except Exception:
        pass
    return hints


def load_plan(args):
    """コマンドライン引数優先、なければ article_plan.csv を読む。
    返り値: [{theme, price, tags}] のリスト"""
    if args:
        return [{"theme": " ".join(args).strip(), "price": "", "tags": ""}]
    rows = []
    if config.PLAN_FILE.exists():
        with open(config.PLAN_FILE, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                theme = (row.get("theme") or "").strip()
                if theme and not theme.startswith("#"):
                    rows.append({
                        "theme": theme,
                        "price": (row.get("price") or "").strip(),
                        "tags": (row.get("tags") or "").strip(),
                    })
    return rows


def slugify(text):
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"[\\/:*?\"<>|]", "", text)
    return text[:40] or "article"


def generate_with_ai(theme, price, tags, hints):
    """Anthropic API で本文を生成。失敗/未設定なら None。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    word_hint = ""
    if hints["words"]:
        word_hint = "参考にしたい頻出ワード: " + ", ".join(hints["words"][:10]) + "\n"
    user_prompt = (
        f"テーマ: {theme}\n"
        f"想定読者にとって有料(¥{price})の価値があるノウハウ記事にしてください。\n"
        f"{word_hint}"
        f"タグ候補: {tags or '(自由に5個提案)'}\n\n"
        "Markdownで、タイトルから本文・まとめまで完成形を書いてください。"
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=config.AI_MODEL,
            max_tokens=config.MAX_TOKENS,
            system=SYSTEM_PROMPT.format(paywall=config.PAYWALL_MARK),
            messages=[{"role": "user", "content": user_prompt}],
        )
        return resp.content[0].text.strip()
    except Exception as e:
        print(f"  [AI生成失敗] {e} -> 雛形を出力します")
        return None


def generate_template(theme, price, tags):
    """AIなしの雛形(あなたが書き足す用)。"""
    body = SELLABLE_STRUCTURE.format(
        paywall="―" * 20 + f"\n**{config.PAYWALL_MARK}**\n" + "―" * 20
    )
    return body.replace(
        "# (ベネフィットが伝わる強いタイトル。数字や【】を使う)",
        f"# 【テーマ:{theme}】(ここに強いタイトルを書く)",
    )


def build_front_matter(theme, price, tags):
    return (
        "---\n"
        f"テーマ: {theme}\n"
        f"推奨価格: ¥{price}\n"
        f"タグ: {tags or '(5個ほど設定)'}\n"
        f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        "---\n\n"
    )


def main():
    try:
        from dotenv import load_dotenv
        load_dotenv(config.BASE_DIR / ".env")
    except ImportError:
        pass

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plan = load_plan(sys.argv[1:])
    if not plan:
        print("生成するテーマがありません。article_plan.csv にテーマを書いてください。")
        sys.exit(1)

    hints = research_hints()
    print(f"リサーチヒント: 推奨価格 ¥{hints['price']}  (note_research の最新CSVを参照)")
    use_ai = config.USE_AI and os.environ.get("ANTHROPIC_API_KEY")
    print(f"生成モード: {'AI執筆' if use_ai else '雛形(APIキー未設定)'}\n")

    created = []
    for i, item in enumerate(plan, 1):
        theme = item["theme"]
        price = item["price"] or str(hints["price"])
        tags = item["tags"]
        print(f"[{i}/{len(plan)}] 生成中: {theme}  (¥{price})")

        body = generate_with_ai(theme, price, tags, hints) if use_ai else None
        if not body:
            body = generate_template(theme, price, tags)

        content = build_front_matter(theme, price, tags) + body
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = config.OUTPUT_DIR / f"{i:02d}_{slugify(theme)}_{stamp}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"      -> {path.name}")
        created.append({"theme": theme, "price": price})

    mode_label = "AI執筆" if use_ai else "雛形"
    print(f"\n✅ 完了。output フォルダに {len(created)} 本を出力しました。")
    print("   AIキー未設定の場合は雛形です。articles/ の完成サンプルを参考に書き足してください。")

    # LINE 通知(任意。LINE_CHANNEL_ACCESS_TOKEN を設定した時のみ送信)
    if config.NOTIFY_LINE and created:
        send_line_notification(created, mode_label)


def send_line_notification(created, mode_label):
    """記事生成の完了を LINE に通知する。"""
    try:
        import line_notifier
    except ImportError:
        return
    if not line_notifier.is_configured():
        print("   (LINE通知はトークン未設定のためスキップ)")
        return
    lines = [f"✅ note記事を{len(created)}本作成しました（{mode_label}）"]
    for i, c in enumerate(created[:15], 1):
        lines.append(f"{i}. {c['theme']}（¥{c['price']}）")
    lines.append("\n▶ note_writer/output を確認し、投稿してください。")
    ok, msg = line_notifier.notify("\n".join(lines))
    print(f"   LINE通知: {'送信しました' if ok else msg}")


if __name__ == "__main__":
    main()
