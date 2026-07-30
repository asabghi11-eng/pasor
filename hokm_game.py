"""
Hokm game engine — core rules, dealing, and AI helpers used by server.py.

This mirrors the original client-side JS logic (createDeck / shuffle / sortHand /
isBetter / aiPlay) exactly, so the server's authoritative rulings match what the
UI has always shown to players.
"""
import random
from typing import Optional

SUITS = {
    "S": {"symbol": "♠", "name": "پیک", "color": "black"},
    "H": {"symbol": "♥", "name": "دل", "color": "red"},
    "D": {"symbol": "♦", "name": "خشت", "color": "red"},
    "C": {"symbol": "♣", "name": "گشنیز", "color": "black"},
}
SUIT_ORDER = ["S", "H", "D", "C"]
RANK_LABEL = {11: "J", 12: "Q", 13: "K", 14: "A"}

# Turn order around the table. south/north are the two human seats (team A),
# west/east are the bot seats (team B) — matches SEAT_HUMANS/SEAT_BOTS in server.py.
SEATS = ["south", "east", "north", "west"]
TEAM = {"south": "A", "north": "A", "west": "B", "east": "B"}
TARGET_ROUNDS = 7  # hands (rounds) needed to win the match


def next_seat(seat: str) -> str:
    i = SEATS.index(seat)
    return SEATS[(i + 1) % len(SEATS)]


def create_deck() -> list:
    deck = []
    for suit in SUIT_ORDER:
        for rank in range(2, 15):
            deck.append({"suit": suit, "rank": rank})
    return deck


def shuffle(cards: list) -> list:
    cards = list(cards)
    random.shuffle(cards)
    return cards


def sort_hand(cards: list, trump: Optional[str]) -> list:
    order = [trump] + [s for s in SUIT_ORDER if s != trump] if trump else list(SUIT_ORDER)
    return sorted(cards, key=lambda c: (order.index(c["suit"]), -c["rank"]))


def is_better(card: dict, best: dict, led_suit: str, trump: Optional[str]) -> bool:
    c_trump = card["suit"] == trump
    b_trump = best["suit"] == trump
    if c_trump and not b_trump:
        return True
    if not c_trump and b_trump:
        return False
    if c_trump and b_trump:
        return card["rank"] > best["rank"]
    if card["suit"] == led_suit and best["suit"] == led_suit:
        return card["rank"] > best["rank"]
    return False


def is_legal_play(hand: list, current_trick: list, card: dict) -> bool:
    """Must follow the led suit if you're able to."""
    if not current_trick:
        return True
    led_suit = current_trick[0]["card"]["suit"]
    if card["suit"] == led_suit:
        return True
    has_led_suit = any(c["suit"] == led_suit for c in hand)
    return not has_led_suit


def resolve_trick_winner(current_trick: list, led_suit: str, trump: Optional[str]) -> str:
    best = current_trick[0]
    for play in current_trick[1:]:
        if is_better(play["card"], best["card"], led_suit, trump):
            best = play
    return best["seat"]


def ai_choose_trump(hand: list) -> str:
    """Pick the suit the bot holds the most of (ties broken by SUIT_ORDER)."""
    counts = {}
    for c in hand:
        counts[c["suit"]] = counts.get(c["suit"], 0) + 1
    best, best_n = None, -1
    for s in SUIT_ORDER:
        n = counts.get(s, 0)
        if n > best_n:
            best, best_n = s, n
    return best


def ai_choose_card(hand: list, current_trick: list, trump: Optional[str], seat: str) -> dict:
    """Simple-but-sane bot: follow suit if possible, help a winning teammate
    with the lowest card, otherwise win as cheaply as possible, otherwise dump low."""
    led_suit = current_trick[0]["card"]["suit"] if current_trick else None
    legal = [c for c in hand if c["suit"] == led_suit] if led_suit else []
    if not legal:
        legal = list(hand)

    def lowest(cards):
        return min(cards, key=lambda c: c["rank"])

    if not current_trick:
        non_trump = [c for c in legal if c["suit"] != trump]
        return lowest(non_trump if non_trump else legal)

    teammate = next((s for s in SEATS if s != seat and TEAM[s] == TEAM[seat]), None)
    best = current_trick[0]
    for play in current_trick[1:]:
        if is_better(play["card"], best["card"], led_suit, trump):
            best = play
    teammate_winning = best["seat"] == teammate
    can_win = [c for c in legal if is_better(c, best["card"], led_suit, trump)]

    if teammate_winning:
        non_trump = [c for c in legal if c["suit"] != trump]
        return lowest(non_trump if non_trump else legal)
    if can_win:
        return lowest(can_win)
    non_trump = [c for c in legal if c["suit"] != trump]
    return lowest(non_trump if non_trump else legal)
