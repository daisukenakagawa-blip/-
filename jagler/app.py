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

import time
from datetime import date

import pandas as pd
import streamlit as st

import config
import storage as db
import scraper
import analysis
import exporter
import sample_data

st.set_page_config(page_title="ジャグラー データ分析ツール", layout="wide")

# --- 保存先の認証情報を Streamlit secrets から注入（クラウド永続化用） ---
# .streamlit/secrets.toml もしくは Streamlit Cloud の Secrets に
# [gcp_service_account] と（任意で）[gsheet] を設定すると蓄積先がSheetsになる。
try:
    if "gcp_service_account" in st.secrets:
        db.set_gsheet_credentials(dict(st.secrets["gcp_service_account"]))
        if "gsheet" in st.secrets:
            db.set_gsheet_config(dict(st.secrets["gsheet"]))
except Exception:  # noqa: BLE001  secrets未設定でもSQLiteで動く
    pass

# 表示用カラム名（日本語）
DISPLAY_COLS = {
    "date": "日付", "weekday": "曜日", "store": "店舗", "machine_name": "機種",
    "machine_no": "台番号", "big": "BIG回数", "reg": "REG回数",
    "total_games": "総回転数", "big_prob": "BIG確率", "reg_prob": "REG確率",
    "combined_prob": "合算確率", "bb_reg_total": "BB_REG合計",
    "reg_ratio": "REG比率", "tail": "末尾",
}


def jp_view(df: pd.DataFrame) -> pd.DataFrame:
    keep = [c for c in DISPLAY_COLS if c in df.columns]
    return df[keep].rename(columns=DISPLAY_COLS)


# ==================================================================
# サイドバー：データ取得
# ==================================================================
st.sidebar.title("⚙️ データ取得")
st.sidebar.caption(f"対象機種: {config.MACHINE_NAME}（ジャグラー系）")

mode = "🟢 実サイト接続" if config.SCRAPER_ENABLED else "🟡 デモデータ"
st.sidebar.info(f"取得モード: {mode}")
st.sidebar.caption(f"保存先: {db.backend_label()}")
st.sidebar.caption(f"登録店舗数: {len(config.STORES)}店")

remaining = scraper.seconds_until_allowed()
if remaining > 0:
    st.sidebar.warning(f"次回の全店取得まで 約{remaining/3600:.1f} 時間（1日1回制限）")
else:
    st.sidebar.success("取得可能です")

fetch_date = st.sidebar.date_input("取得対象日", value=date.today())

if st.sidebar.button("📥 全店データ取得", use_container_width=True, type="primary"):
    prog = st.sidebar.progress(0.0)
    total_ins = total_skip = total_err = 0
    try:
        stores = scraper.target_stores(fetch_date)
    except scraper.FetchBlocked as e:
        stores = []
        st.sidebar.error(f"店舗一覧の取得に失敗: {e}")
    for n, store in enumerate(stores):
        try:
            recs = scraper.fetch_store(store, fetch_date)
            machine = store.get("machine") or config.MACHINE_NAME
            i, s = db.save_records(recs, fetch_date.isoformat(),
                                   store.get("name"), machine)
            total_ins += i
            total_skip += s
        except Exception as e:  # noqa: BLE001
            total_err += 1
            st.sidebar.warning(f"{store.get('name')}: {e}")
        prog.progress((n + 1) / len(stores))
        # マナー：実サイト巡回時は1店ごとに待機
        if config.SCRAPER_ENABLED and n < len(stores) - 1:
            time.sleep(config.REQUEST_DELAY_SEC)
    if stores:
        scraper.mark_run()
        st.sidebar.success(
            f"取得完了: 新規{total_ins}件 / 重複{total_skip}件 / 失敗{total_err}店")

st.sidebar.divider()
st.sidebar.subheader("デモ用")
demo_days = st.sidebar.slider("生成日数", 7, 120, 90)
if st.sidebar.button("🧪 デモ履歴をまとめて生成", use_container_width=True):
    hist = sample_data.generate_history(days=demo_days)
    total_ins = total_skip = 0
    for entry in hist:
        i, s = db.save_records(entry["records"], entry["date"],
                               entry["store"], entry["machine"])
        total_ins += i
        total_skip += s
    st.sidebar.success(
        f"デモ生成: {len(sample_data.DEMO_STORES)}店 -> "
        f"新規{total_ins}件 / 重複{total_skip}件")

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
st.caption("東京都のジャグラーデータを店舗横断で蓄積し、傾向を見える化します")

df_all = db.load_all()
if df_all.empty:
    st.warning("まだデータがありません。左の「全店データ取得」または"
               "「デモ履歴をまとめて生成」を押してください。")
    st.stop()

# 店舗フィルタ（分析タブは選択店に絞って計算。比較タブは全店を使用）
stores = ["（全店）"] + sorted(df_all["store"].dropna().unique().tolist())
sel_store = st.selectbox("🏪 分析する店舗", stores)
df = df_all if sel_store == "（全店）" else df_all[df_all["store"] == sel_store]

c1, c2, c3, c4 = st.columns(4)
c1.metric("総レコード数", f"{len(df_all):,}")
c2.metric("店舗数", f"{df_all['store'].nunique()} 店")
c3.metric("収集日数", f"{df_all['date'].nunique()} 日")
c4.metric("最新データ", df_all["date"].max())

tabs = st.tabs([
    "📋 データ一覧", "🏆 店舗比較", "🏪 店舗傾向分析", "🔢 末尾分析",
    "📅 曜日分析", "🎯 狙い台ランキング", "💾 CSVダウンロード",
])

# --- データ一覧 ---
with tabs[0]:
    st.subheader("データ一覧（合算・REG確率を色分け）")
    st.caption("合算: 黄(1/140-130)→橙(1/129-110)→赤(1/109-80) ｜ "
               "REG: 値が小さいほど高設定示唆")
    dates = sorted(df["date"].dropna().unique().tolist(), reverse=True)
    sel = st.selectbox("日付で絞り込み", ["（全期間）"] + dates)
    view = df if sel == "（全期間）" else df[df["date"] == sel]
    view = view.sort_values(["date", "store", "machine_no"],
                            ascending=[False, True, True])
    st.dataframe(
        exporter.style_dataframe(jp_view(view).rename(
            columns={"合算確率": "combined_prob", "REG確率": "reg_prob"})),
        use_container_width=True, height=520,
    )

# --- 店舗比較（多店舗：どの店が出しているか） ---
with tabs[1]:
    st.subheader("店舗比較ランキング（過去30日）")
    st.caption("平均合算が良い（分母が小さい）店ほど上位＝設定を入れている傾向。"
               "東京都内で狙う店を絞る材料に。")
    stt = analysis.store_trend(df_all, days=30)
    if stt.empty:
        st.info("店舗比較にはデータが必要です。")
    else:
        st.dataframe(stt, use_container_width=True)
        st.bar_chart(stt.set_index("店舗")["平均合算"])
        st.caption("※ 棒が低い店ほど平均合算が良い")

# --- 店舗傾向分析（台番号別） ---
with tabs[2]:
    st.subheader(f"台番号別 傾向（{sel_store}）")
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
with tabs[3]:
    st.subheader(f"末尾別 傾向（{sel_store}）")
    tt = analysis.tail_trend(df)
    st.dataframe(tt, use_container_width=True)
    if not tt.empty:
        st.bar_chart(tt.set_index("末尾")["平均合算"])
        st.caption("※ 棒が低い末尾ほど平均合算が良い傾向")

# --- 曜日分析 ---
with tabs[4]:
    st.subheader(f"曜日別 傾向（{sel_store}）")
    wt = analysis.weekday_trend(df)
    st.dataframe(wt, use_container_width=True)
    if not wt.empty:
        st.bar_chart(wt.set_index("曜日")["平均合算"])
        st.caption("※ 棒が低い曜日ほど平均合算が良い傾向")

# --- 狙い台ランキング ---
with tabs[5]:
    st.subheader(f"翌日の狙い台ランキング（{sel_store}・1〜{config.RANKING_TOP_N}位）")
    st.caption("過去REG・合算・末尾・曜日・前日凹みを加点したスコア順。"
               "完璧な予想ではなく傾向の見える化です。")
    if sel_store == "（全店）":
        st.info("狙い台ランキングは店舗ごとに算出します。上の「分析する店舗」で"
                "店舗を選んでください。")
    else:
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
with tabs[6]:
    st.subheader("CSVダウンロード")
    st.download_button(
        "📥 全店・全データCSV（Excel対応・BOM付き）",
        data=exporter.to_csv_bytes(jp_view(df_all)),
        file_name="jagler_all.csv", mime="text/csv",
    )
    if sel_store != "（全店）":
        rk = analysis.aim_ranking(df)
        if not rk.empty:
            st.download_button(
                f"📥 狙い台ランキングCSV（{sel_store}）",
                data=exporter.to_csv_bytes(rk),
                file_name="jagler_ranking.csv", mime="text/csv",
            )
