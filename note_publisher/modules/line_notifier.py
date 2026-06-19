# -*- coding: utf-8 -*-
"""
LINE に通知を送る小さなモジュール(追加ライブラリ不要・標準のurllibのみ)。

LINE Messaging API を使います。環境変数で設定してください:
  - LINE_CHANNEL_ACCESS_TOKEN : 必須。LINE公式アカウントのチャネルアクセストークン
  - LINE_USER_ID              : 任意。指定すればその人へ push、無ければ broadcast(友だち全員)

個人利用なら「自分の公式アカウントを友だち追加 → broadcast」が最も簡単で、
USER_ID の取得は不要です(トークンだけでOK)。

※ かつての「LINE Notify」は2025年3月末で終了したため、本モジュールは
   Messaging API を使用します。
"""
import json
import os
import urllib.request

BROADCAST_URL = "https://api.line.me/v2/bot/message/broadcast"
PUSH_URL = "https://api.line.me/v2/bot/message/push"
MAX_LEN = 4900  # LINEテキストは5000字まで。余裕をもって切る


def is_configured() -> bool:
    return bool(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))


def build_message(messages):
    """文字列 or 文字列リストを LINE のtextメッセージ配列にする。"""
    if isinstance(messages, str):
        messages = [messages]
    out = []
    for m in messages[:5]:  # LINEは1リクエスト最大5メッセージ
        out.append({"type": "text", "text": str(m)[:MAX_LEN]})
    return out


def notify(text, logger=None):
    """LINE に text を送る。戻り値 (ok: bool, message: str)。"""
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        if logger:
            logger.info("LINE_CHANNEL_ACCESS_TOKEN 未設定のため LINE 通知はスキップします。")
        return False, "未設定"

    user_id = os.environ.get("LINE_USER_ID", "").strip()
    messages = build_message(text)
    if user_id:
        url, payload = PUSH_URL, {"to": user_id, "messages": messages}
    else:
        url, payload = BROADCAST_URL, {"messages": messages}

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            ok = 200 <= resp.status < 300
            msg = f"LINE通知 送信({resp.status})"
            if logger:
                logger.info(msg)
            return ok, msg
    except Exception as e:
        msg = f"LINE通知 失敗: {e}"
        if logger:
            logger.warn(msg)
        return False, msg
