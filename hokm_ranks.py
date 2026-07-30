"""
Hokm ranking system — Phase 5.

Six-tier ladder (Bronze -> Silver -> Gold -> Diamond -> Master -> Grand
Master -> Legend), Bronze..Diamond split into III/II/I divisions of 100 RR
each, Master+ climb continuously with no divisions. Seasons roll over
monthly with a soft RR reset so nobody starts a new season at zero, but
top players still have room to climb again.

This module is imported by server.py as `hokm_ranks as R` and is required
for the server to start — without it, `import hokm_ranks as R` fails and
the whole app crashes on boot.
"""

import datetime

# ---------------------------------------------------------------- tiers ---

# (name_fa, name_en, icon, rr_floor) — rr_floor is where the tier begins.
# Bronze/Silver/Gold/Diamond are divided into 3 bands of 100 RR (III, II, I).
# Master/Grand Master are single continuous bands. Legend has no ceiling.
TIERS = [
    {"key": "bronze", "fa": "برنز", "icon": "🥉", "floor": 0, "band": 100, "divisions": 3},
    {"key": "silver", "fa": "نقره‌ای", "icon": "🥈", "floor": 300, "band": 100, "divisions": 3},
    {"key": "gold", "fa": "طلایی", "icon": "🥇", "floor": 600, "band": 100, "divisions": 3},
    {"key": "diamond", "fa": "الماس", "icon": "💎", "floor": 900, "band": 100, "divisions": 3},
    {"key": "master", "fa": "استاد", "icon": "🏆", "floor": 1200, "band": 300, "divisions": 1},
    {"key": "grandmaster", "fa": "استاد بزرگ", "icon": "👑", "floor": 1500, "band": 300, "divisions": 1},
    {"key": "legend", "fa": "افسانه", "icon": "🌟", "floor": 1800, "band": None, "divisions": 1},
]

DIVISION_LABEL = {3: "III", 2: "II", 1: "I"}  # division 3 = lowest, 1 = highest (about to promote)

WIN_RR = 25
LOSE_RR = -20
STREAK_BONUS_STEP = 3     # extra RR per consecutive win beyond the first, capped below
STREAK_BONUS_CAP = 15


def _tier_at(rr: int) -> dict:
    rr = max(0, rr)
    current = TIERS[0]
    for tier in TIERS:
        if rr >= tier["floor"]:
            current = tier
        else:
            break
    return current


def rank_info(rr: int) -> dict:
    """Full display info for a given RR value."""
    rr = max(0, int(rr))
    tier = _tier_at(rr)
    into_tier = rr - tier["floor"]

    if tier["band"] is None:
        # Legend — uncapped, no divisions, no "next" threshold.
        return {
            "tier": tier["key"],
            "tierName": tier["fa"],
            "icon": tier["icon"],
            "division": None,
            "label": tier["fa"],
            "rr": rr,
            "rrIntoDivision": into_tier,
            "rrForNext": None,
            "progressPct": 100,
        }

    divisions = tier["divisions"]
    band = tier["band"]
    div_index = min(into_tier // band, divisions - 1)  # 0-based from bottom
    division_number = divisions - div_index            # e.g. 3 -> 2 -> 1
    rr_into_division = into_tier - div_index * band
    rr_for_next = band - rr_into_division
    label = tier["fa"] if divisions == 1 else f"{tier['fa']} {DIVISION_LABEL.get(division_number, '')}"

    return {
        "tier": tier["key"],
        "tierName": tier["fa"],
        "icon": tier["icon"],
        "division": division_number if divisions > 1 else None,
        "label": label,
        "rr": rr,
        "rrIntoDivision": rr_into_division,
        "rrForNext": rr_for_next,
        "progressPct": round(100 * rr_into_division / band),
    }


def apply_result(rr: int, won: bool, win_streak: int = 0) -> dict:
    """Compute the new RR after a match and report what changed.

    win_streak: consecutive wins *before* this match (0 if this is the
    first win of a new streak or the player just lost/hasn't played).
    """
    before = rank_info(rr)

    if won:
        bonus = min(STREAK_BONUS_CAP, win_streak * STREAK_BONUS_STEP)
        delta = WIN_RR + bonus
    else:
        delta = LOSE_RR
        bonus = 0

    new_rr = max(0, rr + delta)
    after = rank_info(new_rr)

    return {
        "rr": new_rr,
        "delta": delta,
        "streakBonus": bonus,
        "before": before,
        "after": after,
        "promoted": after["tier"] != before["tier"] and new_rr > rr,
        "demoted": after["tier"] != before["tier"] and new_rr < rr,
    }


# --------------------------------------------------------------- season ---

def current_season_id() -> str:
    """One season per calendar month, e.g. '2026-07'."""
    now = datetime.datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def season_soft_reset(rr: int) -> int:
    """Compress RR toward the middle of Gold (650) by 35% at season start,
    so high-ranked players keep most of their standing but still have
    climbing to do, and low-ranked players get a small boost back up."""
    rr = max(0, int(rr))
    anchor = 650
    new_rr = round(rr * 0.65 + anchor * 0.35)
    return max(0, min(rr, new_rr) if rr > anchor else new_rr)
