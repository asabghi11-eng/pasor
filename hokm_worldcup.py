"""
Hokm World Cup — Phase 12 (مسابقات جهانی).

One live global championship per season (see server.py's
CURRENT_WORLD_CUP). Shape, deliberately, mirrors hokm_tournament.py's
points-league-with-cutoffs model, for the same honest reason: matches
are always south+north (partners) vs two bots, so there's no
human-vs-human seat to build a literal 1v1 bracket on. What this module
adds on top of a normal tournament:

  - eligibility gate (Gold rank / rr and above — see MIN_RR_TO_JOIN),
  - a *qualifying* stage run separately inside each region
    (hokm_regions.py) so players first compete against others with
    similar latency/community, then
  - a *finals* stage that pools the top finishers from every region
    into one global bracket, with elimination cuts, ending in a single
    champion for the season.

Pure functions only (no I/O, no globals) — server.py owns the
WorldCup dataclass instance and the Player.world_cup_titles field.
"""

import datetime

MIN_RR_TO_JOIN = 600          # Gold tier and above (see hokm_ranks.TIERS)
MIN_TOTAL_TO_START = 8        # need at least this many registered (across all regions) to begin qualifiers
PROMOTE_PER_REGION = 2        # top N from each region's qualifiers advance to the finals

QUALIFIER_MATCHES_REQUIRED = 3   # matches each qualifier participant plays before their region is "done"
FINALS_ROUND_MATCHES = 3         # matches per finals round before the next elimination cut
FINALS_CUT_FRACTION = 0.5        # bottom half is cut at each finals round

POINTS_PER_WIN = 3
POINTS_PER_LOSS = 1

# (coins, gems) per finishing place in the final standings; anyone
# further down still gets a small participation reward.
PRIZE_TABLE = [(5000, 250), (2500, 120), (1200, 60), (1200, 60)]
PARTICIPATION_REWARD = (150, 5)


def season_id() -> str:
    """Monthly season id, e.g. '2026-07'."""
    today = datetime.date.today()
    return f"{today.year:04d}-{today.month:02d}"


def is_eligible(rr: int) -> bool:
    return rr >= MIN_RR_TO_JOIN


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


def _standings(participants: dict) -> list:
    def key(item):
        _, p = item
        win_rate = p["wins"] / p["matchesPlayed"] if p["matchesPlayed"] else 0
        return (-p["points"], -win_rate, p["matchesPlayed"])

    return sorted(participants.items(), key=key)


def region_standings(bucket: dict) -> list:
    """bucket: {player_id: participant}. Best-first (player_id, participant) list."""
    return _standings(bucket)


def final_standings(finalists: dict) -> list:
    return _standings(finalists)


def total_registered(regions: dict) -> int:
    """regions: {region_key: {player_id: participant}}."""
    return sum(len(bucket) for bucket in regions.values())


def all_regions_done(regions: dict) -> bool:
    """True once every region that has at least 2 participants has had
    each of its (non-eliminated — qualifiers don't eliminate anyone,
    everyone just plays out the round) participants play the required
    number of qualifier matches. Empty/single-player regions can't run
    a qualifier and don't block the rest."""
    active_regions = [bucket for bucket in regions.values() if len(bucket) >= 2]
    if not active_regions:
        return False
    return all(
        all(p["matchesPlayed"] >= QUALIFIER_MATCHES_REQUIRED for p in bucket.values())
        for bucket in active_regions
    )


def promote_region(bucket: dict) -> list:
    """Returns up to PROMOTE_PER_REGION player_ids (best-first) from one
    region's qualifiers to send into the finals."""
    ranked = [pid for pid, _ in region_standings(bucket)]
    return ranked[:PROMOTE_PER_REGION]


def should_run_cut(finalists: dict) -> bool:
    active = [p for p in finalists.values() if not p["eliminated"]]
    # Unlike a normal league (which a host can just stop whenever), the
    # World Cup has to reach a single champion on its own — so, unlike
    # hokm_tournament's knockout cut, we keep cutting all the way down
    # to exactly 2 active players (one more cut there decides the
    # champion) instead of stopping early.
    if len(active) < 2:
        return False
    return all(
        p["matchesPlayed"] > 0 and p["matchesPlayed"] % FINALS_ROUND_MATCHES == 0
        for p in active
    )


def apply_cut(finalists: dict) -> list:
    """Eliminates the bottom FINALS_CUT_FRACTION of active finalists.
    Returns the list of player_ids just eliminated."""
    active_ids = [pid for pid, p in finalists.items() if not p["eliminated"]]
    ordered = [pid for pid, _ in _standings({pid: finalists[pid] for pid in active_ids})]
    cut_count = max(1, int(len(ordered) * FINALS_CUT_FRACTION))
    survivors = ordered[:-cut_count] if cut_count < len(ordered) else ordered[:1]
    eliminated = [pid for pid in ordered if pid not in survivors]
    for pid in eliminated:
        finalists[pid]["eliminated"] = True
    return eliminated


def is_finished(finalists: dict) -> bool:
    active = [p for p in finalists.values() if not p["eliminated"]]
    return len(active) <= 1 and len(finalists) > 1


def prizes_for(ranked_ids: list) -> dict:
    """ranked_ids: player_ids best-first (from final_standings, ids only).
    Returns {player_id: {"coins": int, "gems": int, "place": int}}."""
    result = {}
    for i, pid in enumerate(ranked_ids):
        if i < len(PRIZE_TABLE):
            coins, gems = PRIZE_TABLE[i]
        else:
            coins, gems = PARTICIPATION_REWARD
        result[pid] = {"coins": coins, "gems": gems, "place": i + 1}
    return result


def champion_title(season_id_str: str) -> str:
    return f"قهرمان جام جهانی {season_id_str}"
