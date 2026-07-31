"""
Hokm regional servers — Phase 12 (سرورهای منطقه‌ای).

This isn't literally separate physical servers/deployments per region
(that's an infra decision, not application logic) — it's the part of
"regional servers" that actually changes gameplay and can live in this
codebase: each player picks a region, quick-match prefers pairing them
with someone from the *same* region (lower expected latency / same
community), and the world cup (hokm_worldcup.py) runs its qualifiers
region-by-region before a global final.

Pure functions/data only (no I/O, no globals) — server.py owns
Player.region and the MM_QUEUE / MM_QUEUE_JOINED_AT dicts.
"""

DEFAULT_REGION = "ir"

# key -> {lang: label}. Regions chosen to match where a Persian card
# game's community actually is: Iran itself, the wider Middle East,
# Europe, (Central/South) Asia, and the Americas.
REGIONS = [
    {"key": "ir", "fa": "ایران", "en": "Iran", "ar": "إيران", "tr": "İran", "ru": "Иран"},
    {"key": "me", "fa": "خاورمیانه", "en": "Middle East", "ar": "الشرق الأوسط", "tr": "Orta Doğu", "ru": "Ближний Восток"},
    {"key": "eu", "fa": "اروپا", "en": "Europe", "ar": "أوروبا", "tr": "Avrupa", "ru": "Европа"},
    {"key": "as", "fa": "آسیا", "en": "Asia", "ar": "آسيا", "tr": "Asya", "ru": "Азия"},
    {"key": "na", "fa": "آمریکا", "en": "Americas", "ar": "الأمريكتان", "tr": "Amerika", "ru": "Америка"},
]

_VALID = {row["key"] for row in REGIONS}

# How long the head of the matchmaking queue waits for a same-region
# opponent before we pair them with anyone, so small regions never
# get stuck waiting forever.
REGION_MATCH_GRACE_SECONDS = 12.0


def is_valid_region(region) -> bool:
    return isinstance(region, str) and region in _VALID


def normalize_region(region) -> str:
    return region if is_valid_region(region) else DEFAULT_REGION


def region_list(lang: str = "fa") -> list:
    lang = lang if lang in ("fa", "en", "ar", "tr", "ru") else "fa"
    return [{"key": row["key"], "label": row.get(lang, row["fa"])} for row in REGIONS]


def regional_leaderboard(entries: list, region_of: dict, region: str) -> list:
    """entries: any list of dicts that include a 'playerId' key (e.g. the
    global stats leaderboard). Returns only the entries whose player is
    in `region`, order preserved."""
    region = normalize_region(region)
    return [e for e in entries if region_of.get(e.get("playerId")) == region]


def pick_pair(queue: list, region_of: dict, joined_at: dict, now: float):
    """queue: player_ids waiting for a quick match, FIFO order.
    region_of: {player_id: region}. joined_at: {player_id: unix-time
    they joined the queue}.

    Prefers pairing the player who's been waiting longest with someone
    from their own region. If that player has waited past
    REGION_MATCH_GRACE_SECONDS and no same-region opponent is
    available, pairs them with whoever's next instead, so nobody in a
    quiet region waits forever.

    Returns (player_id, player_id) or None if no pair can be made yet.
    """
    for p1 in queue:
        same_region = [
            p2 for p2 in queue
            if p2 != p1 and region_of.get(p2) == region_of.get(p1)
        ]
        if same_region:
            return (p1, same_region[0])

        waited = now - joined_at.get(p1, now)
        if waited >= REGION_MATCH_GRACE_SECONDS:
            others = [p2 for p2 in queue if p2 != p1]
            if others:
                return (p1, others[0])

    return None
