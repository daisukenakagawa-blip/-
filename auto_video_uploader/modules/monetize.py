"""説明欄への収益リンク自動挿入。

YouTube の収益化条件(登録者数など)を満たす前でも、説明欄のアフィリエイト
リンクや自分の商品・LINE 登録などへの導線から収益を発生させるための仕組み。

リンクの登録方法(どちらでも可。両方あれば links.txt が優先):
  1. auto_video_uploader/links.txt に 1 行 1 件で書く
       ラベル|https://example.com/xxx
       https://example.com/yyy          ← ラベル省略も可
  2. 環境変数 MONETIZE_LINKS に同じ書式で複数行書く

挿入例:
    ▼おすすめ・お得情報
    ・オンラインカジノ入門はこちら → https://...
    ・LINE で狙い台配信中 → https://...
    ※上記にはアフィリエイトリンク(PR)を含む場合があります。

日本の景品表示法(ステマ規制・2023年10月施行)対応のため、リンクを挿入する
場合は PR 表記を必ず付ける。表記文言は MONETIZE_DISCLOSURE で変更できる。
"""

import config
from modules.logger import get_logger


def _parse_lines(text: str) -> list:
    """"ラベル|URL" 形式の複数行テキストを (ラベル, URL) のリストにする。"""
    links = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            label, _, url = line.partition("|")
            label, url = label.strip(), url.strip()
        else:
            label, url = "", line
        if not url.lower().startswith(("http://", "https://")):
            get_logger().warning("収益リンクとして解釈できない行をスキップ: %s", line)
            continue
        links.append((label, url))
    return links


def load_links() -> list:
    """links.txt → 環境変数 MONETIZE_LINKS の順で収益リンクを読み込む。"""
    if config.MONETIZE_LINKS_FILE.exists():
        text = config.MONETIZE_LINKS_FILE.read_text(encoding="utf-8-sig")
        links = _parse_lines(text)
        if links:
            return links
    return _parse_lines(config.MONETIZE_LINKS)


def build_block() -> str:
    """説明欄に挿入するリンクブロックを組み立てる。リンク未設定なら空文字。"""
    links = load_links()
    if not links:
        return ""
    lines = [config.MONETIZE_HEADER]
    for label, url in links:
        lines.append(f"・{label} → {url}" if label else f"・{url}")
    if config.MONETIZE_DISCLOSURE:
        lines.append(config.MONETIZE_DISCLOSURE)
    return "\n".join(lines)


def inject(description: str) -> str:
    """説明文に収益リンクブロックを挿入する。

    ハッシュタグ行(#で始まる最後の行)は説明欄の末尾に残したいので、
    その手前にブロックを差し込む。リンク未設定なら何もしない。
    """
    block = build_block()
    if not block:
        return description
    lines = (description or "").rstrip().split("\n")
    # 末尾のハッシュタグ行を探す(script_generator が最後に付けている)
    if lines and lines[-1].lstrip().startswith("#"):
        body, tail = lines[:-1], lines[-1:]
    else:
        body, tail = lines, []
    parts = ["\n".join(body).rstrip(), block]
    if tail:
        parts.append("\n".join(tail))
    get_logger().info("収益リンクを説明欄に挿入しました (%d 件)", len(load_links()))
    return "\n\n".join(p for p in parts if p)
