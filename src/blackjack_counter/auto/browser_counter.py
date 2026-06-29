"""Web ブラックジャックの DOM からカードを自動読取してカウントする。

学習・GPU 不要。Playwright + Chromium があれば今すぐ動く。
カードが DOM 要素として描画されるゲーム（HTML/JS 製）に対応する。
canvas 描画のゲームは ``vision_counter`` を使う。

使い方:
    # このリポジトリの自作ゲームを自動カウント（ブラウザ表示あり）
    python -m blackjack_counter.auto.browser_counter --url file:///abs/path/blackjack.html

    # 任意サイト（カードのセレクタを指定）
    python -m blackjack_counter.auto.browser_counter \\
        --url https://example.com/blackjack \\
        --player-selector "#player-cards .card-rank" \\
        --dealer-selector "#dealer-cards .card-rank"
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time

from blackjack_counter.advisor.advisor import BettingAdvisor
from blackjack_counter.auto.card_diff import RoundTracker
from blackjack_counter.counting.engine import CountEngine
from blackjack_counter.counting.strategies import available_strategies, get_strategy
from blackjack_counter.domain.types import Rank

# ブラウザ内で実行され {player, dealer, remaining} を返す JS。
# 既定は #player-cards / #dealer-cards 配下の表向きカードのランクを読む。
# `deck` 変数が露出していればリシャッフル検知に使う（自作ゲーム向け）。
_DEFAULT_EXTRACTOR = """
(sel) => {
  const read = (s) => Array.from(document.querySelectorAll(s))
      .map(e => (e.textContent || '').trim()).filter(Boolean);
  let remaining = null;
  try { if (typeof deck !== 'undefined' && deck && deck.length != null) remaining = deck.length; }
  catch (e) {}
  return {
    player: read(sel.player),
    dealer: read(sel.dealer),
    remaining: remaining,
  };
}
"""


def _detect_chromium() -> str | None:
    """事前インストールされた Chromium を探す（環境差を吸収）。

    Playwright が既定ブラウザを持っていればそちらを使えばよいので None を返す。
    """
    candidates: list[str] = []
    base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    candidates += glob.glob(os.path.join(base, "chromium-*/chrome-linux/chrome"))
    candidates += glob.glob(os.path.join(base, "chromium-*/chrome-mac/Chromium.app"))
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _normalize(ranks: list[str]) -> list[Rank]:
    """生テキストのランク列を Rank に変換（変換できないものは無視）。"""
    out: list[Rank] = []
    for r in ranks:
        try:
            out.append(Rank.from_input(r))
        except ValueError:
            continue
    return out


def _render(engine: CountEngine, advisor: BettingAdvisor, reshuffled: bool) -> str:
    snap = engine.snapshot()
    advice = advisor.advise(snap)
    tag = "  [リシャッフル検知→リセット]" if reshuffled else ""
    return (
        f"RC={snap.display_running:>4}  TC={snap.display_true:>5}  "
        f"残{snap.remaining_decks:4.1f}デッキ  見{snap.cards_seen:>3}枚  "
        f"| {advice.edge} → {advice.bet_label}{tag}"
    )


def run(
    url: str,
    *,
    strategy_name: str = "hi_lo",
    num_decks: int = 6,
    player_selector: str = "#player-cards .card:not(.hidden-card) .card-rank",
    dealer_selector: str = "#dealer-cards .card:not(.hidden-card) .card-rank",
    headless: bool = False,
    poll_ms: int = 200,
    max_seconds: float | None = None,
    executable_path: str | None = None,
) -> int:
    """ブラウザを開き、カードを自動読取してカウントを表示し続ける。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright が未インストールです。\n"
            "  pip install playwright && playwright install chromium",
            file=sys.stderr,
        )
        return 3

    try:
        strategy = get_strategy(strategy_name)
    except KeyError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2

    engine = CountEngine(strategy, num_decks=num_decks)
    advisor = BettingAdvisor()
    tracker = RoundTracker()
    selectors = {"player": player_selector, "dealer": dealer_selector}

    print(f"対象URL : {url}")
    print(f"方式     : {strategy.name} / {num_decks} デッキ")
    print(f"監視中... カードが配られると自動でカウントします（Ctrl+C で終了）\n")

    started = time.monotonic()
    exe = executable_path or _detect_chromium()
    launch_kwargs: dict = {"headless": headless}
    if exe:
        launch_kwargs["executable_path"] = exe

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page()
        page.goto(url)
        try:
            while True:
                if max_seconds is not None and time.monotonic() - started > max_seconds:
                    break
                try:
                    data = page.evaluate(_DEFAULT_EXTRACTOR, selectors)
                except Exception:
                    # ページ遷移中などは次のポーリングで再試行
                    time.sleep(poll_ms / 1000)
                    continue

                new_ranks, reshuffled = tracker.update(
                    data.get("player", []),
                    data.get("dealer", []),
                    data.get("remaining"),
                )
                if reshuffled:
                    engine.reset()
                for rank in _normalize(new_ranks):
                    engine.add_card(rank)

                if new_ranks or reshuffled:
                    print("\r" + _render(engine, advisor, reshuffled), flush=True)
                time.sleep(poll_ms / 1000)
        except KeyboardInterrupt:
            print("\n終了します。")
        finally:
            browser.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="blackjack-counter-browser",
        description="Web ブラックジャックの DOM からカードを自動読取してカウント",
    )
    parser.add_argument("--url", required=True, help="対象ページの URL（file:// 可）")
    parser.add_argument("--strategy", default="hi_lo",
                        help=f"方式 ({', '.join(available_strategies())})")
    parser.add_argument("--decks", type=int, default=6, help="デッキ数")
    parser.add_argument(
        "--player-selector",
        default="#player-cards .card:not(.hidden-card) .card-rank",
        help="プレイヤーの表向きカードのランクを指す CSS セレクタ",
    )
    parser.add_argument(
        "--dealer-selector",
        default="#dealer-cards .card:not(.hidden-card) .card-rank",
        help="ディーラーの表向きカードのランクを指す CSS セレクタ",
    )
    parser.add_argument("--headless", action="store_true",
                        help="ブラウザを表示しない")
    parser.add_argument("--poll-ms", type=int, default=200,
                        help="ポーリング間隔(ミリ秒)")
    parser.add_argument("--browser-path", default=None,
                        help="Chromium 実行ファイルのパス（省略時は自動検出）")
    args = parser.parse_args(argv)

    return run(
        args.url,
        strategy_name=args.strategy,
        num_decks=args.decks,
        player_selector=args.player_selector,
        dealer_selector=args.dealer_selector,
        headless=args.headless,
        poll_ms=args.poll_ms,
        executable_path=args.browser_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
