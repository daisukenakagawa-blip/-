"""自作 blackjack.html に対する自動カウントの統合テスト。

Playwright と Chromium が利用できない環境では自動スキップする。
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

GAME = ROOT / "blackjack.html"

playwright = pytest.importorskip("playwright.sync_api")

from blackjack_counter.auto.browser_counter import (  # noqa: E402
    _DEFAULT_EXTRACTOR,
    _detect_chromium,
    _normalize,
)
from blackjack_counter.auto.card_diff import RoundTracker  # noqa: E402
from blackjack_counter.counting.engine import CountEngine  # noqa: E402
from blackjack_counter.counting.strategies import HiLo  # noqa: E402
from blackjack_counter.domain.types import Rank  # noqa: E402


def _hilo_sum(ranks: list[str]) -> int:
    s = HiLo()
    return int(sum(s.value(Rank.from_input(r)) for r in ranks))


@pytest.mark.skipif(not GAME.exists(), reason="blackjack.html が無い")
def test_auto_count_matches_revealed_cards():
    from playwright.sync_api import sync_playwright

    exe = _detect_chromium()
    sel = {
        "player": "#player-cards .card:not(.hidden-card) .card-rank",
        "dealer": "#dealer-cards .card:not(.hidden-card) .card-rank",
    }
    engine = CountEngine(HiLo(), num_decks=1)
    tracker = RoundTracker()
    revealed: list[str] = []

    with sync_playwright() as p:
        kwargs = {"headless": True}
        if exe:
            kwargs["executable_path"] = exe
        try:
            browser = p.chromium.launch(**kwargs)
        except Exception as e:  # ブラウザ起動不可ならスキップ
            pytest.skip(f"Chromium を起動できない: {e}")
        page = browser.new_page()
        page.goto(f"file://{GAME}")

        def poll():
            data = page.evaluate(_DEFAULT_EXTRACTOR, sel)
            new, reshuffled = tracker.update(
                data["player"], data["dealer"], data.get("remaining")
            )
            if reshuffled:
                engine.reset()
                revealed.clear()
            for r in _normalize(new):
                engine.add_card(r)
            revealed.extend(new)

        # 数ラウンド自動プレイ
        for _ in range(3):
            page.click("#btn-deal")
            page.wait_for_timeout(150)
            poll()
            page.click("#btn-stand")
            page.wait_for_timeout(400)
            poll()
            # 次ラウンドへ
            try:
                page.click("#btn-next", timeout=1000)
            except Exception:
                pass
            page.wait_for_timeout(150)
        browser.close()

    # 自動でカードを読み取れている
    assert engine.cards_seen >= 4
    # Running count は公開カードの Hi-Lo 合計に一致（リシャッフルが無い限り）
    assert engine.running_count == _hilo_sum(revealed)
