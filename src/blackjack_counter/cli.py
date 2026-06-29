"""対話型カードカウンター（ターミナルで今すぐ使える）。

カードが出るたびにキーを押すと、running/true count とベット助言を表示する。

使い方:
    python -m blackjack_counter            # 既定: Hi-Lo, 6 デッキ
    python -m blackjack_counter --strategy ko --decks 8

入力キー:
    2-9          そのランク
    0 または t   10
    j q k a      J / Q / K / A
    u            直前を取り消し (undo)
    r            リセット (シャッフル)
    h            ヘルプ
    s            現在の状態を再表示
    quit / exit  終了
"""

from __future__ import annotations

import argparse
import sys

from blackjack_counter.advisor.advisor import BettingAdvisor
from blackjack_counter.counting.engine import CountEngine
from blackjack_counter.counting.strategies import available_strategies, get_strategy
from blackjack_counter.domain.types import Rank

# ANSI カラー（端末が対応していれば色付け）
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _color_for_tc(tc: float) -> str:
    if tc >= 2:
        return _GREEN
    if tc <= -1:
        return _RED
    return _YELLOW


def _render(engine: CountEngine, advisor: BettingAdvisor) -> str:
    snap = engine.snapshot()
    advice = advisor.advise(snap)
    color = _color_for_tc(snap.true_count)

    lines = [
        "",
        f"  {_BOLD}方式{_RESET}: {snap.strategy}   "
        f"{_DIM}見たカード: {snap.cards_seen} 枚   "
        f"残り {snap.remaining_decks:.1f} デッキ   "
        f"消化 {snap.penetration * 100:.0f}%{_RESET}",
        f"  {_BOLD}Running Count{_RESET}: {snap.display_running}",
        f"  {_BOLD}True Count{_RESET}   : {color}{snap.display_true}{_RESET}",
        f"  {_BOLD}判定{_RESET}: {color}{advice.edge}{_RESET}  "
        f"→ 推奨ベット: {_CYAN}{advice.bet_label}{_RESET}",
        f"  {_DIM}{advice.detail}{_RESET}",
        "",
    ]
    return "\n".join(lines)


def _print_help() -> None:
    print(__doc__)


def run_interactive(strategy_name: str, num_decks: int) -> int:
    """対話ループを実行する。終了コードを返す。"""
    try:
        strategy = get_strategy(strategy_name)
    except KeyError as exc:
        print(f"エラー: {exc}", file=sys.stderr)
        return 2

    engine = CountEngine(strategy, num_decks=num_decks)
    advisor = BettingAdvisor()

    print(f"{_BOLD}♠ ブラックジャック カードカウンター ♠{_RESET}")
    print(f"{_DIM}方式={strategy.name} / デッキ数={num_decks}  "
          f"（'h' でヘルプ, 'quit' で終了）{_RESET}")
    print(_render(engine, advisor))

    while True:
        try:
            raw = input("card> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了します。")
            return 0

        if not raw:
            continue

        cmd = raw.lower()
        if cmd in ("quit", "exit", "q"):
            print("終了します。")
            return 0
        if cmd == "h":
            _print_help()
            continue
        if cmd == "s":
            print(_render(engine, advisor))
            continue
        if cmd == "r":
            engine.reset()
            print(f"{_YELLOW}リセットしました（シャッフル）。{_RESET}")
            print(_render(engine, advisor))
            continue
        if cmd == "u":
            removed = engine.undo()
            if removed is None:
                print(f"{_DIM}取り消すカードがありません。{_RESET}")
            else:
                print(f"{_DIM}取り消し: {removed.value}{_RESET}")
            print(_render(engine, advisor))
            continue

        # 複数カードをまとめて入力できる（例: "k 5 a"）
        tokens = raw.split()
        added: list[str] = []
        ok = True
        for tok in tokens:
            try:
                rank: Rank = Rank.from_input(tok)
            except ValueError:
                print(f"{_RED}不明な入力: {tok!r}（'h' でヘルプ）{_RESET}")
                ok = False
                break
            engine.add_card(rank)
            added.append(rank.value)
        if ok and added:
            print(f"{_DIM}追加: {' '.join(added)}{_RESET}")
        print(_render(engine, advisor))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="blackjack-counter",
        description="ブラックジャックの対話型カードカウンター",
    )
    parser.add_argument(
        "--strategy",
        default="hi_lo",
        help=f"カウント方式 ({', '.join(available_strategies())})",
    )
    parser.add_argument(
        "--decks", type=int, default=6, help="デッキ数 (1-8)"
    )
    args = parser.parse_args(argv)

    if not 1 <= args.decks <= 8:
        parser.error("--decks は 1〜8 で指定してください")

    return run_interactive(args.strategy, args.decks)


if __name__ == "__main__":
    raise SystemExit(main())
