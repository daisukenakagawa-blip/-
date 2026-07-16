# -*- coding: utf-8 -*-
"""パチンコ・パチスロ情報スクレイパー

config.json に登録したサイト(RSS / HTML)から記事タイトル・URL・日付を収集し、
CSV / JSON に保存する。robots.txt を確認し、アクセス間隔を空けて巡回する。

使い方:
    python scraper.py                # 全サイトを巡回
    python scraper.py --site 一撃    # 名前に「一撃」を含むサイトだけ
    python scraper.py --limit 10     # 1サイトあたり最大10件
    python scraper.py --keyword ジャグラー  # キーワードを含む記事だけ
"""

import argparse
import csv
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"
DATA_DIR = BASE_DIR / "data"
JST = timezone(timedelta(hours=9))

USER_AGENT = "PachinkoScraper/1.0 (personal research; contact via GitHub)"
REQUEST_INTERVAL_SEC = 3  # 同一ドメインへの最低アクセス間隔
TIMEOUT = 20

_last_access = {}  # domain -> time.time()
_robots_cache = {}  # domain -> RobotFileParser or None


def log(msg):
    print(f"[{datetime.now(JST).strftime('%H:%M:%S')}] {msg}")


def polite_wait(url):
    """同一ドメインへ連続アクセスしないように待機する。"""
    domain = urlparse(url).netloc
    last = _last_access.get(domain)
    if last is not None:
        elapsed = time.time() - last
        if elapsed < REQUEST_INTERVAL_SEC:
            time.sleep(REQUEST_INTERVAL_SEC - elapsed)
    _last_access[domain] = time.time()


def robots_allowed(url):
    """robots.txt で許可されているか確認する。取得できない場合は許可扱い。"""
    parsed = urlparse(url)
    domain = parsed.netloc
    if domain not in _robots_cache:
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"
        rp = RobotFileParser()
        try:
            resp = requests.get(robots_url, timeout=10,
                                headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
                _robots_cache[domain] = rp
            else:
                _robots_cache[domain] = None
        except requests.RequestException:
            _robots_cache[domain] = None
    rp = _robots_cache[domain]
    if rp is None:
        return True
    return rp.can_fetch(USER_AGENT, url)


def fetch(url):
    if not robots_allowed(url):
        log(f"  ✗ robots.txt で禁止されているためスキップ: {url}")
        return None
    polite_wait(url)
    try:
        resp = requests.get(url, timeout=TIMEOUT,
                            headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        return resp
    except requests.RequestException as e:
        log(f"  ✗ 取得失敗: {url} ({e})")
        return None


def strip_html(text):
    return re.sub(r"<[^>]+>", "", text or "").strip()


def parse_rss(content, limit):
    """RSS 2.0 / Atom の両方をパースして記事リストを返す。"""
    items = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        log(f"  ✗ RSSのパースに失敗: {e}")
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}

    # RSS 2.0
    for item in root.iter("item"):
        title = strip_html(item.findtext("title", ""))
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or item.findtext(
            "{http://purl.org/dc/elements/1.1/}date") or "").strip()
        if title and link:
            items.append({"title": title, "url": link, "published": pub})
        if len(items) >= limit:
            return items

    # Atom
    if not items:
        for entry in root.findall("atom:entry", ns):
            title = strip_html(entry.findtext("atom:title", "", ns))
            link_el = entry.find("atom:link[@rel='alternate']", ns)
            if link_el is None:
                link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            pub = (entry.findtext("atom:published", "", ns)
                   or entry.findtext("atom:updated", "", ns)).strip()
            if title and link:
                items.append({"title": title, "url": link, "published": pub})
            if len(items) >= limit:
                break
    return items


def parse_html(content, site, base_url, limit):
    """CSSセレクタ設定に従ってHTMLから記事リストを抽出する。"""
    if BeautifulSoup is None:
        log("  ✗ beautifulsoup4 が未インストールです (pip install -r requirements.txt)")
        return []
    soup = BeautifulSoup(content, "html.parser")
    sel = site.get("selectors", {})
    item_sel = sel.get("item")
    if not item_sel:
        log("  ✗ selectors.item が設定されていません")
        return []

    items = []
    for node in soup.select(item_sel)[:limit * 2]:
        title_el = node.select_one(sel["title"]) if sel.get("title") else node
        link_el = node.select_one(sel["link"]) if sel.get("link") else (
            node if node.name == "a" else node.select_one("a"))
        date_el = node.select_one(sel["date"]) if sel.get("date") else None

        title = title_el.get_text(strip=True) if title_el else ""
        href = link_el.get("href", "") if link_el else ""
        pub = date_el.get_text(strip=True) if date_el else ""
        if title and href:
            items.append({
                "title": title,
                "url": urljoin(base_url, href),
                "published": pub,
            })
        if len(items) >= limit:
            break
    return items


def scrape_site(site, limit):
    name = site["name"]
    url = site["url"]
    log(f"● {name} ({url})")
    resp = fetch(url)
    if resp is None:
        return []

    if site.get("type") == "rss":
        items = parse_rss(resp.content, limit)
    else:
        resp.encoding = resp.apparent_encoding
        items = parse_html(resp.text, site, url, limit)

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    for it in items:
        it["site"] = name
        it["scraped_at"] = now
    log(f"  ✓ {len(items)}件取得")
    return items


def load_existing_urls(csv_path):
    if not csv_path.exists():
        return set()
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        return {row.get("url", "") for row in csv.DictReader(f)}


def save(results, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "articles.csv"
    fieldnames = ["scraped_at", "site", "title", "url", "published"]

    existing = load_existing_urls(csv_path)
    new_rows = [r for r in results if r["url"] not in existing]

    write_header = not csv_path.exists()
    with open(csv_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerows(new_rows)

    json_path = out_dir / f"articles_{datetime.now(JST).strftime('%Y%m%d_%H%M%S')}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    log(f"新規 {len(new_rows)}件 を {csv_path} に追記 (重複 {len(results) - len(new_rows)}件はスキップ)")
    log(f"今回の全結果: {json_path}")


def main():
    parser = argparse.ArgumentParser(description="パチンコ・パチスロ情報スクレイパー")
    parser.add_argument("--site", help="この文字列を名前に含むサイトだけ巡回する")
    parser.add_argument("--limit", type=int, default=20, help="1サイトあたりの最大取得件数")
    parser.add_argument("--keyword", help="タイトルにこの文字列を含む記事だけ保存する")
    parser.add_argument("--out", default=str(DATA_DIR), help="保存先ディレクトリ")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        log(f"設定ファイルがありません: {CONFIG_PATH}")
        sys.exit(1)
    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = json.load(f)

    sites = [s for s in config.get("sites", []) if s.get("enabled", True)]
    if args.site:
        sites = [s for s in sites if args.site in s["name"]]
    if not sites:
        log("対象サイトがありません。config.json を確認してください。")
        sys.exit(1)

    results = []
    for site in sites:
        results.extend(scrape_site(site, args.limit))

    if args.keyword:
        before = len(results)
        results = [r for r in results if args.keyword in r["title"]]
        log(f"キーワード「{args.keyword}」で絞り込み: {before}件 → {len(results)}件")

    if results:
        save(results, Path(args.out))
    else:
        log("取得できた記事がありませんでした。")


if __name__ == "__main__":
    main()
