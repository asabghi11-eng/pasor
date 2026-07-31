"""
Hokm stats, replay & AI analysis — Phase 11.

This module is the piece server.py was already wired for but never shipped:
career stats, per-match replays, a heuristic "AI coach" that reviews a human's
card choices, a stats-based global leaderboard, and an on-demand move
suggestion. Everything here is pure/stateless — server.py owns all the
mutable state (Player.stats, Player.match_history, Room.match_log, etc.) and
just calls into these helpers.

Honest scope note: the "AI analysis" is a heuristic coach, not a real trained
model. It compares each human decision against what the existing bot AI
(hokm_game.ai_choose_card) would have played in the same spot and buckets the
gap into a handful of human-readable categories. It's good enough to point out
patterns ("you're ruffing partner's tricks a lot") but it isn't a full
double-dummy solver — a true optimal-play analyzer would need to search the
remaining cards, which is future work.
"""

import hokm_game as G

# --------------------------------------------------------------- stats -----

def new_stats() -> dict:
    return {
        "matchesPlayed": 0,
        "matchesWon": 0,
        "handsPlayed": 0,
        "handsWon": 0,
        "tricksWon": 0,
        "surWon": 0,          # حاصل از "سور" — بردهای تمام‌و‌کمال (7-0)
        "hakemHands": 0,
        "hakemWins": 0,
        "bestWinStreak": 0,
    }


def _pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 1)


def win_rate(stats: dict) -> float:
    return _pct(stats.get("matchesWon", 0), stats.get("matchesPlayed", 0))


def sur_rate(stats: dict) -> float:
    """Of the hands this player's team WON, what % were a clean 7-0 sweep."""
    return _pct(stats.get("surWon", 0), stats.get("handsWon", 0))


def hakem_win_rate(stats: dict) -> float:
    """Win rate specifically for hands where this player was hakem."""
    return _pct(stats.get("hakemWins", 0), stats.get("hakemHands", 0))


def record_match(stats: dict, match_log: list, seat: str, won: bool, win_streak_after: int) -> dict:
    """Fold one finished match's hand records into a player's running stats.
    match_log is Room.match_log: a list of build_hand_record(...) dicts for
    every hand played in that match."""
    team = G.TEAM[seat]
    stats = dict(stats)  # never mutate the caller's dict in place

    stats["matchesPlayed"] = stats.get("matchesPlayed", 0) + 1
    if won:
        stats["matchesWon"] = stats.get("matchesWon", 0) + 1
    stats["bestWinStreak"] = max(stats.get("bestWinStreak", 0), win_streak_after)

    for hand in match_log:
        stats["handsPlayed"] = stats.get("handsPlayed", 0) + 1
        hand_won = hand.get("winnerTeam") == team
        if hand_won:
            stats["handsWon"] = stats.get("handsWon", 0) + 1
            tricks_won = hand.get("tricksWon", {})
            other_team = "B" if team == "A" else "A"
            if tricks_won.get(team) == 7 and tricks_won.get(other_team, 0) == 0:
                stats["surWon"] = stats.get("surWon", 0) + 1
        stats["tricksWon"] = stats.get("tricksWon", 0) + sum(
            1 for trick in hand.get("tricks", []) if trick.get("team") == team
        )
        if hand.get("hakem") == seat:
            stats["hakemHands"] = stats.get("hakemHands", 0) + 1
            if hand_won:
                stats["hakemWins"] = stats.get("hakemWins", 0) + 1

    return stats


# ------------------------------------------------------------- replay ------

def build_hand_record(hand_number: int, hakem: str, trump: str, tricks_won: dict,
                       winner_team: str, hand_log: list) -> dict:
    """One hand's worth of replay data — called right when a hand ends."""
    return {
        "handNumber": hand_number,
        "hakem": hakem,
        "trump": trump,
        "tricksWon": dict(tricks_won),
        "winnerTeam": winner_team,
        "tricks": list(hand_log),
    }


def build_match_record(match_id: str, ts: float, seat: str, won: bool, rounds_won: dict,
                        match_log: list, analysis: dict) -> dict:
    """One full match, stored on Player.match_history. `hands` is the replay
    payload — match_history_payload() strips it out for the summary list and
    the client fetches it on demand via get_replay."""
    return {
        "matchId": match_id,
        "ts": ts,
        "seat": seat,
        "won": won,
        "roundsWon": dict(rounds_won),
        "hands": match_log,
        "analysis": analysis,
    }


def cap_history(history: list, limit: int = 20) -> list:
    return history[:limit]


def find_match(history: list, match_id: str) -> dict | None:
    return next((m for m in history if m.get("matchId") == match_id), None)


# --------------------------------------------------------- AI analysis -----

_TAG_TIP = {
    "unnecessary_trump": "چند بار حکم رو خرج کردی وقتی خیر همبازی داشت می‌برد — حکم رو برای وقتی نگه دار که واقعاً لازمه.",
    "missed_cheap_win": "جاهایی بود که با یک برگ کوچیک‌تر هم می‌بردی — برگ گرون‌تر رو برای بعد نگه دار.",
    "gave_up_trick": "با اینکه برگ برنده داشتی، دست رو واگذار کردی — حواست به دست‌های نزدیک باشه.",
    "optimal": None,
}


def classify_decision(hand: list, current_trick: list, card: dict, trump: str, seat: str) -> str:
    """Classify a single card play by comparing it to what the bot AI would
    have played in the exact same spot. Called live, right when a human
    plays a card, so the tag can be stashed cheaply (before the hand's state
    is mutated) for the post-match summary."""
    recommended = G.ai_choose_card(hand, current_trick, trump, seat)
    if recommended["suit"] == card["suit"] and recommended["rank"] == card["rank"]:
        return "optimal"

    led_suit = current_trick[0]["card"]["suit"] if current_trick else None
    legal = [c for c in hand if c["suit"] == led_suit] if led_suit else list(hand)
    if not legal:
        legal = list(hand)

    if not current_trick:
        # Leading — nothing to compare against a "winning" bar for, so the
        # only meaningful gap is spending trump to open with.
        if card["suit"] == trump and recommended["suit"] != trump:
            return "unnecessary_trump"
        return "other"

    best = current_trick[0]
    for play in current_trick[1:]:
        if G.is_better(play["card"], best["card"], led_suit, trump):
            best = play
    can_win = [c for c in legal if G.is_better(c, best["card"], led_suit, trump)]
    played_wins = G.is_better(card, best["card"], led_suit, trump)

    if card["suit"] == trump and recommended["suit"] != trump:
        return "unnecessary_trump"
    if can_win and not played_wins:
        return "gave_up_trick"
    if played_wins and can_win and card["rank"] > min(c["rank"] for c in can_win) and card["suit"] == recommended["suit"]:
        return "missed_cheap_win"
    return "other"


def summarize_analysis(decisions: list) -> dict:
    """decisions: list of {"tag": <str>} snapshots collected during the match
    for one human seat. Produces a short heuristic "coach" summary."""
    total = len(decisions)
    tag_counts: dict = {}
    for d in decisions:
        tag = d.get("tag", "other")
        tag_counts[tag] = tag_counts.get(tag, 0) + 1

    optimal = tag_counts.get("optimal", 0)
    optimal_rate = _pct(optimal, total)

    tips = []
    for tag, _count in sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True):
        tip = _TAG_TIP.get(tag)
        if tip:
            tips.append(tip)
        if len(tips) >= 2:
            break
    if not tips and total:
        tips.append("این دست خیلی خوب بازی کردی — همینطوری ادامه بده!")

    return {
        "totalDecisions": total,
        "optimalRate": optimal_rate,
        "tags": tag_counts,
        "tips": tips,
    }


def suggest_move(hand: list, current_trick: list, trump: str, seat: str) -> dict:
    """On-demand move suggestion for a human seat: what would the AI play
    right now, and (briefly) why."""
    card = G.ai_choose_card(hand, current_trick, trump, seat)
    if not current_trick:
        reason = "چون تو شروع‌کننده‌ی دستی، یه برگ کوچیکِ غیرحکم بازی کن تا حکمت برای بعد بمونه."
    else:
        led_suit = current_trick[0]["card"]["suit"]
        if card["suit"] != led_suit and card["suit"] != trump:
            reason = "همخال نداری و نیازی به حکم زدن هم نیست — کوچیک‌ترین برگ بی‌فایده رو دور بریز."
        elif card["suit"] == trump and led_suit != trump:
            reason = "همخال نداری ولی این دست ارزش حکم زدن داره."
        else:
            reason = "این برگ ارزون‌ترین راه برای بردن یا کمک به این دسته."
    return {"card": card, "reason": reason}


# ---------------------------------------------------------- leaderboard ----

def _stats_win_rate(entry: dict) -> float:
    return _pct(entry.get("matchesWon", 0), entry.get("matchesPlayed", 0))


def build_leaderboard(entries: list, limit: int = 20) -> list:
    ranked = sorted(
        entries,
        key=lambda e: (e.get("matchesWon", 0), e.get("matchesPlayed", 0)),
        reverse=True,
    )
    return [
        {**e, "position": i + 1, "winRate": _stats_win_rate(e)}
        for i, e in enumerate(ranked[:limit])
    ]


def leaderboard_position(entries: list, player_id: str) -> dict | None:
    ranked = sorted(
        entries,
        key=lambda e: (e.get("matchesWon", 0), e.get("matchesPlayed", 0)),
        reverse=True,
    )
    for i, e in enumerate(ranked):
        if e.get("playerId") == player_id:
            return {**e, "position": i + 1, "winRate": _stats_win_rate(e)}
    return None
