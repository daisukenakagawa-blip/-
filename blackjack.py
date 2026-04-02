#!/usr/bin/env python3
"""ブラックジャックゲーム"""

import random


SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def create_deck(num_decks=1):
    """デッキを作成してシャッフルする"""
    deck = [(rank, suit) for suit in SUITS for rank in RANKS] * num_decks
    random.shuffle(deck)
    return deck


def card_value(rank):
    """カードの数値を返す（Aは11として扱い、後で調整）"""
    if rank in ("J", "Q", "K"):
        return 10
    if rank == "A":
        return 11
    return int(rank)


def hand_value(hand):
    """手札の合計値を計算する（Aは必要に応じて1として扱う）"""
    total = sum(card_value(rank) for rank, _ in hand)
    aces = sum(1 for rank, _ in hand if rank == "A")
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


def format_card(card):
    """カードを表示用文字列にする"""
    rank, suit = card
    return f"[{rank}{suit}]"


def format_hand(hand):
    """手札を表示用文字列にする"""
    return " ".join(format_card(c) for c in hand)


def display_table(player_hand, dealer_hand, hide_dealer=True):
    """テーブルの状態を表示する"""
    print()
    if hide_dealer:
        shown = format_card(dealer_hand[0])
        print(f"  ディーラー: {shown} [??]  (見えている値: {card_value(dealer_hand[0][0])})")
    else:
        print(f"  ディーラー: {format_hand(dealer_hand)}  (合計: {hand_value(dealer_hand)})")
    print(f"  あなた:     {format_hand(player_hand)}  (合計: {hand_value(player_hand)})")
    print()


def play_round(deck, chips):
    """1ラウンドをプレイする。残りチップ数を返す。"""
    # ベット
    while True:
        try:
            bet = int(input(f"  チップ: {chips}  ベット額を入力 (1-{chips}): "))
            if 1 <= bet <= chips:
                break
            print("  無効な額です。")
        except ValueError:
            print("  数字を入力してください。")

    # デッキ補充チェック
    if len(deck) < 10:
        deck.clear()
        deck.extend(create_deck())

    # 初期配布
    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    display_table(player_hand, dealer_hand)

    # ナチュラルブラックジャック判定
    player_bj = hand_value(player_hand) == 21
    dealer_bj = hand_value(dealer_hand) == 21

    if player_bj or dealer_bj:
        display_table(player_hand, dealer_hand, hide_dealer=False)
        if player_bj and dealer_bj:
            print("  両者ブラックジャック！ 引き分け。")
            return chips
        if player_bj:
            winnings = int(bet * 1.5)
            print(f"  ブラックジャック！ +{winnings} チップ獲得！")
            return chips + winnings
        print("  ディーラーがブラックジャック… 負けです。")
        return chips - bet

    # プレイヤーのターン
    while True:
        action = input("  [H]ヒット / [S]スタンド: ").strip().upper()
        if action in ("H", "HIT", "ヒット"):
            player_hand.append(deck.pop())
            display_table(player_hand, dealer_hand)
            if hand_value(player_hand) > 21:
                print("  バスト！ 負けです。")
                return chips - bet
        elif action in ("S", "STAND", "スタンド"):
            break
        else:
            print("  H または S を入力してください。")

    # ディーラーのターン
    display_table(player_hand, dealer_hand, hide_dealer=False)
    while hand_value(dealer_hand) < 17:
        dealer_hand.append(deck.pop())
        display_table(player_hand, dealer_hand, hide_dealer=False)

    # 結果判定
    player_total = hand_value(player_hand)
    dealer_total = hand_value(dealer_hand)

    if dealer_total > 21:
        print(f"  ディーラーがバスト！ +{bet} チップ獲得！")
        return chips + bet
    if player_total > dealer_total:
        print(f"  勝ち！ +{bet} チップ獲得！")
        return chips + bet
    if player_total < dealer_total:
        print("  負け…")
        return chips - bet
    print("  引き分け。")
    return chips


def main():
    print("=" * 40)
    print("     ♠ ブラックジャック ♠")
    print("=" * 40)

    chips = 100
    deck = create_deck()

    while chips > 0:
        print("-" * 40)
        chips = play_round(deck, chips)

        if chips <= 0:
            print("\n  チップがなくなりました… ゲームオーバー！")
            break

        again = input("  続けますか？ [Y/N]: ").strip().upper()
        if again in ("N", "NO", "いいえ"):
            break

    print(f"\n  最終チップ: {chips}")
    print("  お疲れ様でした！\n")


if __name__ == "__main__":
    main()
