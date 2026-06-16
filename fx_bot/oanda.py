"""OANDA v20 REST API クライアント (標準ライブラリのみ)。

実発注はこのモジュール経由で行う。MT4/MT5は不要。
OANDA Japan / OANDA(海外) どちらでも v20 APIなら利用可。

事前準備:
  1. OANDAで口座開設し、v20のAPIトークンを発行
  2. 環境変数を設定:
       OANDA_TOKEN     ... APIトークン
       OANDA_ACCOUNT   ... 口座ID (101-xxx-xxxxxxx-xxx 形式)
       OANDA_ENV       ... "practice"(デモ) または "live"(本番)

注意: 本番(live)を指定すると実資金が動く。必ず practice で十分検証すること。
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional

from .data import Bar

_HOSTS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}
_GRAN = {"M15": "M15", "H1": "H1", "H4": "H4"}


class OandaError(RuntimeError):
    pass


class OandaClient:
    def __init__(self, token: Optional[str] = None, account: Optional[str] = None,
                 env: Optional[str] = None):
        self.token = token or os.environ.get("OANDA_TOKEN", "")
        self.account = account or os.environ.get("OANDA_ACCOUNT", "")
        self.env = (env or os.environ.get("OANDA_ENV", "practice")).lower()
        if self.env not in _HOSTS:
            raise OandaError("OANDA_ENV は practice か live を指定してください。")
        if not self.token or not self.account:
            raise OandaError("OANDA_TOKEN と OANDA_ACCOUNT を設定してください。")
        self.host = _HOSTS[self.env]

    # --- 低レベルHTTP ---
    def _request(self, method: str, path: str, params=None, body=None):
        url = self.host + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", "Bearer " + self.token)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            raise OandaError(f"HTTP {e.code}: {e.read().decode()[:300]}")
        except urllib.error.URLError as e:
            raise OandaError(f"接続エラー: {e}")

    # --- データ取得 ---
    def candles(self, instrument: str, timeframe: str, count: int = 300,
                complete_only: bool = True) -> List[Bar]:
        """確定済みローソク足を取得 (BID/ASKの中値=midを使用)。"""
        path = f"/v3/instruments/{instrument}/candles"
        params = {"granularity": _GRAN[timeframe], "count": count, "price": "M"}
        res = self._request("GET", path, params=params)
        bars: List[Bar] = []
        for c in res.get("candles", []):
            if complete_only and not c.get("complete", False):
                continue
            mid = c["mid"]
            # OANDAのtimeはRFC3339文字列。unix秒に変換。
            from datetime import datetime
            ts = int(datetime.fromisoformat(
                c["time"].replace("Z", "+00:00")).timestamp())
            bars.append(Bar(ts, float(mid["o"]), float(mid["h"]),
                            float(mid["l"]), float(mid["c"])))
        return bars

    def account_summary(self) -> dict:
        path = f"/v3/accounts/{self.account}/summary"
        return self._request("GET", path)["account"]

    def balance(self) -> float:
        return float(self.account_summary()["balance"])

    def open_positions(self, instrument: str) -> int:
        """指定銘柄のオープンポジション数 (ロング+ショート建玉の有無)。"""
        path = f"/v3/accounts/{self.account}/openPositions"
        res = self._request("GET", path)
        cnt = 0
        for p in res.get("positions", []):
            if p["instrument"] != instrument:
                continue
            if int(p["long"]["units"]) != 0:
                cnt += 1
            if int(p["short"]["units"]) != 0:
                cnt += 1
        return cnt

    # --- 発注 ---
    def market_order(self, instrument: str, units: int,
                     sl_price: float, tp_price: float, digits: int = 3) -> dict:
        """成行 + SL/TP を同時発注。units>0=買い, units<0=売り。"""
        path = f"/v3/accounts/{self.account}/orders"
        body = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(int(units)),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": f"{sl_price:.{digits}f}"},
                "takeProfitOnFill": {"price": f"{tp_price:.{digits}f}"},
            }
        }
        return self._request("POST", path, body=body)

    def has_high_impact_news(self, minutes: int = 60) -> bool:
        """OANDA v20には経済カレンダーAPIが無いため常にFalse。

        実運用で指標フィルターを厳密に使う場合は、外部の経済指標API
        (例: ForexFactory/Investing系のフィード)を別途接続して
        このメソッドを差し替えること。
        """
        return False
