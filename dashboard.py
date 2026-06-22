#!/usr/bin/env python3
"""USD/JPY 独自ボット - スマホ用モニタリング・ダッシュボード。

スマホのブラウザで開いて、ボットの状況(残高・ポジション・現在のシグナル
判定・本日/今月損益)を確認するための軽量Webサーバー。標準ライブラリのみ。

  python3 dashboard.py                 # http://localhost:8000 で起動
  python3 dashboard.py --port 8000

これを公開URLにすればスマホから開けます (READMEのデプロイ手順を参照)。
※安全のため、環境変数 DASH_TOKEN を設定すると ?token=... が必須になります。
※このダッシュボードは「監視専用」。発注は run_live.py 側が行います。
"""
import argparse
import json
import os
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from fx_bot.backtest import run as run_backtest
from fx_bot.config import Config
from fx_bot.data import TF_SECONDS, TimeframeIndex, generate_synthetic, resample
from fx_bot.indicators import atr, ema, rsi
from fx_bot.strategy import entry_signal, trend_direction

CFG = Config()
TOKEN = os.environ.get("DASH_TOKEN", "")

_CHART_CACHE = {"t": 0.0, "data": None}
CHART_SHOW = 140          # 表示するM15本数
CHART_HISTORY = 4000      # 指標/シグナル計算に使う履歴本数(EMA200(H4)に十分な量)


def _candles_for_chart():
    """チャート用のM15足を返す。(ライブ or サンプル, ソース表示用ラベル)"""
    try:
        from fx_bot.oanda import OandaClient
        client = OandaClient()
        m15 = client.candles(CFG.symbol, "M15", count=CHART_HISTORY)
        if len(m15) >= 300:
            return m15, "ライブ"
    except Exception:
        pass
    # 未接続ならサンプル(合成)データで表示
    return generate_synthetic(months=6, seed=7), "サンプル"


def build_chart() -> dict:
    """MT4風チャート用データ: ローソク足 + EMA50/200 + 売買シグナル矢印。

    EMAはH4(環境認識足)で計算し、各M15足が見ている確定H4値を割り当てる。
    シグナル矢印はバックテストエンジンを実データに通して得たエントリー位置。
    """
    if _CHART_CACHE["data"] and time.time() - _CHART_CACHE["t"] < 60:
        return _CHART_CACHE["data"]

    m15, source = _candles_for_chart()

    # H4のEMA50/200を計算し、M15時刻へ割り当て(ボットが実際に見ている値)
    h4 = resample(m15, TF_SECONDS["H4"])
    ef = ema([b.close for b in h4], CFG.ema_fast)
    es = ema([b.close for b in h4], CFG.ema_slow)
    idx_h4 = TimeframeIndex(h4, TF_SECONDS["H4"])

    # シグナル位置(エントリー)をバックテストで取得
    markers = []
    try:
        res = run_backtest(m15, CFG)
        for t in res.trades:
            markers.append({"time": t.entry_time, "dir": t.direction})
    except Exception:
        pass

    # 表示窓: ライブは最新側。サンプルは最後のシグナルが見える位置に寄せる
    end = len(m15)
    if source == "サンプル" and markers:
        last_t = markers[-1]["time"]
        for i in range(len(m15) - 1, -1, -1):
            if m15[i].time == last_t:
                end = min(len(m15), i + 20)
                break
    start = max(0, end - CHART_SHOW)
    visible = m15[start:end]
    vstart = visible[0].time
    candles = []
    for b in visible:
        j = idx_h4.last_closed_index(b.time)
        candles.append({
            "t": b.time, "o": b.open, "h": b.high, "l": b.low, "c": b.close,
            "ef": ef[j] if j >= 0 and ef[j] is not None else None,
            "es": es[j] if j >= 0 and es[j] is not None else None,
        })
    vis_markers = [m for m in markers if m["time"] >= vstart]

    data = {
        "symbol": "USDJPY  M15",
        "source": source,
        "candles": candles,
        "markers": vis_markers,
        "ema_fast": CFG.ema_fast,
        "ema_slow": CFG.ema_slow,
    }
    _CHART_CACHE.update(t=time.time(), data=data)
    return data


def build_status() -> dict:
    """OANDA接続があればライブ状況を、無ければオフライン状態を返す。"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        from fx_bot.oanda import OandaClient
        client = OandaClient()
    except Exception as e:
        return {"mode": "offline", "time": now, "message": str(e)}

    try:
        inst = CFG.symbol
        summary = client.account_summary()
        balance = float(summary["balance"])
        ccy = summary.get("currency", "")
        positions = client.open_positions(inst)

        m15 = client.candles(inst, "M15", count=CFG.breakout_bars + 5)
        h1 = client.candles(inst, "H1", count=CFG.rsi_period + 5)
        h4 = client.candles(inst, "H4", count=CFG.ema_slow + 5)
        ef = ema([b.close for b in h4], CFG.ema_fast)[-1]
        es = ema([b.close for b in h4], CFG.ema_slow)[-1]
        rv = rsi([b.close for b in h1], CFG.rsi_period)[-1]
        av = atr([b.high for b in h1], [b.low for b in h1],
                 [b.close for b in h1], CFG.atr_period)[-1]

        direction = trend_direction(ef, es) if ef and es else 0
        trend = "買い環境" if direction == 1 else "売り環境" if direction == -1 else "中立"

        sig_txt = "条件待ち"
        if direction != 0 and rv is not None and len(m15) > CFG.breakout_bars + 1:
            window = m15[-(CFG.breakout_bars + 1):-1]
            rh = max(b.high for b in window)
            rl = min(b.low for b in window)
            s = entry_signal(direction, rv, m15[-1].close, rh, rl, CFG)
            if s == 1:
                sig_txt = "★ 買いシグナル"
            elif s == -1:
                sig_txt = "★ 売りシグナル"

        return {
            "mode": "live" if client.env == "live" else "demo",
            "time": now,
            "balance": balance,
            "currency": ccy,
            "positions": positions,
            "trend": trend,
            "rsi": None if rv is None else round(rv, 1),
            "atr_pips": None if av is None else round(av / CFG.pip_size, 1),
            "price": m15[-1].close if m15 else None,
            "signal": sig_txt,
        }
    except Exception as e:
        return {"mode": "error", "time": now, "message": str(e)}


PAGE = """<!DOCTYPE html>
<html lang="ja"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>USDJPY Bot</title>
<style>
  :root{color-scheme:dark}
  body{margin:0;background:#0e1117;color:#e6edf3;font-family:-apple-system,Segoe UI,Roboto,sans-serif}
  .wrap{max-width:480px;margin:0 auto;padding:16px}
  h1{font-size:18px;margin:8px 0 2px}
  .sub{color:#8b949e;font-size:12px;margin-bottom:14px}
  .card{background:#161b22;border:1px solid #30363d;border-radius:14px;padding:16px;margin-bottom:12px}
  .row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid #21262d}
  .row:last-child{border-bottom:none}
  .k{color:#8b949e;font-size:14px}
  .v{font-size:16px;font-weight:600}
  .big{font-size:30px;font-weight:700;letter-spacing:.5px}
  .sig{font-size:20px;font-weight:700;text-align:center;padding:14px;border-radius:12px;background:#21262d}
  .buy{color:#3fb950}.sell{color:#f85149}.muted{color:#8b949e}
  .pill{font-size:12px;padding:3px 10px;border-radius:999px;background:#21262d}
  .live{color:#f85149;border:1px solid #f85149}
  .demo{color:#3fb950;border:1px solid #3fb950}
  .err{background:#3d1c1c;border:1px solid #f85149;color:#ffb4ab;padding:14px;border-radius:12px;font-size:13px}
  .foot{color:#6e7681;font-size:11px;text-align:center;margin-top:18px;line-height:1.6}
</style></head>
<body><div class="wrap">
  <h1>USD/JPY 自動売買ボット</h1>
  <div class="sub" id="time">読み込み中...</div>
  <div class="card" style="padding:10px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin:2px 4px 8px">
      <span class="v" id="chartTitle">USDJPY M15</span>
      <span class="pill" id="chartSrc">-</span>
    </div>
    <canvas id="chart" style="width:100%;height:280px;display:block"></canvas>
    <div class="foot" style="margin-top:6px">
      <span style="color:#58a6ff">━ EMA50</span>　<span style="color:#f0883e">━ EMA200</span>
      <span style="color:#3fb950">▲買い</span> <span style="color:#f85149">▼売り</span>
    </div>
  </div>
  <div id="body"><div class="card muted">接続中...</div></div>
  <div class="foot">30秒ごとに自動更新 / 監視専用画面<br>発注はサーバー側のボットが行います</div>
</div>
<script>
function yen(n){return Number(n).toLocaleString('ja-JP',{maximumFractionDigits:0})}
async function refresh(){
  try{
    const r = await fetch('api/status'+location.search);
    const d = await r.json();
    document.getElementById('time').textContent = d.time;
    const b = document.getElementById('body');
    if(d.mode==='offline'||d.mode==='error'){
      b.innerHTML = '<div class="err"><b>'+(d.mode==='offline'?'未接続':'エラー')+'</b><br>'+
        (d.message||'')+'<br><br>サーバーで OANDA_TOKEN / OANDA_ACCOUNT を設定してください。</div>';
      return;
    }
    const sigCls = d.signal.indexOf('買い')>=0?'buy':d.signal.indexOf('売り')>=0?'sell':'muted';
    const modeCls = d.mode==='live'?'live':'demo';
    const modeTxt = d.mode==='live'?'本番':'デモ';
    b.innerHTML =
      '<div class="card"><div class="row"><span class="k">口座状態</span>'+
        '<span class="pill '+modeCls+'">'+modeTxt+'</span></div>'+
        '<div class="row"><span class="k">残高</span><span class="big">'+yen(d.balance)+' '+d.currency+'</span></div>'+
        '<div class="row"><span class="k">保有ポジション</span><span class="v">'+(d.positions>0?d.positions+' 件':'なし')+'</span></div>'+
      '</div>'+
      '<div class="card"><div class="sig '+sigCls+'">'+d.signal+'</div></div>'+
      '<div class="card">'+
        '<div class="row"><span class="k">現在値</span><span class="v">'+(d.price??'-')+'</span></div>'+
        '<div class="row"><span class="k">H4トレンド</span><span class="v">'+d.trend+'</span></div>'+
        '<div class="row"><span class="k">H1 RSI(14)</span><span class="v">'+(d.rsi??'-')+'</span></div>'+
        '<div class="row"><span class="k">ATR(14)</span><span class="v">'+(d.atr_pips??'-')+' pips</span></div>'+
      '</div>';
  }catch(e){
    document.getElementById('body').innerHTML='<div class="err">読み込み失敗: '+e+'</div>';
  }
}
// ===== MT4風ローソク足チャート (canvasに自前描画・外部ライブラリなし) =====
function drawChart(d){
  const cv = document.getElementById('chart');
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  const g = cv.getContext('2d'); g.scale(dpr, dpr);
  g.clearRect(0,0,W,H);
  g.fillStyle = '#0d1117'; g.fillRect(0,0,W,H);
  const cs = d.candles || [];
  if(cs.length === 0){ g.fillStyle='#8b949e'; g.fillText('データ取得中...',12,24); return; }

  const padL=6, padR=52, padT=10, padB=14;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  let lo=Infinity, hi=-Infinity;
  for(const c of cs){ lo=Math.min(lo,c.l); hi=Math.max(hi,c.h);
    if(c.ef){lo=Math.min(lo,c.ef);hi=Math.max(hi,c.ef);}
    if(c.es){lo=Math.min(lo,c.es);hi=Math.max(hi,c.es);} }
  const pad=(hi-lo)*0.08||0.1; lo-=pad; hi+=pad;
  const x = i => padL + (i+0.5)*(plotW/cs.length);
  const y = v => padT + (hi-v)/(hi-lo)*plotH;

  // グリッド + 価格目盛り
  g.strokeStyle='#21262d'; g.fillStyle='#6e7681'; g.font='10px sans-serif'; g.lineWidth=1;
  for(let k=0;k<=4;k++){ const v=lo+(hi-lo)*k/4, yy=y(v);
    g.beginPath(); g.moveTo(padL,yy); g.lineTo(padL+plotW,yy); g.stroke();
    g.fillText(v.toFixed(3), padL+plotW+4, yy+3); }

  // ローソク足
  const cw = Math.max(1.5, plotW/cs.length*0.6);
  for(let i=0;i<cs.length;i++){ const c=cs[i], up=c.c>=c.o;
    g.strokeStyle = up?'#3fb950':'#f85149'; g.fillStyle = up?'#3fb950':'#f85149';
    g.beginPath(); g.moveTo(x(i), y(c.h)); g.lineTo(x(i), y(c.l)); g.stroke();
    const yo=y(c.o), yc=y(c.c); g.fillRect(x(i)-cw/2, Math.min(yo,yc), cw, Math.max(1,Math.abs(yc-yo))); }

  // EMA線
  function line(key,color){ g.strokeStyle=color; g.lineWidth=1.4; g.beginPath(); let started=false;
    for(let i=0;i<cs.length;i++){ const v=cs[i][key]; if(v==null){started=false;continue;}
      const px=x(i),py=y(v); if(!started){g.moveTo(px,py);started=true;}else g.lineTo(px,py);} g.stroke(); }
  line('ef','#58a6ff'); line('es','#f0883e');

  // シグナル矢印
  const t2i = {}; cs.forEach((c,i)=>t2i[c.t]=i);
  for(const m of (d.markers||[])){ const i=t2i[m.time]; if(i==null) continue;
    g.fillStyle = m.dir===1?'#3fb950':'#f85149'; g.beginPath();
    if(m.dir===1){ const yy=y(cs[i].l)+10; g.moveTo(x(i),yy-7); g.lineTo(x(i)-5,yy); g.lineTo(x(i)+5,yy); }
    else { const yy=y(cs[i].h)-10; g.moveTo(x(i),yy+7); g.lineTo(x(i)-5,yy); g.lineTo(x(i)+5,yy); }
    g.closePath(); g.fill(); }

  // 現在値ライン
  const last=cs[cs.length-1].c; g.strokeStyle='#e6edf3'; g.setLineDash([3,3]); g.lineWidth=1;
  g.beginPath(); g.moveTo(padL,y(last)); g.lineTo(padL+plotW,y(last)); g.stroke(); g.setLineDash([]);
  g.fillStyle='#e6edf3'; g.fillRect(padL+plotW, y(last)-7, padR, 14);
  g.fillStyle='#0d1117'; g.font='bold 10px sans-serif'; g.fillText(last.toFixed(3), padL+plotW+4, y(last)+3);
}
async function refreshChart(){
  try{
    const r = await fetch('api/chart'+location.search);
    const d = await r.json();
    document.getElementById('chartTitle').textContent = d.symbol||'USDJPY M15';
    document.getElementById('chartSrc').textContent = d.source||'-';
    drawChart(d);
  }catch(e){}
}
refresh(); setInterval(refresh, 30000);
refreshChart(); setInterval(refreshChart, 60000);
window.addEventListener('resize', refreshChart);
</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _auth_ok(self) -> bool:
        if not TOKEN:
            return True
        q = parse_qs(urlparse(self.path).query)
        return q.get("token", [""])[0] == TOKEN

    def do_GET(self):
        path = urlparse(self.path).path
        if not self._auth_ok():
            self.send_response(401)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("401 Unauthorized: ?token=... が必要です".encode())
            return
        if path == "/" or path == "/index.html":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/status":
            body = json.dumps(build_status(), ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/chart":
            try:
                payload = build_chart()
            except Exception as e:
                payload = {"error": str(e), "candles": [], "markers": []}
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass  # アクセスログ抑制


def main():
    p = argparse.ArgumentParser(description="USD/JPY ボット スマホ用ダッシュボード")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--host", default="0.0.0.0")
    args = p.parse_args()
    print(f"ダッシュボード起動: http://{args.host}:{args.port}")
    if TOKEN:
        print("アクセスには ?token=... が必要です (DASH_TOKEN設定済み)")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
