#!/usr/bin/env python3
"""HistData等のヒストリカルCSVを、バックテスト用のM15 CSVに変換する。

HistData.com からダウンロードできるUSDJPYのデータ(1分足など)を、
run_backtest.py がそのまま読める `time,open,high,low,close` 形式の
15分足CSVに変換・結合します。zipのままでも読み込めます。

対応する入力フォーマット (自動判別):
  1) HistData Generic ASCII   : 20230102 170000;130.999;131.03;130.995;131.02;0
  2) HistData MetaTrader       : 2023.01.02,17:00,130.999,131.03,130.995,131.02,0
  3) すでに time,open,high,low,close 形式のCSV

使い方:
  # ダウンロードした年次/月次ファイルをまとめて変換 (zip可)
  python3 prepare_histdata.py "DAT_ASCII_USDJPY_M1_*.zip" -o usdjpy_m15.csv

  # HistData Generic ASCII は時刻がEST(UTC-5)なので合わせる場合:
  python3 prepare_histdata.py "*.csv" -o usdjpy_m15.csv --tz-offset -5

  # できたファイルでバックテスト:
  python3 run_backtest.py --csv usdjpy_m15.csv --trades
"""
import argparse
import glob
import io
import sys
import zipfile
from datetime import datetime, timezone

from fx_bot.data import Bar, TF_SECONDS, resample


def _epoch(y, mo, d, h, mi, s, tz_offset_h):
    """Y/M/D H:M:S をUTC unix秒へ。入力が UTC+tz_offset_h 前提で補正。"""
    dt = datetime(y, mo, d, h, mi, s, tzinfo=timezone.utc)
    return int(dt.timestamp()) - int(tz_offset_h * 3600)


def parse_line(line, tz_offset_h):
    """1行を (epoch, o, h, l, c) に。判別不能なら None。"""
    line = line.strip()
    if not line:
        return None
    low = line.lower()
    if low.startswith("time") or low.startswith("date") or low.startswith("<"):
        return None  # ヘッダー行

    # フォーマット1: HistData Generic ASCII (セミコロン区切り)
    if ";" in line:
        p = line.split(";")
        if len(p) >= 5 and " " in p[0]:
            dpart, tpart = p[0].split()
            y, mo, d = int(dpart[0:4]), int(dpart[4:6]), int(dpart[6:8])
            h, mi, s = int(tpart[0:2]), int(tpart[2:4]), int(tpart[4:6])
            return (_epoch(y, mo, d, h, mi, s, tz_offset_h),
                    float(p[1]), float(p[2]), float(p[3]), float(p[4]))
        return None

    # カンマ区切り (フォーマット2 or 3)
    p = line.split(",")
    if len(p) >= 6 and "." in p[0] and ":" in p[1]:
        # フォーマット2: HistData MetaTrader
        y, mo, d = (int(x) for x in p[0].split("."))
        h, mi = (int(x) for x in p[1].split(":")[:2])
        return (_epoch(y, mo, d, h, mi, 0, tz_offset_h),
                float(p[2]), float(p[3]), float(p[4]), float(p[5]))
    if len(p) >= 5:
        # フォーマット3: time,open,high,low,close (timeはISO8601かunix秒)
        t = p[0].strip()
        if t.isdigit():
            epoch = int(t)
        else:
            epoch = int(datetime.fromisoformat(
                t.replace("Z", "+00:00")).timestamp())
        return (epoch, float(p[1]), float(p[2]), float(p[3]), float(p[4]))
    return None


def read_source(path, tz_offset_h):
    """1ファイル(.csv または .zip)からBarを読み出す。"""
    bars = []

    def feed(text_lines):
        for line in text_lines:
            r = parse_line(line, tz_offset_h)
            if r:
                bars.append(Bar(r[0], r[1], r[2], r[3], r[4]))

    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith(".csv"):
                    with z.open(name) as f:
                        feed(io.TextIOWrapper(f, encoding="utf-8", errors="ignore"))
    else:
        with open(path, encoding="utf-8", errors="ignore") as f:
            feed(f)
    return bars


def main():
    ap = argparse.ArgumentParser(description="ヒストリカルCSV→M15変換")
    ap.add_argument("inputs", nargs="+", help="入力ファイル/グロブ (.csv / .zip)")
    ap.add_argument("-o", "--out", default="usdjpy_m15.csv", help="出力CSV")
    ap.add_argument("--tz-offset", type=float, default=0.0,
                    help="入力時刻のUTCオフセット時間 (HistData Generic ASCIIは -5)")
    args = ap.parse_args()

    paths = []
    for pat in args.inputs:
        matched = sorted(glob.glob(pat))
        if not matched:
            print(f"警告: 一致するファイルがありません: {pat}")
        paths.extend(matched)
    if not paths:
        print("入力ファイルが見つかりません。")
        return 1

    all_bars = []
    for p in paths:
        b = read_source(p, args.tz_offset)
        print(f"  {p}: {len(b):,} 本")
        all_bars.extend(b)
    if not all_bars:
        print("有効なデータを読み込めませんでした。フォーマットを確認してください。")
        return 1

    # 時刻でソートし重複除去
    all_bars.sort(key=lambda b: b.time)
    dedup = []
    seen = -1
    for b in all_bars:
        if b.time != seen:
            dedup.append(b)
            seen = b.time
    print(f"読み込み合計: {len(dedup):,} 本 (重複除去後)")

    # M15へ集約 (入力が1分足等でも、すでにM15でも正しく動く)
    m15 = resample(dedup, TF_SECONDS["M15"])

    with open(args.out, "w") as f:
        f.write("time,open,high,low,close\n")
        for b in m15:
            ts = datetime.fromtimestamp(b.time, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            f.write(f"{ts},{b.open},{b.high},{b.low},{b.close}\n")

    first = datetime.fromtimestamp(m15[0].time, tz=timezone.utc).strftime("%Y-%m-%d")
    last = datetime.fromtimestamp(m15[-1].time, tz=timezone.utc).strftime("%Y-%m-%d")
    print(f"\n出力: {args.out}")
    print(f"M15足: {len(m15):,} 本  期間: {first} 〜 {last}")
    print(f"\n次のコマンドでバックテスト:")
    print(f"  python3 run_backtest.py --csv {args.out} --trades")
    return 0


if __name__ == "__main__":
    sys.exit(main())
