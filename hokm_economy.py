"""
Hokm game economy — Phase 6.

Coins + gems wallet, XP/level curve, per-match rewards with a win-streak
bonus, three rotating daily missions, a static shop catalog, a once-a-day
free lucky wheel, and gem-bought prize boxes.

Pure functions only (no I/O, no globals) so server.py can own persistence —
mirrors the style of hokm_ranks.py. Everything here operates on plain
dicts so it's trivial to store on the Player dataclass and serialize over
the websocket.
"""

import datetime
import random

# ------------------------------------------------------------------ xp ---

def xp_for_level(level: int) -> int:
    """XP required to go from `level` to `level + 1`. Grows so leveling
    slows down a bit at higher levels, but never feels like a wall."""
    return 100 + (level - 1) * 40


def add_xp(xp: int, level: int, amount: int) -> dict:
    """Apply XP gain, handling multi-level-ups in one go."""
    xp += amount
    levels_gained = 0
    while xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
        levels_gained += 1
    return {"xp": xp, "level": level, "levelsGained": levels_gained}


# -------------------------------------------------------------- wallet ---

def new_wallet() -> dict:
    return {"coins": 300, "gems": 20, "xp": 0, "level": 1}


# ------------------------------------------------------------- rewards ---

def match_reward(won: bool, win_streak: int = 0) -> dict:
    """Coins/gems/XP earned at the end of a match. win_streak is the
    player's consecutive-win count *including* this win (0 if lost)."""
    if won:
        coins = 60 + min(win_streak, 5) * 10
        xp = 35
        gems = 2 if win_streak and win_streak % 3 == 0 else 0
    else:
        coins = 20
        xp = 12
        gems = 0
    return {"coins": coins, "gems": gems, "xp": xp}


# ------------------------------------------------------------- missions --

MISSION_POOL = [
    {"id": "win_1", "fa": "۱ بازی را ببر", "target": 1, "metric": "wins", "coins": 50, "xp": 20},
    {"id": "win_3", "fa": "۳ بازی را ببر", "target": 3, "metric": "wins", "coins": 150, "xp": 60},
    {"id": "play_3", "fa": "۳ بازی انجام بده", "target": 3, "metric": "played", "coins": 80, "xp": 30},
    {"id": "play_5", "fa": "۵ بازی انجام بده", "target": 5, "metric": "played", "coins": 130, "xp": 45},
    {"id": "tricks_20", "fa": "۲۰ دست (trick) ببر", "target": 20, "metric": "tricks", "coins": 100, "xp": 40},
    {"id": "hakem_2", "fa": "۲ بار حاکم شو و برنده شو", "target": 2, "metric": "hakem_wins", "coins": 120, "xp": 50},
    {"id": "sur_1", "fa": "یک بار «هفت‌سور» ثبت کن (۷-۰)", "target": 1, "metric": "sur", "coins": 200, "xp": 80},
]


def generate_daily_missions(date_str: str, seed_extra: str = "") -> list:
    """Deterministic-per-day pick of 3 missions so a client refresh
    doesn't hand out a different set. `date_str` should be YYYY-MM-DD."""
    rng = random.Random(f"{date_str}:{seed_extra}")
    picks = rng.sample(MISSION_POOL, k=3)
    return [
        {
            "id": m["id"],
            "title": m["fa"],
            "target": m["target"],
            "metric": m["metric"],
            "progress": 0,
            "claimed": False,
            "rewardCoins": m["coins"],
            "rewardXp": m["xp"],
        }
        for m in picks
    ]


def today_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def bump_mission_progress(missions: list, metric: str, amount: int = 1) -> list:
    for m in missions:
        if m["metric"] == metric and not m["claimed"]:
            m["progress"] = min(m["target"], m["progress"] + amount)
    return missions


def claim_mission(wallet: dict, missions: list, mission_id: str) -> dict:
    m = next((x for x in missions if x["id"] == mission_id), None)
    if not m:
        return {"ok": False, "error": "ماموریت پیدا نشد"}
    if m["claimed"]:
        return {"ok": False, "error": "قبلاً دریافت شده"}
    if m["progress"] < m["target"]:
        return {"ok": False, "error": "هنوز کامل نشده"}
    m["claimed"] = True
    wallet["coins"] += m["rewardCoins"]
    xp_result = add_xp(wallet["xp"], wallet["level"], m["rewardXp"])
    wallet.update(xp_result)
    return {"ok": True, "reward": {"coins": m["rewardCoins"], "xp": m["rewardXp"]}}


# ----------------------------------------------------------------- shop --

SHOP_ITEMS = [
    {"id": "skin_royal", "name": "پوسته سلطنتی", "category": "skin", "price": 800, "currency": "coins"},
    {"id": "skin_neon", "name": "پوسته نئون", "category": "skin", "price": 25, "currency": "gems"},
    {"id": "skin_gold", "name": "پوسته طلایی", "category": "skin", "price": 60, "currency": "gems"},
    {"id": "table_cafe", "name": "میز کافه", "category": "table", "price": 500, "currency": "coins"},
    {"id": "table_marble", "name": "میز مرمر", "category": "table", "price": 35, "currency": "gems"},
    {"id": "cardback_dragon", "name": "پشت کارت اژدها", "category": "cardback", "price": 900, "currency": "coins"},
    {"id": "avatar_frame_gold", "name": "قاب پروفایل طلایی", "category": "frame", "price": 40, "currency": "gems"},
]


def buy_item(wallet: dict, inventory: set, item_id: str) -> dict:
    item = next((x for x in SHOP_ITEMS if x["id"] == item_id), None)
    if not item:
        return {"ok": False, "error": "آیتم پیدا نشد"}
    if item_id in inventory:
        return {"ok": False, "error": "قبلاً خریداری شده"}
    currency = item["currency"]
    if wallet.get(currency, 0) < item["price"]:
        return {"ok": False, "error": "موجودی کافی نیست"}
    wallet[currency] -= item["price"]
    inventory.add(item_id)
    return {"ok": True, "item": item}


# ---------------------------------------------------------- lucky wheel --

# (label, kind, amount, weight) — weight controls odds, higher = more common.
WHEEL_PRIZES = [
    ("۵۰ سکه", "coins", 50, 30),
    ("۱۲۰ سکه", "coins", 120, 22),
    ("۲۵۰ سکه", "coins", 250, 12),
    ("۵ جم", "gems", 5, 18),
    ("۱۵ جم", "gems", 15, 8),
    ("۳۰ جم", "gems", 30, 3),
    ("۵۰۰ سکه (جکپات)", "coins", 500, 2),
    ("۶۰ جم (جکپات)", "gems", 60, 1),
]


def spin_wheel(wallet: dict, last_spin_date: str) -> dict:
    today = today_str()
    if last_spin_date == today:
        return {"ok": False, "error": "امروز قبلاً چرخوندی، فردا دوباره بیا"}
    labels, kinds, amounts, weights = zip(*WHEEL_PRIZES)
    idx = random.choices(range(len(WHEEL_PRIZES)), weights=weights, k=1)[0]
    label, kind, amount, _ = WHEEL_PRIZES[idx]
    wallet[kind] = wallet.get(kind, 0) + amount
    return {"ok": True, "prizeIndex": idx, "label": label, "kind": kind, "amount": amount, "lastSpinDate": today}


# ---------------------------------------------------------- prize boxes --

BOX_TYPES = {
    "bronze": {"cost": 10, "currency": "gems", "coin_range": (80, 200), "gem_chance": 0.1, "gem_range": (3, 8)},
    "silver": {"cost": 25, "currency": "gems", "coin_range": (200, 450), "gem_chance": 0.25, "gem_range": (5, 15)},
    "gold": {"cost": 60, "currency": "gems", "coin_range": (450, 1000), "gem_chance": 0.5, "gem_range": (10, 30)},
}


def open_box(wallet: dict, box_type: str) -> dict:
    box = BOX_TYPES.get(box_type)
    if not box:
        return {"ok": False, "error": "نوع جعبه نامعتبره"}
    if wallet.get(box["currency"], 0) < box["cost"]:
        return {"ok": False, "error": "موجودی کافی نیست"}
    wallet[box["currency"]] -= box["cost"]
    coins = random.randint(*box["coin_range"])
    wallet["coins"] += coins
    reward = {"coins": coins}
    if random.random() < box["gem_chance"]:
        gems = random.randint(*box["gem_range"])
        wallet["gems"] += gems
        reward["gems"] = gems
    return {"ok": True, "reward": reward}
