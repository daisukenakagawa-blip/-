"""ローソク足データの読み込み・リサンプリング・上位足マッピング。

ベースは M15 のOHLC。H1/H4 は M15 から時計境界で集約して作る。
各 M15 足の時点で「直近の確定済み上位足」を参照できるようにする
(未来参照を防ぐため、現在進行中の上位足は使わない)。
"""
import bisect
import csv
import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List


@dataclass
class Bar:
    time: int      # 開始時刻 (unix秒, UTC)
    open: float
    high: float
    low: float
    close: float


TF_SECONDS = {"M15": 900, "H1": 3600, "H4": 14400}


def load_csv(path: str) -> List[Bar]:
    """M15のCSVを読み込む。列: time,open,high,low,close

    time は ISO8601 (例 2025-01-02T03:15:00Z) か unix秒。
    """
    bars: List[Bar] = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = {name.strip().lower(): i for i, name in enumerate(header)}
        for row in reader:
            if not row:
                continue
            t = row[idx["time"]].strip()
            ts = int(t) if t.isdigit() else int(
                datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp())
            bars.append(Bar(ts,
                            float(row[idx["open"]]),
                            float(row[idx["high"]]),
                            float(row[idx["low"]]),
                            float(row[idx["close"]])))
    bars.sort(key=lambda b: b.time)
    return bars


def resample(m15: List[Bar], seconds: int) -> List[Bar]:
    """M15足を上位足へ集約 (時計境界でバケット化)。"""
    buckets = {}
    for b in m15:
        key = b.time - (b.time % seconds)
        x = buckets.get(key)
        if x is None:
            buckets[key] = Bar(key, b.open, b.high, b.low, b.close)
        else:
            x.high = max(x.high, b.high)
            x.low = min(x.low, b.low)
            x.close = b.close
    return [buckets[k] for k in sorted(buckets)]


class TimeframeIndex:
    """上位足の確定足を、M15時刻から逆引きするための索引。"""

    def __init__(self, bars: List[Bar], seconds: int):
        self.bars = bars
        self.seconds = seconds
        self.starts = [b.time for b in bars]

    def last_closed_index(self, m15_open_time: int) -> int:
        """m15_open_time の時点で確定済みの最新上位足のindex。無ければ-1。

        開始 start の足は [start, start+seconds) を覆う。これが確定
        しているのは start + seconds <= 現在時刻 のとき。
        """
        return bisect.bisect_right(self.starts, m15_open_time - self.seconds) - 1


def generate_synthetic(months: int = 6, seed: int = 7,
                       start_price: float = 150.0) -> List[Bar]:
    """検証用の合成M15データ (トレンドとレンジが交互に来る乱歩)。

    実データが無くてもバックテストを即実行できるようにするためのもの。
    本番の検証は必ず実データ(ヒストリカル)で行うこと。
    """
    rng = random.Random(seed)
    bars: List[Bar] = []
    price = start_price
    t = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = t + timedelta(days=months * 30)
    drift = 0.0
    regime_left = 0
    while t < end:
        # 週末はスキップ (土=5, 日=6)
        if t.weekday() < 5:
            if regime_left <= 0:
                # 新しいレジーム: トレンド or レンジ
                regime_left = rng.randint(200, 1200)
                drift = rng.choice([-1, 0, 1]) * rng.uniform(0.0, 0.0009)
            regime_left -= 1
            vol = 0.05  # 1足あたりの標準的な値動き(円)
            o = price
            step = drift + rng.gauss(0, vol)
            c = o + step
            hi = max(o, c) + abs(rng.gauss(0, vol * 0.6))
            lo = min(o, c) - abs(rng.gauss(0, vol * 0.6))
            bars.append(Bar(int(t.timestamp()), round(o, 3), round(hi, 3),
                            round(lo, 3), round(c, 3)))
            price = c
        t += timedelta(minutes=15)
    return bars
