"""
Hokm competitive tournaments — Phase 8.

Honest note on why this isn't a classic 1v1 bracket:
in the current match model (see server.py), the two real players in a
match are always *partners* (team A: south+north) playing co-operatively
against two bots (team B: west+east) — there is no human-vs-human seat
yet. So a head-to-head elimination bracket ("player A vs player B, loser
is out") isn't something the game engine can run today.

Phase 8 is implemented instead as a **points league with knockout
cutoffs**, which delivers everything on the phase-8 checklist with the
match model we actually have:

  - تورنمنت / لیگ: players register, then each of their normal ranked
    matches (quick match or private room) counts toward the tournament
    while it's running.
  - حذفی: in "knockout" mode, the bottom slice of the standings is
    eliminated at the end of every round; only the survivors continue
    into the next one.
  - جدول: live standings/leaderboard, sorted by tournament points.
  - جایزه: coins/gems prize pool paid out to the top finishers when the
    tournament ends.

When human-vs-human seating lands, this module's standings/prize logic
still applies unchanged — only how a "match" is produced would change.

Pure functions only (no I/O, no globals) — server.py owns the
TOURNAMENTS dict and the Player.active_tournament field.
"""

import datetime
import math

POINTS_PER_WIN = 3
POINTS_PER_LOSS = 1        # small consolation point just for finishing a match
ROUND_MATCHES = 3          # how many matches make up one "round" of a knockout tournament
KNOCKOUT_CUT_FRACTION = 0.5  # bottom half is eliminated at each round cutoff

SIZES = (4, 8, 16, 32)
MODES = ("league", "knockout")

# prize pool (coins, gems) per finishing place, scaled by tournament size.
# index 0 = 1st place, 1 = 2nd place, etc. Anyone below this list gets
# only a small participation reward.
PRIZE_TABLE = {
    4: [(300, 15), (150, 5)],
    8: [(600, 30), (300, 10), (150, 5), (150, 5)],
    16: [(1200, 60), (600, 25), (300, 10), (300, 10)],
    32: [(2500, 120), (1200, 50), (600, 20), (600, 20)],
}
PARTICIPATION_REWARD = (40, 0)


def today_str() -> str:
    return datetime.date.today().isoformat()


def validate_new_tournament(name: str, size: int, mode: str) -> str:
    name = (name or "").strip()
    if not name:
        return "نام تورنمنت نمی‌تواند خالی باشد"
    if len(name) > 32:
        return "نام تورنمنت حداکثر ۳۲ کاراکتر است"
    if size not in SIZES:
        return f"ظرفیت تورنمنت باید یکی از {SIZES} باشد"
    if mode not in MODES:
        return "نوع تورنمنت نامعتبر است"
    return ""


def new_participant() -> dict:
    return {"points": 0, "wins": 0, "losses": 0, "matchesPlayed": 0, "eliminated": False}


def record_match(participant: dict, won: bool) -> dict:
    """Mutates and returns the participant dict after one reported match."""
    participant["matchesPlayed"] += 1
    if won:
        participant["wins"] += 1
        participant["points"] += POINTS_PER_WIN
    else:
        participant["losses"] += 1
        participant["points"] += POINTS_PER_LOSS
    return participant


def standings(participants: dict) -> list:
    """participants: {player_id: participant_dict}. Returns a list of
    (player_id, participant_dict) sorted best-first: points desc, then
    win rate desc, then fewer matches played (efficiency) first."""
    def key(item):
        _, p = item
        win_rate = p["wins"] / p["matchesPlayed"] if p["matchesPlayed"] else 0
        return (-p["points"], -win_rate, p["matchesPlayed"])

    return sorted(participants.items(), key=key)


def should_run_knockout_cut(participants: dict) -> bool:
    """True once every *active* participant has played a full round's
    worth of matches — time to cut the bottom half."""
    active = [p for p in participants.values() if not p["eliminated"]]
    if len(active) <= 2:
        return False
    return all(p["matchesPlayed"] > 0 and p["matchesPlayed"] % ROUND_MATCHES == 0 for p in active)


def apply_knockout_cut(participants: dict) -> list:
    """Eliminates the bottom KNOCKOUT_CUT_FRACTION of active players.
    Returns the list of player_ids just eliminated."""
    active_ids = [pid for pid, p in participants.items() if not p["eliminated"]]
    ordered = [pid for pid, _ in standings({pid: participants[pid] for pid in active_ids})]
    cut_count = max(1, math.floor(len(ordered) * KNOCKOUT_CUT_FRACTION))
    survivors = ordered[:-cut_count] if cut_count < len(ordered) else ordered[:1]
    eliminated = [pid for pid in ordered if pid not in survivors]
    for pid in eliminated:
        participants[pid]["eliminated"] = True
    return eliminated


def is_finished(participants: dict, mode: str) -> bool:
    active = [p for p in participants.values() if not p["eliminated"]]
    if mode == "knockout":
        return len(active) <= 1 and len(participants) > 1
    return False  # league tournaments end when the host/timer ends them, not automatically


def prizes_for(size: int, ranked_ids: list) -> dict:
    """ranked_ids: player_ids best-first (from `standings`, ids only).
    Returns {player_id: {"coins": int, "gems": int, "place": int}}."""
    table = PRIZE_TABLE.get(size, PRIZE_TABLE[4])
    result = {}
    for i, pid in enumerate(ranked_ids):
        if i < len(table):
            coins, gems = table[i]
        else:
            coins, gems = PARTICIPATION_REWARD
        result[pid] = {"coins": coins, "gems": gems, "place": i + 1}
    return result
