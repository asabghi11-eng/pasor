"""
hokm_minimax.py — real minimax + alpha-beta double-dummy card-play solver.
Phase 15: this replaces the "compare to the simple bot" heuristic that
hokm_stats.py used to call an "AI analysis" with an actual game-tree search.

Honest scope note (same spirit as hokm_stats.py's original note, which this
file is here to resolve): this performs a REAL minimax search with
alpha-beta pruning over the true known cards of all four seats. server.py
is already authoritative for every hand (it deals the cards), so this is
the same principle as a chess engine's "hint" button: the search sees full
information, but only the recommended card is ever surfaced to a player —
never the opponents' hands themselves.

For the tail of a hand (roughly the last 8-9 tricks, once branching has
narrowed), this is an EXACT double-dummy solve — the returned card is
provably optimal given perfect information, not a guess. Early in a hand
(a fresh 13-card hand) the full game tree is bridge-solver-scale, so a node
budget caps the search; once the budget runs out mid-branch, that branch is
scored with a fast non-searching heuristic instead of continuing exactly —
the same "search, then fall back to a static evaluator" design every real
game engine (chess, go, bridge) uses. A result carries `exact: True/False`
so callers can tell honestly which case they got.
"""

import hokm_game as G

TEAM = G.TEAM


def _other_team(team: str) -> str:
    return "B" if team == "A" else "A"


def _legal_cards(hand: list, current_trick: list) -> list:
    if not current_trick:
        return list(hand)
    led_suit = current_trick[0]["card"]["suit"]
    same = [c for c in hand if c["suit"] == led_suit]
    return same if same else list(hand)


def _order_candidates(cards: list, current_trick: list, trump) -> list:
    """Move ordering only — doesn't affect correctness, just how much
    alpha-beta gets to prune. Try the strongest-looking moves first."""
    if not current_trick:
        return sorted(cards, key=lambda c: (c["suit"] == trump, -c["rank"]))
    led_suit = current_trick[0]["card"]["suit"]
    best = current_trick[0]["card"]
    for play in current_trick[1:]:
        if G.is_better(play["card"], best, led_suit, trump):
            best = play["card"]

    def score(c):
        wins = G.is_better(c, best, led_suit, trump)
        return (wins, c["suit"] == trump, -c["rank"] if wins else c["rank"])

    return sorted(cards, key=score, reverse=True)


def _heuristic_eval(hands: dict, trump, tricks_won: dict, root_team: str) -> float:
    """Non-searching estimate, used only once the node budget runs out
    partway through a branch. Weighs each remaining card by rank and by
    whether it's trump, as a rough proxy for future trick-winning power."""
    strength = {"A": 0.0, "B": 0.0}
    for seat, hand in hands.items():
        team = TEAM[seat]
        for c in hand:
            w = 1.0 + (c["rank"] - 7) * 0.12
            if c["suit"] == trump:
                w += 1.5
            strength[team] += max(w, 0.05)

    total_remaining = sum(len(h) for h in hands.values())
    root_current = tricks_won[root_team] - tricks_won[_other_team(root_team)]
    if total_remaining == 0:
        return float(root_current)

    total_strength = strength["A"] + strength["B"] + 1e-9
    root_share = strength[root_team] / total_strength
    projected_swing = (root_share - 0.5) * total_remaining
    return root_current + projected_swing


class _Budget:
    __slots__ = ("nodes", "limit")

    def __init__(self, limit: int):
        self.nodes = 0
        self.limit = limit

    def spend(self) -> bool:
        self.nodes += 1
        return self.nodes <= self.limit


def _search(hands, current_trick, trump, turn_seat, tricks_won, root_team, alpha, beta, budget):
    if tricks_won["A"] >= 7 or tricks_won["B"] >= 7:
        return float(tricks_won[root_team] - tricks_won[_other_team(root_team)])

    if not budget.spend():
        return _heuristic_eval(hands, trump, tricks_won, root_team)

    hand = hands[turn_seat]
    if not hand:
        return float(tricks_won[root_team] - tricks_won[_other_team(root_team)])

    candidates = _order_candidates(_legal_cards(hand, current_trick), current_trick, trump)
    maximizing = TEAM[turn_seat] == root_team
    best_val = float("-inf") if maximizing else float("inf")

    for card in candidates:
        new_hand = [c for c in hand if not (c["suit"] == card["suit"] and c["rank"] == card["rank"])]
        hands[turn_seat] = new_hand
        new_trick = current_trick + [{"seat": turn_seat, "card": card}]

        if len(new_trick) < 4:
            val = _search(hands, new_trick, trump, G.next_seat(turn_seat), tricks_won,
                           root_team, alpha, beta, budget)
        else:
            led_suit = new_trick[0]["card"]["suit"]
            winner_seat = G.resolve_trick_winner(new_trick, led_suit, trump)
            winner_team = TEAM[winner_seat]
            new_tricks_won = dict(tricks_won)
            new_tricks_won[winner_team] += 1
            val = _search(hands, [], trump, winner_seat, new_tricks_won,
                           root_team, alpha, beta, budget)

        hands[turn_seat] = hand  # undo, back to the parent's state

        if maximizing:
            best_val = max(best_val, val)
            alpha = max(alpha, best_val)
        else:
            best_val = min(best_val, val)
            beta = min(beta, best_val)
        if alpha >= beta:
            break

    return best_val


def best_card(hands: dict, current_trick: list, trump, seat: str, tricks_won: dict,
              node_budget: int = 300_000) -> dict:
    """Real entry point. `hands` must be the ACTUAL current hands of all
    four seats (server-side full information) — server.py's room.hands.
    Returns {"card", "score", "exact", "nodesUsed"}. `exact=True` means the
    node budget was never hit on any branch, so `card` is provably optimal;
    `exact=False` means at least one branch was cut off and scored with the
    heuristic, so `card` is the search's best-effort pick, not a guarantee.
    """
    root_team = TEAM[seat]
    hand = hands[seat]
    candidates = _order_candidates(_legal_cards(hand, current_trick), current_trick, trump)
    if len(candidates) == 1:
        return {"card": candidates[0], "score": None, "exact": True, "nodesUsed": 0}

    budget = _Budget(node_budget)
    alpha, beta = float("-inf"), float("inf")
    best_val, chosen = float("-inf"), candidates[0]
    working = {s: list(h) for s, h in hands.items()}

    for card in candidates:
        new_hand = [c for c in hand if not (c["suit"] == card["suit"] and c["rank"] == card["rank"])]
        working[seat] = new_hand
        new_trick = current_trick + [{"seat": seat, "card": card}]

        if len(new_trick) < 4:
            val = _search(working, new_trick, trump, G.next_seat(seat), tricks_won,
                           root_team, alpha, beta, budget)
        else:
            led_suit = new_trick[0]["card"]["suit"]
            winner_seat = G.resolve_trick_winner(new_trick, led_suit, trump)
            winner_team = TEAM[winner_seat]
            new_tricks_won = dict(tricks_won)
            new_tricks_won[winner_team] += 1
            val = _search(working, [], trump, winner_seat, new_tricks_won,
                           root_team, alpha, beta, budget)

        working[seat] = hand

        if val > best_val:
            best_val, chosen = val, card
        alpha = max(alpha, best_val)

    return {
        "card": chosen,
        "score": best_val,
        "exact": budget.nodes < budget.limit,
        "nodesUsed": budget.nodes,
    }
