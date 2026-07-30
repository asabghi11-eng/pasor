"""
Hokm ranking system — Phase 5

Design: a single integer "RR" (rank rating) per player drives everything else.
- 7 tiers: برنزی, نقره‌ای, طلایی, الماسی, استاد, استاد بزرگ, اسطوره
  (Bronze, Silver, Gold, Diamond, Master, Grand Master, Legend)
- The first 6 tiers are split into 3 divisions of 100 RR each (300 RR/tier).
- اسطوره (Legend) is open-ended — no divisions, ranked purely by RR so a
  future leaderboard (phase 11/12) can sort players within it.
- Win a match: +25 RR. Lose a match: -20 RR. RR never drops below 0.
- Season = 1 calendar month. At the start of a new season every player gets
  a "soft reset": pulled back exactly one tier (never below 0), so climbing
  stays meaningful but nobody loses everything.

This module is pure and stateless — it takes an RR int in, and returns
plain dicts/ints out. server.py owns persistence (currently in-memory).
"""
from datetime import datetime, timezone

TIERS = ["برنزی", "نقره‌ای", "طلایی", "الماسی", "استاد", "استاد بزرگ", "اسطوره"]
TIER_COLORS = {
    "برنزی": "#a5682a",
    "نقره‌ای": "#9aa5b1",
    "طلایی": "#e0b23f",
    "الماسی": "#5ad1e6",
    "استاد": "#b06bf2",
    "استاد بزرگ": "#f25b8b",
    "اسطوره": "#ffd76a",
}

DIVISION_RR = 100                                  # RR needed per division
DIVISIONS_PER_TIER = 3                             # divisions in every tier except Legend
TIER_RR = DIVISION_RR * DIVISIONS_PER_TIER         # 300 RR per tier
LEGEND_START = TIER_RR * (len(TIERS) - 1)          # 1800 — RR where Legend begins

WIN_RR = 25
LOSE_RR = 20

_FA_DIGIT = {"1": "۱", "2": "۲", "3": "۳"}


def _division_label(n: int) -> str:
    return _FA_DIGIT.get(str(n), str(n))


def rank_info(rr: int) -> dict:
    """Turn an RR integer into a full display-ready rank breakdown."""
    rr = max(0, rr)
    if rr >= LEGEND_START:
        tier = TIERS[-1]
        return {
            "rr": rr,
            "tierIndex": len(TIERS) - 1,
            "tier": tier,
            "division": None,
            "label": tier,
            "progress": None,          # Legend has no division bar — just climbing RR
            "color": TIER_COLORS[tier],
        }
    tier_index = min(rr // TIER_RR, len(TIERS) - 2)
    into_tier = rr - tier_index * TIER_RR
    division_index = min(into_tier // DIVISION_RR, DIVISIONS_PER_TIER - 1)  # 0,1,2 (low->high)
    division_number = DIVISIONS_PER_TIER - division_index                  # shown as 3,2,1
    progress = into_tier - division_index * DIVISION_RR                    # 0..99 within division
    tier = TIERS[tier_index]
    return {
        "rr": rr,
        "tierIndex": tier_index,
        "tier": tier,
        "division": division_number,
        "label": f"{tier} {_division_label(division_number)}",
        "progress": progress,
        "color": TIER_COLORS[tier],
    }


def apply_result(rr: int, won: bool) -> dict:
    """Apply a match result to an RR value. Returns before/after + deltas."""
    before = rank_info(rr)
    delta = WIN_RR if won else -LOSE_RR
    new_rr = max(0, rr + delta)
    after = rank_info(new_rr)
    return {
        "rr": new_rr,
        "delta": new_rr - rr,
        "won": won,
        "before": before,
        "after": after,
        "promoted": after["tierIndex"] > before["tierIndex"],
        "demoted": after["tierIndex"] < before["tierIndex"],
    }


def current_season_id() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def season_soft_reset(rr: int) -> int:
    """Pull the player back exactly one tier at the start of a new season."""
    return max(0, rr - TIER_RR)
