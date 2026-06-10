"""
分析・狙い台ランキング層
====================================================================
過去データから各種傾向を算出し、翌日の狙い台候補をランキングする。

- 曜日別傾向 / 末尾別傾向 / 台番号別傾向
- 前日凹み台分析 / 高REG台ランキング
- 過去30日平均 / 過去90日平均
- 翌日狙い台ランキング（1〜20位）+ おすすめ理由（日本語）

【方針】
完璧な予想AIではなく「傾向の見える化」を目的とする。
スコアは複数の傾向を素直に加点した、説明可能なモデルにしている。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

import config
from database import WEEKDAY_JP


# ------------------------------------------------------------------
# 補助
# ------------------------------------------------------------------
def _recent(df: pd.DataFrame, days: int, ref_date: str | None = None) -> pd.DataFrame:
    if df.empty:
        return df
    ref = datetime.strptime(ref_date, "%Y-%m-%d") if ref_date else \
        datetime.strptime(df["date"].max(), "%Y-%m-%d")
    start = (ref - timedelta(days=days)).strftime("%Y-%m-%d")
    return df[df["date"] > start]


def _mean_div(series: pd.Series) -> float | None:
    """確率分母の平均。値が小さいほど良い。NaN除外。"""
    s = series.dropna()
    return round(float(s.mean()), 1) if len(s) else None


# ------------------------------------------------------------------
# 0. 店舗別傾向（多店舗比較：どの店が設定を入れているか）
# ------------------------------------------------------------------
def store_trend(df: pd.DataFrame, days: int = 30) -> pd.DataFrame:
    """期間内の店舗別 平均合算・平均REG。分母が小さい店ほど優秀（出している）。"""
    sub = _recent(df, days)
    if sub.empty or "store" not in sub.columns:
        return pd.DataFrame()
    g = sub.groupby("store").agg(
        サンプル数=("combined_prob", "count"),
        平均合算=("combined_prob", "mean"),
        平均REG=("reg_prob", "mean"),
        平均総回転=("total_games", "mean"),
    ).reset_index()
    for c in ["平均合算", "平均REG", "平均総回転"]:
        g[c] = g[c].round(1)
    return g.rename(columns={"store": "店舗"}).sort_values("平均合算")


# ------------------------------------------------------------------
# 1. 曜日別傾向
# ------------------------------------------------------------------
def weekday_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("weekday").agg(
        サンプル数=("combined_prob", "count"),
        平均合算=("combined_prob", "mean"),
        平均REG=("reg_prob", "mean"),
        平均総回転=("total_games", "mean"),
    ).reset_index()
    g["weekday"] = pd.Categorical(g["weekday"], categories=WEEKDAY_JP, ordered=True)
    g = g.sort_values("weekday")
    for c in ["平均合算", "平均REG", "平均総回転"]:
        g[c] = g[c].round(1)
    return g.rename(columns={"weekday": "曜日"})


# ------------------------------------------------------------------
# 2. 末尾別傾向
# ------------------------------------------------------------------
def tail_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("tail").agg(
        サンプル数=("combined_prob", "count"),
        平均合算=("combined_prob", "mean"),
        平均REG=("reg_prob", "mean"),
    ).reset_index()
    for c in ["平均合算", "平均REG"]:
        g[c] = g[c].round(1)
    return g.rename(columns={"tail": "末尾"}).sort_values("末尾")


# ------------------------------------------------------------------
# 3. 台番号別傾向
# ------------------------------------------------------------------
def machine_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("machine_no").agg(
        出現日数=("combined_prob", "count"),
        平均合算=("combined_prob", "mean"),
        平均REG=("reg_prob", "mean"),
        平均総回転=("total_games", "mean"),
    ).reset_index()
    for c in ["平均合算", "平均REG", "平均総回転"]:
        g[c] = g[c].round(1)
    return g.rename(columns={"machine_no": "台番号"}).sort_values("台番号")


# ------------------------------------------------------------------
# 4. 前日凹み台分析
# ------------------------------------------------------------------
def previous_day_slump(df: pd.DataFrame, ref_date: str | None = None) -> pd.DataFrame:
    """
    直近日（または ref_date）に合算が悪かった（分母が大きい）台を抽出。
    「据え置き／前日凹みの翌日狙い」の判断材料。
    """
    if df.empty:
        return pd.DataFrame()
    target = ref_date or df["date"].max()
    day = df[df["date"] == target].copy()
    if day.empty:
        return pd.DataFrame()
    median = day["combined_prob"].median()
    day["凹み判定"] = day["combined_prob"] > median
    day = day.sort_values("combined_prob", ascending=False)
    cols = ["machine_no", "tail", "total_games", "big", "reg",
            "combined_prob", "reg_prob", "凹み判定"]
    out = day[cols].rename(columns={
        "machine_no": "台番号", "tail": "末尾", "total_games": "総回転数",
        "big": "BIG", "reg": "REG", "combined_prob": "合算", "reg_prob": "REG確率",
    })
    return out


# ------------------------------------------------------------------
# 5. 高REG台ランキング
# ------------------------------------------------------------------
def high_reg_ranking(df: pd.DataFrame, days: int = 30, top_n: int = 20) -> pd.DataFrame:
    """期間内のREG確率（分母）が良い＝小さい順。マイジャグラーはREGが設定の鍵。"""
    sub = _recent(df, days)
    if sub.empty:
        return pd.DataFrame()
    g = sub.groupby("machine_no").agg(
        出現日数=("reg_prob", "count"),
        平均REG=("reg_prob", "mean"),
        平均合算=("combined_prob", "mean"),
    ).reset_index()
    g = g[g["出現日数"] >= 2]  # サンプルが極端に少ない台は除外
    g["平均REG"] = g["平均REG"].round(1)
    g["平均合算"] = g["平均合算"].round(1)
    g = g.sort_values("平均REG").head(top_n).reset_index(drop=True)
    g.index = g.index + 1
    return g.rename(columns={"machine_no": "台番号"})


# ------------------------------------------------------------------
# 6. 過去N日平均
# ------------------------------------------------------------------
def period_average(df: pd.DataFrame, days: int) -> pd.DataFrame:
    sub = _recent(df, days)
    if sub.empty:
        return pd.DataFrame()
    g = sub.groupby("machine_no").agg(
        出現日数=("combined_prob", "count"),
        平均合算=("combined_prob", "mean"),
        平均REG=("reg_prob", "mean"),
        平均BIG=("big_prob", "mean"),
    ).reset_index()
    for c in ["平均合算", "平均REG", "平均BIG"]:
        g[c] = g[c].round(1)
    return g.rename(columns={"machine_no": "台番号"}).sort_values("台番号")


# ------------------------------------------------------------------
# 7. 翌日狙い台ランキング
# ------------------------------------------------------------------
def _score_components(df: pd.DataFrame, ref_date: str):
    """ランキング用の各種スコア材料を事前計算して辞書で返す。"""
    recent30 = _recent(df, config.RECENT_30, ref_date)

    # 台番号別 平均REG/合算（小さいほど良い→スコアは反転して加点）
    m30 = recent30.groupby("machine_no").agg(
        avg_reg=("reg_prob", "mean"),
        avg_comb=("combined_prob", "mean"),
        days=("combined_prob", "count"),
    )

    # 末尾別 平均合算
    tail_avg = recent30.groupby("tail")["combined_prob"].mean()

    # 翌日の曜日傾向（ref_date の翌日の曜日）
    next_day = datetime.strptime(ref_date, "%Y-%m-%d") + timedelta(days=1)
    next_wd = WEEKDAY_JP[next_day.weekday()]
    wd_avg = recent30.groupby("weekday")["combined_prob"].mean()

    # 前日データ（凹み判定用）
    last_day = df[df["date"] == ref_date].set_index("machine_no")

    return {
        "m30": m30, "tail_avg": tail_avg, "wd_avg": wd_avg,
        "next_wd": next_wd, "last_day": last_day,
        "global_comb": recent30["combined_prob"].mean(),
        "global_reg": recent30["reg_prob"].mean(),
    }


def aim_ranking(df: pd.DataFrame, ref_date: str | None = None,
                top_n: int | None = None) -> pd.DataFrame:
    """
    翌日の狙い台ランキング（1位〜top_n位）を、おすすめ理由つきで返す。

    スコア = 過去REG良さ + 過去合算良さ + 末尾傾向 + 翌日曜日傾向
             + 前日凹み（据え置き期待）  ※すべて説明可能な加点方式
    """
    top_n = top_n or config.RANKING_TOP_N
    if df.empty:
        return pd.DataFrame()

    ref_date = ref_date or df["date"].max()
    c = _score_components(df, ref_date)
    m30 = c["m30"]
    if m30.empty:
        return pd.DataFrame()

    rows = []
    g_comb = c["global_comb"]
    g_reg = c["global_reg"]

    for machine_no, r in m30.iterrows():
        if r["days"] < 2:
            continue
        score = 0.0
        reasons: list[str] = []

        # (1) 過去REG（マイジャグラーの肝）。平均より良ければ加点。
        if pd.notna(r["avg_reg"]) and pd.notna(g_reg):
            diff = g_reg - r["avg_reg"]  # 正なら平均より分母が小さい＝良い
            pts = max(0.0, diff) * 0.15
            score += pts
            if r["avg_reg"] <= g_reg - 10:
                reasons.append(f"過去30日のREG平均が1/{r['avg_reg']:.0f}と全体平均より優秀")

        # (2) 過去合算。
        if pd.notna(r["avg_comb"]) and pd.notna(g_comb):
            diff = g_comb - r["avg_comb"]
            score += max(0.0, diff) * 0.10
            if r["avg_comb"] <= g_comb - 5:
                reasons.append(f"過去30日の合算平均が1/{r['avg_comb']:.0f}と好調")

        # (3) 末尾傾向
        tail = int(machine_no) % 10
        if tail in c["tail_avg"].index and pd.notna(c["tail_avg"][tail]):
            t_diff = g_comb - c["tail_avg"][tail]
            score += max(0.0, t_diff) * 0.06
            if c["tail_avg"][tail] <= g_comb - 4:
                reasons.append(f"末尾{tail}は過去30日で平均より出ている傾向")

        # (4) 翌日の曜日傾向
        nwd = c["next_wd"]
        if nwd in c["wd_avg"].index and pd.notna(c["wd_avg"][nwd]):
            w_diff = g_comb - c["wd_avg"][nwd]
            score += max(0.0, w_diff) * 0.05
            if c["wd_avg"][nwd] <= g_comb - 3:
                reasons.append(f"翌日（{nwd}曜）は過去傾向で好調")

        # (5) 前日凹み（据え置き／回収後の投入期待）
        if machine_no in c["last_day"].index:
            ld = c["last_day"].loc[machine_no]
            if pd.notna(ld["combined_prob"]) and pd.notna(g_comb) and \
               ld["combined_prob"] > g_comb + 8:
                score += 4.0
                reasons.append(
                    f"前日は合算1/{ld['combined_prob']:.0f}と凹み（据え置き・狙い目の可能性）"
                )

        if not reasons:
            reasons.append("過去データは平均的。様子見推奨")

        rows.append({
            "台番号": int(machine_no),
            "末尾": tail,
            "スコア": round(score, 1),
            "過去30日平均合算": round(r["avg_comb"], 1) if pd.notna(r["avg_comb"]) else None,
            "過去30日平均REG": round(r["avg_reg"], 1) if pd.notna(r["avg_reg"]) else None,
            "出現日数": int(r["days"]),
            "おすすめ理由": " / ".join(reasons),
        })

    if not rows:
        return pd.DataFrame()

    out = pd.DataFrame(rows).sort_values(
        "スコア", ascending=False).head(top_n).reset_index(drop=True)
    out.insert(0, "順位", range(1, len(out) + 1))
    return out
