"""
Hokm game monetization — Phase 10.

Rewarded ads (coins for watching, capped per day), a VIP subscription
(coin/XP multiplier on match rewards + a once-a-day coin bonus), gem IAP
packs, and a 30-tier seasonal battle pass with free + premium tracks.

Pure functions only (no I/O, no globals) — same style as hokm_economy.py
and hokm_ranks.py. Everything here operates on plain dicts/sets that
server.py owns and persists on the Player dataclass.

HONEST NOTE ON PAYMENTS: `apply_vip_purchase` and `grant_gem_pack` do not
charge real money — they just apply the effect. In this MVP, server.py
calls them directly off a client websocket message ({"type":"buy_vip",...}
/ {"type":"buy_gem_pack",...}), which is fine for testing the UI/UX but is
NOT safe to ship: any client could send that message for free. Before a
real launch, these two calls must move behind a verified payment-gateway
callback (Zarinpal / Bazaar / Google Play Billing / App Store server
notifications) — the gateway confirms money actually changed hands, and
*that* server-to-server callback is what should invoke these functions,
never the game client directly.
"""

import datetime
import time

# ------------------------------------------------------------------ vip --

VIP_PLANS = [
    {"id": "vip_week", "fa": "VIP هفتگی", "days": 7, "priceToman": 149000, "priceUSD": 2.99},
    {"id": "vip_month", "fa": "VIP ماهانه", "days": 30, "priceToman": 399000, "priceUSD": 6.99},
    {"id": "vip_season", "fa": "VIP فصلی (۳ ماهه)", "days": 90, "priceToman": 899000, "priceUSD": 14.99},
]

VIP_DAILY_BONUS_COINS = 150
VIP_COIN_MULTIPLIER = 1.25
VIP_XP_MULTIPLIER = 1.15


def today_str() -> str:
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")


def is_vip(vip_until: float) -> bool:
    return vip_until > time.time()


def vip_seconds_left(vip_until: float) -> int:
    return max(0, int(vip_until - time.time()))


def apply_reward_multiplier(reward: dict, vip_until: float) -> dict:
    """Boosts a match_reward()-shaped dict (coins/gems/xp) for VIP members.
    Returns a new dict — doesn't mutate the one passed in."""
    boosted = dict(reward)
    if is_vip(vip_until):
        boosted["coins"] = round(boosted.get("coins", 0) * VIP_COIN_MULTIPLIER)
        boosted["xp"] = round(boosted.get("xp", 0) * VIP_XP_MULTIPLIER)
    return boosted


def apply_vip_purchase(vip_until: float, plan_id: str) -> dict:
    plan = next((x for x in VIP_PLANS if x["id"] == plan_id), None)
    if not plan:
        return {"ok": False, "error": "پلن VIP پیدا نشد"}
    base = max(vip_until, time.time())
    new_until = base + plan["days"] * 86400
    return {"ok": True, "vipUntil": new_until, "plan": plan}


def claim_vip_daily_bonus(wallet: dict, vip_until: float, vip_last_daily_claim: str) -> dict:
    if not is_vip(vip_until):
        return {"ok": False, "error": "این جایزه فقط برای اعضای VIP است"}
    today = today_str()
    if vip_last_daily_claim == today:
        return {"ok": False, "error": "امروز قبلاً این جایزه رو گرفتی"}
    wallet["coins"] = wallet.get("coins", 0) + VIP_DAILY_BONUS_COINS
    return {"ok": True, "reward": {"coins": VIP_DAILY_BONUS_COINS}, "claimDate": today}


# ------------------------------------------------------------------- ads --

AD_MAX_PER_DAY = 5
AD_REWARD_COINS = 40


def watch_ad(wallet: dict, ads_watched_today: int, ads_date: str) -> dict:
    today = today_str()
    watched = ads_watched_today if ads_date == today else 0
    if watched >= AD_MAX_PER_DAY:
        return {"ok": False, "error": "سقف تماشای تبلیغ امروز تمام شده، فردا دوباره بیا"}
    wallet["coins"] = wallet.get("coins", 0) + AD_REWARD_COINS
    watched += 1
    return {
        "ok": True,
        "reward": {"coins": AD_REWARD_COINS},
        "adsWatchedToday": watched,
        "adsDate": today,
    }


# -------------------------------------------------------------- gem IAP --

GEM_PACKS = [
    {"id": "gems_small", "gems": 80, "bonus": 0, "priceToman": 99000, "priceUSD": 1.99},
    {"id": "gems_medium", "gems": 500, "bonus": 50, "priceToman": 399000, "priceUSD": 6.99},
    {"id": "gems_large", "gems": 1200, "bonus": 200, "priceToman": 799000, "priceUSD": 13.99},
    {"id": "gems_mega", "gems": 2600, "bonus": 600, "priceToman": 1499000, "priceUSD": 24.99},
]


def grant_gem_pack(wallet: dict, pack_id: str) -> dict:
    pack = next((x for x in GEM_PACKS if x["id"] == pack_id), None)
    if not pack:
        return {"ok": False, "error": "پک جم پیدا نشد"}
    granted = pack["gems"] + pack.get("bonus", 0)
    wallet["gems"] = wallet.get("gems", 0) + granted
    return {"ok": True, "gemsGranted": granted, "pack": pack}


# ------------------------------------------------------------ battle pass --

BP_XP_PER_TIER = 120
BP_MAX_TIER = 30
BP_PREMIUM_PRICE_GEMS = 250

# Cosmetic ids granted at the 3 milestone premium tiers. These just need to
# match ids the shop/inventory UI knows how to render as "special item".
_BP_MILESTONE_ITEMS = {10: "bp_season_cardback", 20: "bp_season_tableskin", 30: "bp_season_avatarframe"}


def bp_season_id() -> str:
    """One battle-pass season per calendar month — same cadence as the
    ranked ladder's season (hokm_ranks.current_season_id), so both reset
    together. Kept as an independent function (rather than importing
    hokm_ranks) since the two are conceptually separate tracks that just
    happen to share a calendar."""
    now = datetime.datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}"


def bp_tier_from_xp(bp_xp: int) -> int:
    return min(bp_xp // BP_XP_PER_TIER, BP_MAX_TIER)


def battle_pass_tiers() -> list:
    """Static reward table for all 30 tiers. Free track is modest coins
    (+ a gem trickle every 5th tier); premium track is richer coins/gems
    and lands a cosmetic item at tiers 10/20/30."""
    tiers = []
    for t in range(1, BP_MAX_TIER + 1):
        free_reward = {"coins": 40 + t * 8}
        if t % 5 == 0:
            free_reward["gems"] = 5 + (t // 5) * 2

        premium_reward = {"coins": 60 + t * 14, "gems": 4 + t}
        if t in _BP_MILESTONE_ITEMS:
            premium_reward = {"coins": 60 + t * 14, "itemId": _BP_MILESTONE_ITEMS[t]}

        tiers.append({"tier": t, "freeReward": free_reward, "premiumReward": premium_reward})
    return tiers


def buy_battle_pass_premium(wallet: dict, bp_premium: bool) -> dict:
    if bp_premium:
        return {"ok": False, "error": "پس پریمیوم رو قبلاً خریدی"}
    if wallet.get("gems", 0) < BP_PREMIUM_PRICE_GEMS:
        return {"ok": False, "error": "جم کافی نیست"}
    wallet["gems"] -= BP_PREMIUM_PRICE_GEMS
    return {"ok": True}


def claim_bp_reward(
    wallet: dict,
    inventory: set,
    bp_xp: int,
    bp_premium: bool,
    bp_claimed_free: set,
    bp_claimed_premium: set,
    tier,
    track,
) -> dict:
    if track not in ("free", "premium"):
        return {"ok": False, "error": "مسیر نامعتبره"}
    if not isinstance(tier, int) or tier < 1 or tier > BP_MAX_TIER:
        return {"ok": False, "error": "مرحله نامعتبره"}
    if bp_tier_from_xp(bp_xp) < tier:
        return {"ok": False, "error": "هنوز به این مرحله نرسیدی"}
    if track == "premium" and not bp_premium:
        return {"ok": False, "error": "برای این جایزه باید پس پریمیوم رو بخری"}

    claimed = bp_claimed_premium if track == "premium" else bp_claimed_free
    if tier in claimed:
        return {"ok": False, "error": "قبلاً این جایزه رو دریافت کردی"}

    tier_info = next(x for x in battle_pass_tiers() if x["tier"] == tier)
    reward = tier_info["premiumReward"] if track == "premium" else tier_info["freeReward"]

    if reward.get("coins"):
        wallet["coins"] = wallet.get("coins", 0) + reward["coins"]
    if reward.get("gems"):
        wallet["gems"] = wallet.get("gems", 0) + reward["gems"]
    if reward.get("itemId"):
        inventory.add(reward["itemId"])

    claimed.add(tier)
    return {"ok": True, "reward": reward}
