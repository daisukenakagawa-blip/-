"""バックテストエンジン。

M15足を1本ずつ進めながら、確定済みのH4/H1指標を参照してエントリーし、
ATRベースのSL/TPで決済する。1ポジション固定・固定リスク%のため、
ナンピンやマーチンは構造的に発生しない。

損益は口座通貨=JPY前提で計算 (OANDA Japan口座はJPY建て)。
USDJPYでは「1単位(=1USD)を value 円で売買」するので、
  損益(円) = 数量(USD) × (決済価格 - 約定価格) × 方向
となる。
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .config import Config
from .data import Bar, TimeframeIndex, resample, TF_SECONDS
from .indicators import atr, ema, rsi
from .strategy import entry_signal, trend_direction


@dataclass
class Trade:
    direction: int
    entry_time: int
    entry: float
    sl: float
    tp: float
    units: float
    exit_time: int = 0
    exit: float = 0.0
    pnl: float = 0.0
    reason: str = ""


@dataclass
class Result:
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    start_balance: float = 0.0
    end_balance: float = 0.0

    def report(self) -> str:
        n = len(self.trades)
        if n == 0:
            return "トレードが発生しませんでした。期間やパラメーターを見直してください。"
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        gross_win = sum(t.pnl for t in wins)
        gross_loss = -sum(t.pnl for t in losses)
        pf = (gross_win / gross_loss) if gross_loss > 0 else float("inf")
        net = self.end_balance - self.start_balance

        peak = self.equity_curve[0]
        max_dd = 0.0
        for eq in self.equity_curve:
            peak = max(peak, eq)
            max_dd = max(max_dd, (peak - eq) / peak * 100 if peak > 0 else 0)

        avg_win = gross_win / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0

        lines = [
            "==================== バックテスト結果 ====================",
            f"初期資金       : {self.start_balance:,.0f} 円",
            f"最終資金       : {self.end_balance:,.0f} 円",
            f"純損益         : {net:+,.0f} 円  ({net / self.start_balance * 100:+.1f}%)",
            f"総トレード数   : {n}",
            f"勝ち / 負け    : {len(wins)} / {len(losses)}",
            f"勝率           : {len(wins) / n * 100:.1f}%",
            f"プロフィットF  : {pf:.2f}" + ("  (1.2以上が目安)" if pf != float('inf') else ""),
            f"平均利益       : {avg_win:+,.0f} 円",
            f"平均損失       : {-avg_loss:+,.0f} 円",
            f"最大ドローダウン: {max_dd:.1f}%",
            "==========================================================",
        ]
        return "\n".join(lines)


def _calendar_key(ts: int):
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.year, dt.month, dt.day


def run(m15: List[Bar], cfg: Config) -> Result:
    if len(m15) < 300:
        raise ValueError("データが不足しています (M15が300本以上必要)。")

    h1 = resample(m15, TF_SECONDS["H1"])
    h4 = resample(m15, TF_SECONDS["H4"])
    atr_tf = resample(m15, TF_SECONDS[cfg.atr_timeframe])

    # 上位足の指標を事前計算
    ema_fast = ema([b.close for b in h4], cfg.ema_fast)
    ema_slow = ema([b.close for b in h4], cfg.ema_slow)
    rsi_h1 = rsi([b.close for b in h1], cfg.rsi_period)
    atr_vals = atr([b.high for b in atr_tf], [b.low for b in atr_tf],
                   [b.close for b in atr_tf], cfg.atr_period)

    idx_h4 = TimeframeIndex(h4, TF_SECONDS["H4"])
    idx_h1 = TimeframeIndex(h1, TF_SECONDS["H1"])
    idx_atr = TimeframeIndex(atr_tf, TF_SECONDS[cfg.atr_timeframe])

    balance = cfg.initial_balance
    res = Result(start_balance=balance)
    res.equity_curve.append(balance)

    pos: Optional[Trade] = None
    half_spread = cfg.spread_pips * cfg.pip_size / 2.0

    # 日次/月次の損失リミット管理
    cur_day = None
    cur_month = None
    day_start_bal = balance
    month_start_bal = balance
    paused_day = False
    paused_month = False

    n = cfg.breakout_bars
    for i in range(n + 2, len(m15)):
        bar = m15[i]
        y, mo, d = _calendar_key(bar.time)

        if cur_day != (y, mo, d):
            cur_day = (y, mo, d)
            day_start_bal = balance
            paused_day = False
        if cur_month != (y, mo):
            cur_month = (y, mo)
            month_start_bal = balance
            paused_month = False

        # --- 保有ポジションの決済判定 (この足の高値/安値でSL/TP接触) ---
        if pos is not None:
            hit = None
            if pos.direction == 1:
                # 同足でSLとTP両方なら保守的にSLを優先
                if bar.low <= pos.sl:
                    hit = (pos.sl, "SL")
                elif bar.high >= pos.tp:
                    hit = (pos.tp, "TP")
            else:
                if bar.high >= pos.sl:
                    hit = (pos.sl, "SL")
                elif bar.low <= pos.tp:
                    hit = (pos.tp, "TP")
            if hit is not None:
                exit_px, reason = hit
                pnl = pos.units * (exit_px - pos.entry) * pos.direction
                pos.exit_time, pos.exit, pos.pnl, pos.reason = bar.time, exit_px, pnl, reason
                balance += pnl
                res.trades.append(pos)
                res.equity_curve.append(balance)
                pos = None

        # 損失リミット (確定損益ベース)
        if not paused_day and balance - day_start_bal <= -day_start_bal * cfg.max_daily_loss_pct / 100:
            paused_day = True
        if not paused_month and balance - month_start_bal <= -month_start_bal * cfg.max_monthly_loss_pct / 100:
            paused_month = True

        if pos is not None or paused_day or paused_month:
            continue

        # --- 上位足の確定値を取得 ---
        j4 = idx_h4.last_closed_index(bar.time)
        j1 = idx_h1.last_closed_index(bar.time)
        ja = idx_atr.last_closed_index(bar.time)
        if j4 < 0 or j1 < 0 or ja < 0:
            continue
        ef, es = ema_fast[j4], ema_slow[j4]
        rv = rsi_h1[j1]
        av = atr_vals[ja]
        if ef is None or es is None or rv is None or av is None or av <= 0:
            continue

        direction = trend_direction(ef, es)
        if direction == 0:
            continue

        # M15ブレイク: 確定足(i-1)の終値が、その前 n 本(i-1-n .. i-2)の
        # 高値/安値を抜けたか。シグナル足自身は参照窓に含めない。
        recent_high = max(m15[k].high for k in range(i - 1 - n, i - 1))
        recent_low = min(m15[k].low for k in range(i - 1 - n, i - 1))
        sig = entry_signal(direction, rv, m15[i - 1].close, recent_high, recent_low, cfg)
        # 判定は確定済みの1本前(i-1)で行い、現在足(i)の始値付近で約定する
        if sig == 0:
            continue

        sl_dist = av * cfg.sl_atr_mult
        tp_dist = av * cfg.tp_atr_mult
        if sl_dist <= 0 or tp_dist / sl_dist < cfg.min_rr - 1e-9:
            continue

        # 約定価格 (スプレッド込み: 買いはAsk=mid+half, 売りはBid=mid-half)
        mid = bar.open
        if sig == 1:
            entry = mid + half_spread
            sl = entry - sl_dist
            tp = entry + tp_dist
        else:
            entry = mid - half_spread
            sl = entry + sl_dist
            tp = entry - tp_dist

        # 1%リスクから数量(USD)を算出: 損失額(円) = units * sl_dist = balance*risk%
        risk_money = balance * cfg.risk_percent / 100.0
        units = risk_money / sl_dist
        if units <= 0:
            continue

        pos = Trade(direction=sig, entry_time=bar.time, entry=entry,
                    sl=sl, tp=tp, units=units)

    res.end_balance = balance
    if not res.equity_curve:
        res.equity_curve.append(balance)
    return res
