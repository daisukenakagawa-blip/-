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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from fx_bot.config import Config
from fx_bot.indicators import atr, ema, rsi
from fx_bot.strategy import entry_signal, trend_direction

CFG = Config()
TOKEN = os.environ.get("DASH_TOKEN", "")


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
refresh(); setInterval(refresh, 30000);
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
