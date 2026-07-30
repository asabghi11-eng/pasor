"""
Hokm social systems — Phase 7 completion.

Chat, quick-chat, emoji, friends-list and spectator mode were already
implemented directly in server.py while Phase 6 was being built (see the
"Phase 7 — social" comments there). What was still missing from the
original phase-7 checklist:

  - باشگاه (Clan): create/join/leave a clan, member list, small clan XP
    curve so a clan can "level up" as its members play.
  - هدیه دادن (Gift): send coins to a friend, rate-limited so two
    accounts can't just launder currency back and forth.

Pure functions only (no I/O, no globals) — mirrors the style of
hokm_economy.py / hokm_ranks.py. server.py owns the CLANS dict and the
Player.clan_id / Player.last_gift_date fields, and calls into this module
to validate and compute things.
"""

import datetime
import random
import string

CLAN_NAME_MAX = 24
CLAN_MAX_MEMBERS = 30

GIFT_MIN_COINS = 10
GIFT_MAX_COINS = 200


def today_str() -> str:
    return datetime.date.today().isoformat()


def new_clan_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=5))


def validate_clan_name(name: str) -> str:
    """Returns an error message in Persian, or '' if the name is fine."""
    name = (name or "").strip()
    if not name:
        return "نام باشگاه نمی‌تواند خالی باشد"
    if len(name) > CLAN_NAME_MAX:
        return f"نام باشگاه حداکثر {CLAN_NAME_MAX} کاراکتر است"
    return ""


def can_send_gift(last_gift_date: str, coins_available: int, amount: int) -> str:
    """Returns an error message in Persian, or '' if the gift is allowed.

    Rules: one gift *sent* per player per day, amount must be within the
    configured range, and the sender must actually have the coins.
    """
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return "مقدار هدیه نامعتبر است"
    if amount < GIFT_MIN_COINS or amount > GIFT_MAX_COINS:
        return f"مقدار هدیه باید بین {GIFT_MIN_COINS} تا {GIFT_MAX_COINS} سکه باشد"
    if last_gift_date == today_str():
        return "امروز قبلاً یک هدیه فرستادی — فردا دوباره امتحان کن"
    if coins_available < amount:
        return "سکه کافی برای این هدیه نداری"
    return ""


# --------------------------------------------------------------- clan xp --

def clan_xp_for_level(level: int) -> int:
    return 500 + (level - 1) * 250


def add_clan_xp(xp: int, level: int, amount: int) -> dict:
    """Applies clan-XP gain (e.g. a little bit each time a member wins a
    match), handling multi-level-ups in one go."""
    xp += amount
    levels_gained = 0
    while xp >= clan_xp_for_level(level):
        xp -= clan_xp_for_level(level)
        level += 1
        levels_gained += 1
    return {"xp": xp, "level": level, "levelsGained": levels_gained}


CLAN_XP_PER_MATCH = 5
CLAN_XP_PER_WIN_BONUS = 10
