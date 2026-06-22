#!/usr/bin/env python3
"""USD/JPY 独自ボット - 個人用ワンコマンド起動 (ボット本体 + スマホ画面)。

自分専用に、自宅PCなどで1コマンドで動かすためのランチャー。
  - 売買ボット本体 (run_live と同じロジック) を裏で動かし
  - スマホから見るダッシュボードを同じプロセスで立ち上げる
起動時に「スマホで開くURL」と「パスワード(トークン)」を表示します。

使い方:
  export OANDA_TOKEN=...        # v20 APIトークン
  export OANDA_ACCOUNT=...      # 口座ID
  export OANDA_ENV=practice     # practice(デモ) / live(本番)

  python3 run_bot.py                 # 売買 + スマホ画面 (デモ)
  python3 run_bot.py --monitor       # 売買せず監視だけ (スマホ画面のみ)
  python3 run_bot.py --dry           # 判定ログは出すが発注しない

★ 公開しないこと。自宅WiFi内のスマホから開く想定です。外から見たい場合は
  READMEのトンネル手順を使い、必ずトークンを付けたまま運用してください。
"""
import argparse
import os
import secrets
import socket
import sys
import threading
import time

import dashboard
from fx_bot.config import Config
from fx_bot.live import evaluate_and_trade, log

TOKEN_FILE = ".fxbot_token"


def get_or_make_token() -> str:
    """トークンを 環境変数 → ファイル の順で取得。無ければ生成して保存。"""
    env = os.environ.get("DASH_TOKEN", "").strip()
    if env:
        return env
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            t = f.read().strip()
            if t:
                return t
    t = secrets.token_urlsafe(9)
    with open(TOKEN_FILE, "w") as f:
        f.write(t)
    return t


def get_lan_ip() -> str:
    """自宅ネットワークでの自分のIPアドレスを推定。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_dashboard(port: int, token: str):
    from http.server import ThreadingHTTPServer
    dashboard.TOKEN = token  # ダッシュボードにトークンを注入
    srv = ThreadingHTTPServer(("0.0.0.0", port), dashboard.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def print_banner(port: int, token: str, monitor: bool):
    ip = get_lan_ip()
    bar = "=" * 56
    print(bar)
    print(" USD/JPY 自動売買ボット - 起動しました")
    print(bar)
    print(" スマホで下のURLを開いてください (同じWiFiに接続):")
    print(f"   http://{ip}:{port}/?token={token}")
    print()
    print(" PCのブラウザからは:")
    print(f"   http://localhost:{port}/?token={token}")
    print()
    print(f" パスワード(トークン): {token}")
    print(f"   ※ {TOKEN_FILE} に保存済み。次回も同じURLで開けます。")
    print(" 動作モード:", "監視のみ(発注しない)" if monitor else "売買あり")
    print(bar)
    print(" ヒント: スマホで開いた後『ホーム画面に追加』するとアプリ風に使えます")
    print(bar, flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="USD/JPY 独自ボット 個人用ランチャー")
    p.add_argument("--monitor", action="store_true", help="売買せず監視画面だけ動かす")
    p.add_argument("--dry", action="store_true", help="判定ログは出すが発注しない")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--interval", type=int, default=30, help="判定の間隔(秒)")
    args = p.parse_args()

    token = get_or_make_token()
    start_dashboard(args.port, token)
    print_banner(args.port, token, args.monitor)

    if args.monitor:
        # 監視のみ: ダッシュボードを動かし続けるだけ
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            log("停止しました。")
        return 0

    # 売買モード: OANDAに接続してトレードループを回す
    from fx_bot.oanda import OandaClient, OandaError
    try:
        client = OandaClient()
    except OandaError as e:
        log(f"設定エラー: {e}")
        log("OANDA_TOKEN / OANDA_ACCOUNT を設定するか、--monitor で監視のみ起動してください。")
        return 1

    cfg = Config()
    instrument = cfg.symbol
    digits = 3
    log(f"接続先: {client.env}  口座: {client.account}  銘柄: {instrument}")
    log(f"残高: {client.balance():,.0f} {client.account_summary().get('currency','')}")
    if client.env == "live":
        log("★★★ 本番(live)口座です。実資金が動きます。★★★")

    state: dict = {}
    try:
        while True:
            try:
                evaluate_and_trade(client, cfg, instrument, digits, state, dry=args.dry)
            except Exception as e:
                log(f"エラー(継続): {e}")
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        log("停止しました。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
