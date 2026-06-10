"""
Streamlit Web画面
====================================================================
ジャグラー専用 データ自動収集・分析ツール

起動方法:
    cd jagler
    pip install -r requirements.txt
    streamlit run app.py

画面構成:
    ・データ取得ボタン
    ・データ一覧（色分け）
    ・店舗傾向分析（台番号別）
    ・末尾分析
    ・曜日分析
    ・狙い台ランキング
    ・CSVダウンロード
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import config
import database as db
import scraper
import analysis
import exporter
import sample_data

st.set_page_config(page_title="ジャグラー データ分析ツール", layout="wide")

# 表示用カラム名（日本語）
DISPLAY_COLS = {
    "date": "日付", "weekday": "曜日", "machine_no": "台番号",
    "big": "BIG回数", "reg": "REG回数", "total_games": "総回転数",
    "big_prob": "BIG確率", "reg_prob": "REG確率", "combined_prob": "合算確率",
    "bb_reg_total": "BB_REG合計", "reg_ratio": "REG比率", "tail": "末尾",
}


def jp_view(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in DISPLAY_COLS if c in df.columns]
    return df[keep].rename(columns=DISPLAY_COLS)


# ==================================================================
# サイドバー：データ取得
# ==================================================================
st.sidebar.title("⚙️ データ取得")
st.sidebar.caption(f"店舗: {config.STORE_NAME}")
st.sidebar.caption(f"機種: {config.MACHINE_NAME}")

mode = "🟢 実サイト接続" if config.SCRAPER_ENABLED else "🟡 デモデータ"
st.sidebar.info(f"取得モード: {mode}")

remaining = scraper.seconds_until_allowed()
if remaining > 0:
    st.sidebar.warning(f"次回取得まで 約{remaining/3600:.1f} 時間（1日1回制限）")
else:
    st.sidebar.success("取得可能です")

fetch_date = st.sidebar.date_input("取得対象日", value=date.today())

if st.sidebar.button("📥 データ取得", use_container_width=True, type="primary"):
    try:
        records = scraper.fetch(fetch_date)
        ins, skip = db.save_records(records, fetch_date.isoformat())
        st.sidebar.success(f"取得完了: 新規{ins}件 / 重複スキップ{skip}件")
    except scraper.FetchBlocked as e:
        st.sidebar.error(str(e))
    except Exception as e:  # noqa: BLE001
        st.sidebar.error(f"取得に失敗しました: {e}")

st.sidebar.divider()
st.sidebar.subheader("デモ用")
demo_days = st.sidebar.slider("生成日数", 7, 120, 90)
if st.sidebar.button("🧪 デモ履歴をまとめて生成", use_container_width=True):
    hist = sample_data.generate_history(days=demo_days)
    total_ins = total_skip = 0
    for d, recs in hist.items():
        i, s = db.save_records(recs, d)
        total_ins += i
        total_skip += s
    st.sidebar.success(f"デモ生成: 新規{total_ins}件 / 重複{total_skip}件")

if config.GSHEET_ENABLED:
    if st.sidebar.button("📊 スプレッドシート出力", use_container_width=True):
        try:
            url = exporter.export_to_gsheet(db.load_all())
            st.sidebar.success(f"出力しました: {url}")
        except Exception as e:  # noqa: BLE001
            st.sidebar.error(f"出力失敗: {e}")


# ==================================================================
# メイン
# ==================================================================
st.title("🎰 ジャグラー データ分析ツール")
st.caption(f"{config.STORE_NAME} / {config.MACHINE_NAME} ｜ "
           "データを正確に蓄積し、傾向を見える化します")

df = db.load_all()
if df.empty:
    st.warning("まだデータがありません。左の「データ取得」または"
               "「デモ履歴をまとめて生成」を押してください。")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("総レコード数", f"{len(df):,}")
c2.metric("収集日数", f"{df['date'].nunique()} 日")
c3.metric("最新データ", df["date"].max())

tabs = st.tabs([
    "📋 データ一覧", "🏪 店舗傾向分析", "🔢 末尾分析",
    "📅 曜日分析", "🎯 狙い台ランキング", "💾 CSVダウンロード",
])

# --- データ一覧 ---
with tabs[0]:
    st.subheader("データ一覧（合算・REG確率を色分け）")
    st.caption("合算: 黄(1/140-130)→橙(1/129-110)→赤(1/109-80) ｜ "
               "REG: 値が小さいほど高設定示唆")
    dates = db.available_dates()
    sel = st.selectbox("日付で絞り込み", ["（全期間）"] + dates)
    view = df if sel == "（全期間）" else db.load_by_date(sel)
    view = view.sort_values(["date", "machine_no"], ascending=[False, True])
    st.dataframe(
        exporter.style_dataframe(jp_view(view).rename(
            columns={"合算確率": "combined_prob", "REG確率": "reg_prob"})),
        use_container_width=True, height=520,
    )

# --- 店舗傾向分析（台番号別） ---
with tabs[1]:
    st.subheader("台番号別 傾向")
    mt = analysis.machine_trend(df)
    st.dataframe(mt, use_container_width=True)
    if not mt.empty:
        st.bar_chart(mt.set_index("台番号")["平均合算"])
        st.caption("※ 棒が低い台ほど平均合算が良い（分母が小さい）")

    st.divider()
    st.subheader("前日凹み台分析")
    slump = analysis.previous_day_slump(df)
    st.caption("直近営業日に合算が悪かった台。翌日の据え置き・狙い目の判断材料に。")
    st.dataframe(slump, use_container_width=True)

    st.divider()
    st.subheader("高REG台ランキング（過去30日）")
    st.dataframe(analysis.high_reg_ranking(df, days=30), use_container_width=True)

    cc1, cc2 = st.columns(2)
    with cc1:
        st.subheader("過去30日平均")
        st.dataframe(analysis.period_average(df, config.RECENT_30),
                     use_container_width=True)
    with cc2:
        st.subheader("過去90日平均")
        st.dataframe(analysis.period_average(df, config.RECENT_90),
                     use_container_width=True)

# --- 末尾分析 ---
with tabs[2]:
    st.subheader("末尾別 傾向")
    tt = analysis.tail_trend(df)
    st.dataframe(tt, use_container_width=True)
    if not tt.empty:
        st.bar_chart(tt.set_index("末尾")["平均合算"])
        st.caption("※ 棒が低い末尾ほど平均合算が良い傾向")

# --- 曜日分析 ---
with tabs[3]:
    st.subheader("曜日別 傾向")
    wt = analysis.weekday_trend(df)
    st.dataframe(wt, use_container_width=True)
    if not wt.empty:
        st.bar_chart(wt.set_index("曜日")["平均合算"])
        st.caption("※ 棒が低い曜日ほど平均合算が良い傾向")

# --- 狙い台ランキング ---
with tabs[4]:
    st.subheader(f"翌日の狙い台ランキング（1〜{config.RANKING_TOP_N}位）")
    st.caption("過去REG・合算・末尾・曜日・前日凹みを加点したスコア順。"
               "完璧な予想ではなく傾向の見える化です。")
    ranking = analysis.aim_ranking(df)
    if ranking.empty:
        st.info("ランキング算出にはもう少しデータが必要です（複数日分）。")
    else:
        st.dataframe(ranking, use_container_width=True, height=560)
        st.markdown("#### 上位台のおすすめ理由")
        for _, row in ranking.head(5).iterrows():
            st.markdown(
                f"**{row['順位']}位　{row['台番号']}番（末尾{row['末尾']}）"
                f"　スコア{row['スコア']}**  \n{row['おすすめ理由']}")

# --- CSVダウンロード ---
with tabs[5]:
    st.subheader("CSVダウンロード")
    st.download_button(
        "📥 全データCSV（Excel対応・BOM付き）",
        data=exporter.to_csv_bytes(jp_view(df)),
        file_name="jagler_all.csv", mime="text/csv",
    )
    rk = analysis.aim_ranking(df)
    if not rk.empty:
        st.download_button(
            "📥 狙い台ランキングCSV",
            data=exporter.to_csv_bytes(rk),
            file_name="jagler_ranking.csv", mime="text/csv",
        )
