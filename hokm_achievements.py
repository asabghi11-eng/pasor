"""
hokm_achievements.py — دستاوردها (Achievements) — Phase 13.

چرا این فایل حیاتی بود:
server.py از قبل کد فراخوانی این ماژول رو داشت (`import hokm_achievements
as ACH` + سه‌جا استفاده در achievements_payload/claim_achievement) ولی
خودِ فایل توی پروژه وجود نداشت. یعنی همین الان، بدون این فایل، سرور با
ImportError حتی بالا نمی‌اومد. این ماژول همون شکافیه که server.py
انتظارش رو داشت — دقیقاً مثل اتفاقی که قبلاً برای hokm_auth.py افتاد.

طراحی، عامدانه ساده و صادقانه:
  - هیچ دستاورد جدیدی «ردیابی» نمی‌شه؛ همه‌چی از روی آماری محاسبه میشه که
    سرور از قبل نگه می‌داره (hokm_stats، wallet، رتبه، دوستان، کلن، جام
    جهانی، انبار). یعنی امکان نداره دستاوردها با بقیه‌ی state ناهماهنگ
    بشن، چون منبع مشترک دارن.
  - توابع خالص (pure) هستن، به‌جز claim_achievement که wallet و مجموعه‌ی
    claimed رو (که از server.py پاس داده میشن) مستقیم تغییر می‌ده — دقیقاً
    همون الگویی که hokm_economy.py و hokm_security.py استفاده می‌کنن.
  - claim_achievement فقط سکه/جم رو مستقیم به wallet اضافه می‌کنه؛ اضافه
    کردن XP رو عمداً به server.py واگذار کرده (با E.add_xp)، چون کد
    server.py از قبل دقیقاً همین انتظار رو داشت (نگاه کن به خط
    `xp_result = E.add_xp(..., result["reward"]["xp"])`).
"""

# ------------------------------------------------------------ definitions --
# metric باید دقیقاً یکی از کلیدهای dict خروجیِ server.py::achievement_metrics
# باشه: matches_won, tricks_won, sur_won, hakem_wins, best_streak, level,
# max_rr, friends, clan_joined, world_cup_titles, shop_items.

ACHIEVEMENTS = [
    # ---------------------------------------------------------- بردها ----
    {"id": "win_1", "category": "wins", "metric": "matches_won", "target": 1,
     "nameFa": "اولین قدم", "nameEn": "First Win", "icon": "🏅",
     "reward": {"coins": 50, "xp": 20}},
    {"id": "win_10", "category": "wins", "metric": "matches_won", "target": 10,
     "nameFa": "بازیکن جدی", "nameEn": "Getting Serious", "icon": "🎖️",
     "reward": {"coins": 200, "xp": 60}},
    {"id": "win_50", "category": "wins", "metric": "matches_won", "target": 50,
     "nameFa": "حکم‌باز باتجربه", "nameEn": "Seasoned Player", "icon": "🏆",
     "reward": {"coins": 500, "xp": 150}},
    {"id": "win_200", "category": "wins", "metric": "matches_won", "target": 200,
     "nameFa": "افسانه‌ی میز", "nameEn": "Table Legend", "icon": "👑",
     "reward": {"coins": 1500, "xp": 400, "gems": 10}},

    # -------------------------------------------------------------- خشت‌ها --
    {"id": "tricks_100", "category": "tricks", "metric": "tricks_won", "target": 100,
     "nameFa": "دست گرم", "nameEn": "Warmed Up", "icon": "🃏",
     "reward": {"coins": 100, "xp": 30}},
    {"id": "tricks_1000", "category": "tricks", "metric": "tricks_won", "target": 1000,
     "nameFa": "استاد خشت‌گیری", "nameEn": "Trick Master", "icon": "🂡",
     "reward": {"coins": 400, "xp": 120}},
    {"id": "tricks_5000", "category": "tricks", "metric": "tricks_won", "target": 5000,
     "nameFa": "ماشین خشت‌گیری", "nameEn": "Trick Machine", "icon": "🂮",
     "reward": {"coins": 1200, "xp": 300, "gems": 5}},

    # --------------------------------------------------------------- سور --
    {"id": "sur_1", "category": "sur", "metric": "sur_won", "target": 1,
     "nameFa": "اولین سور", "nameEn": "First Sweep", "icon": "🔥",
     "reward": {"coins": 150, "xp": 40}},
    {"id": "sur_10", "category": "sur", "metric": "sur_won", "target": 10,
     "nameFa": "سوربازِ حرفه‌ای", "nameEn": "Sweep Specialist", "icon": "💥",
     "reward": {"coins": 600, "xp": 180}},
    {"id": "sur_50", "category": "sur", "metric": "sur_won", "target": 50,
     "nameFa": "کابوس حریفان", "nameEn": "Opponents' Nightmare", "icon": "☠️",
     "reward": {"coins": 1800, "xp": 500, "gems": 15}},

    # ------------------------------------------------------------- حاکم ---
    {"id": "hakem_10", "category": "hakem", "metric": "hakem_wins", "target": 10,
     "nameFa": "حاکم منتخب", "nameEn": "Elected Hakem", "icon": "🎩",
     "reward": {"coins": 250, "xp": 70}},
    {"id": "hakem_50", "category": "hakem", "metric": "hakem_wins", "target": 50,
     "nameFa": "حاکم بلامنازع", "nameEn": "Undisputed Hakem", "icon": "🫅",
     "reward": {"coins": 900, "xp": 250, "gems": 8}},

    # -------------------------------------------------------------- برد پیاپی --
    {"id": "streak_3", "category": "streak", "metric": "best_streak", "target": 3,
     "nameFa": "شروع طوفانی", "nameEn": "On a Roll", "icon": "⚡",
     "reward": {"coins": 150, "xp": 50}},
    {"id": "streak_10", "category": "streak", "metric": "best_streak", "target": 10,
     "nameFa": "شکست‌ناپذیر", "nameEn": "Unstoppable", "icon": "🌪️",
     "reward": {"coins": 700, "xp": 220, "gems": 10}},

    # ---------------------------------------------------------------- لول --
    {"id": "level_10", "category": "level", "metric": "level", "target": 10,
     "nameFa": "لول ۱۰", "nameEn": "Level 10", "icon": "⭐",
     "reward": {"coins": 200, "xp": 0}},
    {"id": "level_25", "category": "level", "metric": "level", "target": 25,
     "nameFa": "لول ۲۵", "nameEn": "Level 25", "icon": "🌟",
     "reward": {"coins": 600, "xp": 0, "gems": 12}},

    # -------------------------------------------------------------- رتبه --
    {"id": "rank_silver", "category": "rank", "metric": "max_rr", "target": 300,
     "nameFa": "رسیدن به نقره‌ای", "nameEn": "Reached Silver", "icon": "🥈",
     "reward": {"coins": 150, "xp": 40}},
    {"id": "rank_diamond", "category": "rank", "metric": "max_rr", "target": 900,
     "nameFa": "رسیدن به الماس", "nameEn": "Reached Diamond", "icon": "💎",
     "reward": {"coins": 700, "xp": 200, "gems": 10}},
    {"id": "rank_legend", "category": "rank", "metric": "max_rr", "target": 1800,
     "nameFa": "رسیدن به افسانه", "nameEn": "Reached Legend", "icon": "🌠",
     "reward": {"coins": 2000, "xp": 600, "gems": 25}},

    # -------------------------------------------------------------- اجتماعی --
    {"id": "friends_5", "category": "social", "metric": "friends", "target": 5,
     "nameFa": "دوست‌یاب", "nameEn": "Friend Finder", "icon": "🤝",
     "reward": {"coins": 100, "xp": 30}},
    {"id": "friends_20", "category": "social", "metric": "friends", "target": 20,
     "nameFa": "محبوب جمع", "nameEn": "Popular", "icon": "👥",
     "reward": {"coins": 350, "xp": 100}},
    {"id": "clan_member", "category": "social", "metric": "clan_joined", "target": 1,
     "nameFa": "عضو کلن", "nameEn": "Clan Member", "icon": "🛡️",
     "reward": {"coins": 150, "xp": 40}},

    # ------------------------------------------------------------ جام جهانی --
    {"id": "worldcup_1", "category": "worldcup", "metric": "world_cup_titles", "target": 1,
     "nameFa": "قهرمان جام جهانی", "nameEn": "World Cup Champion", "icon": "🏆",
     "reward": {"coins": 1000, "xp": 300, "gems": 20}},
    {"id": "worldcup_3", "category": "worldcup", "metric": "world_cup_titles", "target": 3,
     "nameFa": "سلسله قهرمانی", "nameEn": "Dynasty", "icon": "🌍",
     "reward": {"coins": 2500, "xp": 700, "gems": 40}},

    # -------------------------------------------------------------- کلکسیون --
    {"id": "collector_5", "category": "collector", "metric": "shop_items", "target": 5,
     "nameFa": "کلکسیونر تازه‌کار", "nameEn": "Budding Collector", "icon": "🎒",
     "reward": {"coins": 100, "xp": 30}},
    {"id": "collector_15", "category": "collector", "metric": "shop_items", "target": 15,
     "nameFa": "کلکسیونر حرفه‌ای", "nameEn": "Serious Collector", "icon": "🧳",
     "reward": {"coins": 400, "xp": 120, "gems": 6}},
]

_BY_ID = {a["id"]: a for a in ACHIEVEMENTS}
assert len(_BY_ID) == len(ACHIEVEMENTS), "duplicate achievement id in ACHIEVEMENTS"


def _reward_of(ach: dict) -> dict:
    r = ach.get("reward") or {}
    return {"coins": r.get("coins", 0), "xp": r.get("xp", 0), "gems": r.get("gems", 0)}


def _status(ach: dict, metrics: dict, claimed: set) -> dict:
    current = int(metrics.get(ach["metric"], 0) or 0)
    target = ach["target"]
    unlocked = current >= target
    return {
        "id": ach["id"],
        "category": ach["category"],
        "nameFa": ach["nameFa"],
        "nameEn": ach["nameEn"],
        "icon": ach["icon"],
        "target": target,
        "progress": min(current, target),
        "current": current,
        "unlocked": unlocked,
        "claimed": ach["id"] in claimed,
        "reward": _reward_of(ach),
    }


def all_achievements(metrics: dict, claimed: set) -> list:
    """Full list with progress/unlocked/claimed flags for the UI, grouped
    in definition order (roughly: wins -> tricks -> sur -> hakem -> streak
    -> level -> rank -> social -> worldcup -> collector)."""
    return [_status(a, metrics, claimed) for a in ACHIEVEMENTS]


def unclaimed_unlocked_count(metrics: dict, claimed: set) -> int:
    """How many achievements are unlocked but not yet claimed — used for
    the notification badge on the achievements button."""
    return sum(
        1 for a in ACHIEVEMENTS
        if a["id"] not in claimed and int(metrics.get(a["metric"], 0) or 0) >= a["target"]
    )


def claim_achievement(wallet: dict, claimed: set, metrics: dict, achievement_id: str) -> dict:
    """Claims one unlocked-but-not-yet-claimed achievement.

    Mutates `wallet` (adds coins/gems in place) and `claimed` (adds the id)
    — both are the caller's real objects (Player.wallet / Player.
    achievements_claimed), same mutate-in-place convention as
    hokm_economy.claim_mission. Does NOT touch wallet["xp"]/["level"];
    server.py applies XP itself via hokm_economy.add_xp using
    reward["xp"], so callers must not double-credit XP.

    Returns {"ok": True, "reward": {...}} or {"ok": False, "error": "..."}.
    """
    ach = _BY_ID.get(achievement_id)
    if not ach:
        return {"ok": False, "error": "دستاورد پیدا نشد"}
    if achievement_id in claimed:
        return {"ok": False, "error": "قبلاً دریافت شده"}
    current = int(metrics.get(ach["metric"], 0) or 0)
    if current < ach["target"]:
        return {"ok": False, "error": "هنوز باز نشده"}

    reward = _reward_of(ach)
    wallet["coins"] = wallet.get("coins", 0) + reward["coins"]
    if reward["gems"]:
        wallet["gems"] = wallet.get("gems", 0) + reward["gems"]
    claimed.add(achievement_id)

    return {"ok": True, "achievementId": achievement_id, "reward": reward}
