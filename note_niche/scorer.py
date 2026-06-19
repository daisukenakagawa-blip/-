# -*- coding: utf-8 -*-
"""
ニッチの「勝てる度」を、noteの実データから採点する。

考え方:
  狙い目 = 「需要はある（人々が反応している）」かつ「強い有料記事が少ない（穴がある）」
  回避   = レッドオーシャン（強い有料記事＋大型アカウント）／需要ゼロ（誰も反応しない）

スコアは全て透明な計算（魔法ではない）。閾値は config で調整可能。
"""
import math
from statistics import median


def _safe_median(xs):
    return median(xs) if xs else 0


def score_niche(keyword, items, cfg):
    """items（note検索の上位記事）から、このキーワードの勝てる度を採点。"""
    n = len(items)
    paid = [it for it in items if it["is_paid"]]
    free = [it for it in items if not it["is_paid"]]

    all_likes = [it["like_count"] for it in items]
    paid_likes = [it["like_count"] for it in paid]
    paid_prices = [it["price"] for it in paid if it["price"] > 0]

    # ① 需要シグナル: 上位記事の反応（スキ）の中央値。人々が関心を持っているか。
    demand_engagement = _safe_median(all_likes)
    # log スケールで 0〜50 点に（スキ中央値 5→約23, 20→約33, 100→約46, 300+→50）
    demand_score = min(50.0, 14.0 * math.log10(demand_engagement + 1) * 1.6) if demand_engagement else 0.0
    # 記事が極端に少ない＝そもそも検索に乗らないニッチ（需要不明）
    too_thin = n < cfg.MIN_NOTES_FOR_DEMAND

    # ② 競合シグナル: 「強い有料記事が、何本あるか」で測る。
    #    弱い有料記事が1本あるだけでは競合は軽い（穴は穴）。
    paid_strength = _safe_median(paid_likes)            # 有料記事のスキ中央値
    paid_top = max(paid_likes) if paid_likes else 0     # 最強有料記事のスキ
    big_author = max((it["followers"] for it in paid), default=0)  # 大型アカウント支配
    weak = cfg.WEAK_PAID_LIKES
    n_strong_paid = sum(1 for v in paid_likes if v >= weak)  # 「強い有料記事」の本数

    competition = 0.0
    # 最強有料の強さ: WEAK 以下なら軽微(0〜10)、超えたら対数で増加
    if paid_top <= weak:
        competition += (paid_top / weak) * 10.0
    else:
        competition += 10.0 + min(30.0, 22.0 * math.log10(paid_top / weak + 1))
    # 厚み: 強い有料記事が複数あるほどレッドオーシャン
    competition += min(15.0, n_strong_paid * 5.0)
    # 大型アカウント支配
    if big_author >= cfg.BIG_AUTHOR_FOLLOWERS:
        competition += 8.0
    competition = min(60.0, competition)

    # ③ 具体性ボーナス: 複合語ほど（＝ニッチほど）無名でも勝ちやすい
    words = [w for w in keyword.replace("　", " ").split(" ") if w]
    specificity = min(10.0, (len(words) - 1) * 4.0 + (1 if len(keyword) >= 8 else 0) * 2.0)

    opportunity = round(demand_score - competition + specificity, 1)

    # 判定と理由
    reasons = []
    if too_thin:
        verdict = "需要薄(要検証)"
        reasons.append(f"上位記事が{n}件と少なく、需要が小さい可能性")
    elif opportunity >= cfg.SCORE_GOOD:
        verdict = "狙い目"
    elif opportunity >= cfg.SCORE_MAYBE:
        verdict = "条件付き"
    else:
        verdict = "回避"

    if demand_engagement >= 20:
        reasons.append(f"需要◎（上位スキ中央値{int(demand_engagement)}）")
    elif demand_engagement >= 5:
        reasons.append(f"需要○（上位スキ中央値{int(demand_engagement)}）")
    else:
        reasons.append(f"需要△（上位スキ中央値{int(demand_engagement)}）")

    if not paid:
        reasons.append("有料記事ゼロ＝未開拓（売れるか要検証だが穴の可能性）")
    elif paid_top < cfg.WEAK_PAID_LIKES:
        reasons.append(f"有料競合が弱い（最強でもスキ{paid_top}）＝穴あり")
    else:
        reasons.append(f"有料競合が強い（最強スキ{paid_top}）＝レッドオーシャン寄り")
    if big_author >= cfg.BIG_AUTHOR_FOLLOWERS:
        reasons.append(f"大型アカウント（{big_author:,}フォロワー）が上位＝不利")

    return {
        "keyword": keyword,
        "opportunity": opportunity,
        "verdict": verdict,
        "n_total": n,
        "n_paid": len(paid),
        "demand_engagement": int(demand_engagement),
        "paid_top_likes": paid_top,
        "paid_strength": int(paid_strength),
        "big_author_followers": big_author,
        "price_median": int(_safe_median(paid_prices)),
        "demand_score": round(demand_score, 1),
        "competition_score": round(competition, 1),
        "specificity": round(specificity, 1),
        "reasons": reasons,
    }
