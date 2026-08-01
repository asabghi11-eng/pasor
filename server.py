"""
Hokm real backend — MVP (Phase 4 networking + Phase 5 ranks + Phase 6 economy)

- Guest login (name only, no password) — Google login can be layered on later.
- Quick match: pairs 2 real players as partners (south + north), fills
  west/east with bots so a match can start immediately.
- Private room: host gets a 6-char code, friend joins with it. Same
  south/north + bot-west/east layout.
- Real WebSocket gameplay: server is authoritative for dealing, trump
  selection, legal-play checks, trick resolution and scoring.
- Ping: client sends {type:"ping", ts}, server echoes {type:"pong", ts}.
- Reconnect: client stores its session_token; on drop, reconnect with
  {type:"reconnect", session_token}. If it's your turn while you're
  disconnected, after a grace period the bot plays for you so the match
  isn't stuck — control returns to you the moment you reconnect.
- Ranks (Phase 5): RR ladder Bronze..Legend, monthly season soft-reset.
- Economy (Phase 6): coins/gems/XP wallet, 3 daily missions, shop,
  once-a-day lucky wheel, gem-bought prize boxes.
- Monetization (Phase 10): rewarded ads, VIP subscription (coin/XP
  boost + daily bonus), gem IAP packs, and a 30-tier seasonal battle
  pass with free + premium tracks. See hokm_monetization.py's docstring
  for the honest note on where a real payment gateway still needs to
  plug in.
- Stats, replay & AI analysis (Phase 11): every trick/hand is recorded
  during play; at match end each human gets a frozen replay + a
  heuristic "coach" summary of their card choices, folded into running
  career stats. Plus a live global leaderboard and an on-demand move
  suggestion. See hokm_stats.py's docstring for scope notes.

Run locally:
    pip install -r requirements.txt --break-system-packages
    uvicorn server:app --reload --reload-exclude "*.db" --port 8000

(The --reload-exclude matters: every login writes to hokm.db, which
sits in the same directory --reload watches. Without excluding it,
that write itself looks like a code change to the watcher, so it
restarts the server mid-login — killing the websocket right as you
log in, with nothing that looks like an error in the console.)

Then open http://localhost:8000 in a browser (the server serves the
game page itself — don't double-click hokm-phase4-online.html
directly; some browsers block WebSocket connections from a page
opened via file://, which breaks login with no visible error).
"""

import asyncio
import datetime
import json
import os
import random
import string
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import hokm_game as G
import hokm_ranks as R
import hokm_economy as E
import hokm_social as S
import hokm_tournament as T
import hokm_security as SEC
import hokm_monetization as M
import hokm_stats as ST
import hokm_i18n as I18N
import hokm_regions as REG
import hokm_worldcup as WC
import hokm_storage as DB
import hokm_realtime as RT
import hokm_auth as AUTH
import hokm_payments as PAY
import hokm_achievements as ACH

app = FastAPI()
_STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _load_persisted_players():
    DB.init_db()
    for pid, token, data in DB.load_all_players():
        try:
            p = row_to_player(data)
        except TypeError:
            continue  # a saved shape from an older version of Player — skip rather than crash startup
        PLAYERS[pid] = p
        SESSION_TO_PLAYER[token] = pid
        if p.google_id:
            GOOGLE_TO_PLAYER[p.google_id] = pid
    for rid, data in DB.load_all_rooms():
        try:
            room = row_to_room(data)
        except TypeError:
            continue  # a saved shape from an older version of Room — skip rather than crash startup
        ROOMS[rid] = room
        if room.code:
            CODE_TO_ROOM[room.code] = rid
    asyncio.create_task(autosave_loop())

    # Multi-instance (opt-in via REDIS_URL — see hokm_realtime.py docstring):
    # distributed room lock + cross-instance live-state push. A no-op,
    # and every call below a no-op, when REDIS_URL isn't set.
    await RT.init()
    if RT.is_enabled():
        RT.set_refresh_hook(_refresh_room_from_db)
        await RT.start_listener(_on_remote_room_update)


@app.on_event("shutdown")
async def _flush_persisted_players():
    for p in list(PLAYERS.values()):
        try:
            save_player(p)
        except Exception:
            pass
    for room in list(ROOMS.values()):
        try:
            save_room_state(room)
        except Exception:
            pass
    DB.close()
    await RT.close()


GRACE_SECONDS = float(os.environ.get("HOKM_GRACE_SECONDS", 20))          # how long we wait for a disconnected human before a bot covers their turn
BOT_THINK_SECONDS = float(os.environ.get("HOKM_BOT_THINK_SECONDS", 1.1))  # cosmetic delay so bot moves don't feel instant
TRICK_RESOLVE_DELAY = float(os.environ.get("HOKM_TRICK_RESOLVE_DELAY", 1.3))  # time the "who won the trick" highlight stays up

SEAT_HUMANS = ["south", "north"]                 # kept as a safe default for module-level field factories only
SEAT_BOTS = {"south": "نیلوفر", "north": "سارا", "west": "امیر", "east": "رضا"}  # bot display names by seat
SEAT_FILL_ORDER = ["south", "north", "west", "east"]  # order real players are seated in when a match starts
QUICK_MATCH_BOT_FILL_SECONDS = float(os.environ.get("HOKM_QUICK_MATCH_BOT_FILL_SECONDS", 12))  # how long we wait for more humans before padding the room with bots


# ---------------------------------------------------------------- players --

@dataclass
class Player:
    id: str
    session_token: str
    name: str
    ws: Optional[WebSocket] = None
    connected: bool = True
    room_id: Optional[str] = None
    seat: Optional[str] = None

    # Phase 5 — ranking
    rr: int = 0
    season_id: str = field(default_factory=R.current_season_id)
    win_streak: int = 0

    # Phase 6 — economy
    wallet: dict = field(default_factory=E.new_wallet)
    inventory: set = field(default_factory=set)
    missions: list = field(default_factory=list)
    missions_date: str = ""
    last_wheel_spin: str = ""

    # Phase 7 — social (in-memory only; see note at bottom of file)
    friends: set = field(default_factory=set)
    clan_id: Optional[str] = None
    last_gift_date: str = ""

    # Phase 8 — tournaments
    active_tournament: Optional[str] = None

    # Phase 9 — security
    action_log: list = field(default_factory=list)     # recent action unix-times, for rate limiting
    mute_until: float = 0.0                             # chat muted until this unix-time (auto-mute from reports)
    reports_received: list = field(default_factory=list)  # [{"reporterId","reason","ts"}]

    # Phase 10 — monetization
    vip_until: float = 0.0                              # unix-time VIP expires, 0 = never bought
    vip_last_daily_claim: str = ""
    ads_watched_today: int = 0
    ads_date: str = ""
    bp_season_id: str = field(default_factory=M.bp_season_id)
    bp_xp: int = 0
    bp_premium: bool = False
    bp_claimed_free: set = field(default_factory=set)
    bp_claimed_premium: set = field(default_factory=set)

    # Phase 11 — stats, replays & AI post-match analysis
    stats: dict = field(default_factory=ST.new_stats)
    match_history: list = field(default_factory=list)  # capped list of {matchId, ts, won, roundsWon, seatNames, hands, analysis}

    # Phase 12 — language, region & world cup
    language: str = I18N.DEFAULT_LANG
    region: str = REG.DEFAULT_REGION
    world_cup_titles: list = field(default_factory=list)  # champion badges from past seasons

    # Real Google login (replaces the old fake loginGoogle() placeholder).
    # None for guests; set once a player links/logs in with Google, so the
    # SAME progress comes back even on a brand-new device/browser where
    # localStorage's session_token isn't available.
    google_id: Optional[str] = None
    email: Optional[str] = None

    # Phase 13 — achievements. Progress itself is derived on the fly from
    # stats/wallet/friends/etc (see achievement_metrics() below); the only
    # new state we actually need to keep is which ones were claimed, plus
    # the highest RR ever reached (rr itself can drop after a loss, so it
    # can't answer "did this player ever hit Gold").
    achievements_claimed: set = field(default_factory=set)
    max_rr: int = 0


@dataclass
class Clan:
    id: str
    name: str
    code: str
    owner_id: str
    members: set = field(default_factory=set)
    xp: int = 0
    level: int = 1


@dataclass
class Tournament:
    id: str
    name: str
    size: int
    mode: str                       # "league" | "knockout"
    owner_id: str
    status: str = "registration"    # registration | active | finished
    participants: dict = field(default_factory=dict)   # player_id -> hokm_tournament participant dict
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


@dataclass
class WorldCup:
    """Phase 12 — one live global championship at a time."""
    season_id: str
    status: str = "registration"     # registration | qualifiers | finals | finished
    regions: dict = field(default_factory=dict)    # region_key -> {player_id: participant}
    finalists: dict = field(default_factory=dict)  # player_id -> participant (finals bracket)
    champion_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())


# Fields NOT persisted: ws/connected (runtime-only, always reset on
# reload — a fresh process has no live socket) and action_log (a rolling
# rate-limit window, meaningless after a restart). room_id/seat ARE
# persisted now that Room state is saved too (see save_room_state below):
# on reconnect, PLAYERS[pid].room_id routes the player straight back into
# their in-progress match instead of always dropping them at the lobby.
_PERSISTED_SET_FIELDS = ("inventory", "friends", "bp_claimed_free", "bp_claimed_premium", "achievements_claimed")
_PERSISTED_SKIP_FIELDS = {"ws", "connected", "action_log"}


def player_to_row(p: "Player") -> dict:
    data = {}
    for f in dataclasses_fields_cache():
        if f in _PERSISTED_SKIP_FIELDS:
            continue
        v = getattr(p, f)
        data[f] = sorted(v) if f in _PERSISTED_SET_FIELDS else v
    return data


def row_to_player(data: dict) -> "Player":
    data = dict(data)  # don't mutate the caller's dict
    for f in _PERSISTED_SET_FIELDS:
        if f in data:
            data[f] = set(data[f])
    return Player(ws=None, connected=False, **data)


def save_player(p: "Player"):
    DB.save_player(p.id, p.session_token, player_to_row(p))


AUTOSAVE_SECONDS = float(os.environ.get("HOKM_AUTOSAVE_SECONDS", 20))


async def autosave_loop():
    while True:
        await asyncio.sleep(AUTOSAVE_SECONDS)
        for p in list(PLAYERS.values()):
            try:
                save_player(p)
            except Exception:
                pass  # never let a persistence hiccup take the game server down


def dataclasses_fields_cache():
    import dataclasses
    return [f.name for f in dataclasses.fields(Player)]


PLAYERS: dict[str, Player] = {}
SESSION_TO_PLAYER: dict[str, str] = {}
GOOGLE_TO_PLAYER: dict[str, str] = {}      # google "sub" id -> player_id, so the same Google account
                                            # always resumes the same progress, even on a new device
PENDING_PAYMENTS: dict[str, dict] = {}     # zarinpal authority -> {"player_id","kind","item_id","amount_toman","created_at"}
MM_QUEUE: list[str] = []          # player_ids waiting for quick match
MM_QUEUE_JOINED_AT: dict[str, float] = {}  # player_id -> unix-time they joined MM_QUEUE (Phase 12 regional pairing)
ROOMS: dict[str, "Room"] = {}
CODE_TO_ROOM: dict[str, str] = {}
CLANS: dict[str, Clan] = {}
CLAN_CODE_TO_ID: dict[str, str] = {}
TOURNAMENTS: dict[str, Tournament] = {}
RECONNECT_FAILS: dict[str, list] = {}   # client ip -> recent failed-reconnect unix-times
CURRENT_WORLD_CUP = WorldCup(season_id=WC.season_id())


# ------------------------------------------------------------------ room ---

@dataclass
class Room:
    id: str
    seats: dict                    # seat -> player_id | "bot"
    code: Optional[str] = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    turn_token: int = 0

    # game state
    phase: str = "waiting"          # waiting | idle | choosing-trump | playing | hand-end | match-end
    hands: dict = field(default_factory=lambda: {s: [] for s in G.SEATS})
    deck: list = field(default_factory=list)
    hakem: Optional[str] = None
    trump: Optional[str] = None
    current_trick: list = field(default_factory=list)
    trick_leader: Optional[str] = None
    turn: Optional[str] = None
    tricks_won: dict = field(default_factory=lambda: {"A": 0, "B": 0})
    rounds_won: dict = field(default_factory=lambda: {"A": 0, "B": 0})
    trick_winner_seat: Optional[str] = None
    hand_winner_team: Optional[str] = None
    match_winner_team: Optional[str] = None
    match_id: str = ""

    # Phase 7 — social
    spectators: set = field(default_factory=set)  # player_ids watching, no seat
    chat_log: list = field(default_factory=list)   # last 50 chat/emoji events

    # Phase 11 — replay & AI-analysis recording for the match in progress
    hand_log: list = field(default_factory=list)     # tricks played so far in the current hand
    match_log: list = field(default_factory=list)    # finished hands so far in the current match (replay data)
    decisions: dict = field(default_factory=lambda: {s: [] for s in SEAT_HUMANS})  # human seat -> per-card snapshots for AI analysis
    analysis_tasks: list = field(default_factory=list)  # Phase 15 — in-flight background minimax classify_decision() tasks, awaited before summarize_analysis()

    # Phase 14 — voice chat. Who currently has their mic "on" in this room.
    # The server never sees/touches actual audio — it only relays WebRTC
    # signaling (SDP offers/answers, ICE candidates) between the peers
    # in this set so they can open a direct (mesh) peer-to-peer audio
    # connection with each other. See voice_join/voice_leave/webrtc_*
    # in handle_message() and the "Phase 14" note near the top of
    # voice-panel.js for the full picture.
    voice_participants: set = field(default_factory=set)

    def seat_of(self, player_id: str) -> Optional[str]:
        for seat, pid in self.seats.items():
            if pid == player_id:
                return seat
        return None

    def human_seat_ids(self):
        return {s: pid for s, pid in self.seats.items() if pid != "bot"}

    def human_seats(self):
        return list(self.human_seat_ids().keys())

    def partner_of(self, seat: Optional[str]) -> Optional[str]:
        """The other human seat on the same team, if any (real 2v2-capable —
        works whether that teammate is south/north OR west/east)."""
        if not seat:
            return None
        team = G.TEAM.get(seat)
        for s in self.human_seats():
            if s != seat and G.TEAM.get(s) == team:
                return s
        return None

    def is_seat_connected(self, seat: str) -> bool:
        pid = self.seats.get(seat)
        if pid is None or pid == "bot":
            return False
        p = PLAYERS.get(pid)
        return bool(p and p.connected)

    def name_of(self, seat: str) -> str:
        pid = self.seats.get(seat)
        if pid == "bot":
            return SEAT_BOTS[seat]
        p = PLAYERS.get(pid) if pid else None
        return (p.name if p else None) or {"south": "شما", "north": "سارا"}.get(seat, seat)

    def bump_token(self) -> int:
        self.turn_token += 1
        return self.turn_token


# Fields persisted for a live room: everything needed to reconstruct the
# match exactly as it was (seats, deal, trump, trick-in-progress, score,
# chat/replay logs). Fields NOT persisted, because they're either
# runtime-only synchronization primitives or session state that's safe
# (even correct) to drop across a restart:
#   - lock: an asyncio.Lock can't be serialized and wouldn't mean anything
#     in a fresh process anyway — a new one is created when the Room is
#     rebuilt.
#   - analysis_tasks: in-flight background minimax analysis. Safe to lose;
#     it isn't gameplay state, just a nice-to-have summary computed after
#     the fact.
#   - voice_participants: WebRTC signaling state tied to the sockets that
#     no longer exist after a restart. Reconnecting players simply toggle
#     their mic back on.
_ROOM_PERSISTED_FIELDS = (
    "id", "seats", "code", "phase", "hands", "deck", "hakem", "trump",
    "current_trick", "trick_leader", "turn", "tricks_won", "rounds_won",
    "trick_winner_seat", "hand_winner_team", "match_winner_team", "match_id",
    "spectators", "chat_log", "hand_log", "match_log", "decisions",
)


def room_to_row(room: "Room") -> dict:
    data = {}
    for f in _ROOM_PERSISTED_FIELDS:
        v = getattr(room, f)
        data[f] = sorted(v) if isinstance(v, set) else v
    return data


def row_to_room(data: dict) -> "Room":
    data = dict(data)  # don't mutate the caller's dict
    if "spectators" in data:
        data["spectators"] = set(data["spectators"])
    return Room(**data)


def save_room_state(room: "Room"):
    try:
        DB.save_room(room.id, room_to_row(room), code=room.code)
    except Exception:
        pass  # never let a persistence hiccup take the game server down


async def _refresh_room_from_db(room: "Room"):
    """Overwrites `room`'s persisted fields in place with whatever's
    currently saved (Postgres, in a multi-instance setup) — used right
    after acquiring a distributed room lock, so this instance mutates the
    latest state rather than a possibly-stale local copy. Registered with
    hokm_realtime.set_refresh_hook() at startup; only ever called when
    Redis is actually enabled. Runtime-only fields (lock, analysis_tasks,
    voice_participants) are deliberately left untouched — see the note by
    _ROOM_PERSISTED_FIELDS."""
    row = DB.load_room(room.id)
    if not row:
        return
    try:
        fresh = row_to_room(row)
    except TypeError:
        return  # a saved shape from an older version of Room — keep what we have
    for f in _ROOM_PERSISTED_FIELDS:
        if f == "id":
            continue
        setattr(room, f, getattr(fresh, f))


def _hydrate_room(room_id: Optional[str]) -> Optional["Room"]:
    """ROOMS.get(), but falls back to loading the room from the database
    if this instance has never seen it (e.g. it was created on a
    different instance and this one is only hearing about it now, via a
    reconnect or an in-game action). No-op fallback on a single instance
    or on SQLite — DB.load_room() simply won't find anything this
    process didn't already save itself."""
    if not room_id:
        return None
    room = ROOMS.get(room_id)
    if room:
        return room
    row = DB.load_room(room_id)
    if not row:
        return None
    try:
        room = row_to_room(row)
    except TypeError:
        return None
    ROOMS[room.id] = room
    if room.code:
        CODE_TO_ROOM[room.code] = room.id
    return room


def _hydrate_room_by_code(code: str) -> Optional["Room"]:
    """Same idea as _hydrate_room(), but for the "join by code" and
    "spectate by code" flows: a friend's code might belong to a room this
    instance never created or loaded before."""
    room_id = CODE_TO_ROOM.get(code)
    if room_id:
        return _hydrate_room(room_id)
    row = DB.find_room_by_code(code)
    if not row:
        return None
    try:
        room = row_to_room(row)
    except TypeError:
        return None
    ROOMS[room.id] = room
    if room.code:
        CODE_TO_ROOM[room.code] = room.id
    return room


def _get_room(room_id: Optional[str]) -> Optional["Room"]:
    """Alias kept distinct from _hydrate_room() only for readability at
    call sites — every in-game action that needs "the room this already-
    connected player is sitting in" goes through here."""
    return _hydrate_room(room_id)


async def _on_remote_room_update(room_id: str):
    """Called (only when Redis is enabled) whenever ANOTHER instance
    reports a change to room_id. If we have no locally-connected sockets
    for this room at all, there's nothing to do — the next time someone
    here interacts with it, _get_room()/_hydrate_room() will pull the
    latest row anyway. If we do, refresh from Postgres and push straight
    to our own sockets — no re-save, no re-publish, so this can never
    loop back to the instance that started it."""
    room = ROOMS.get(room_id)
    if not room:
        return
    await _refresh_room_from_db(room)
    await broadcast_room(room, lambda seat: state_for(room, seat))


def check_season(p: "Player") -> Optional[dict]:
    """Call whenever a player connects. If a new season has started since
    their last visit, soft-reset their RR and report what changed."""
    season = R.current_season_id()
    if p.season_id == season:
        return None
    before = R.rank_info(p.rr)
    p.rr = R.season_soft_reset(p.rr)
    p.season_id = season
    after = R.rank_info(p.rr)
    return {"season": season, "before": before, "after": after}


def check_daily_missions(p: "Player") -> bool:
    """Call whenever a player connects. Refreshes their 3 daily missions
    if the calendar day has rolled over since their last visit."""
    today = E.today_str()
    if p.missions_date != today:
        p.missions = E.generate_daily_missions(today, seed_extra=p.id)
        p.missions_date = today
        return True
    return False


def economy_payload(p: "Player") -> dict:
    return {
        "type": "economy_state",
        "wallet": p.wallet,
        "inventory": list(p.inventory),
        "missions": p.missions,
        "shop": E.SHOP_ITEMS,
        "canSpinWheel": p.last_wheel_spin != E.today_str(),
    }


def achievement_metrics(p: "Player") -> dict:
    """Every number hokm_achievements.py needs, read straight off state the
    server already keeps elsewhere (hokm_stats' lifetime stats, wallet
    level, max rank ever reached, social state, world-cup titles, shop
    inventory) — nothing new to track or that can fall out of sync."""
    return {
        "matches_won": p.stats.get("matchesWon", 0),
        "tricks_won": p.stats.get("tricksWon", 0),
        "sur_won": p.stats.get("surWon", 0),
        "hakem_wins": p.stats.get("hakemWins", 0),
        "best_streak": p.stats.get("bestWinStreak", 0),
        "level": p.wallet.get("level", 1),
        "max_rr": p.max_rr,
        "friends": len(p.friends),
        "clan_joined": 1 if p.clan_id else 0,
        "world_cup_titles": len(p.world_cup_titles),
        "shop_items": len(p.inventory),
    }


def achievements_payload(p: "Player") -> dict:
    metrics = achievement_metrics(p)
    return {
        "type": "achievements_state",
        "achievements": ACH.all_achievements(metrics, p.achievements_claimed),
        "unclaimedCount": ACH.unclaimed_unlocked_count(metrics, p.achievements_claimed),
    }


def check_bp_season(p: "Player") -> bool:
    """Battle pass shares its season with the ranked ladder (hokm_ranks'
    monthly 'YYYY-MM' id). New season -> fresh track, same as a real
    battle pass: unclaimed rewards from last season are simply gone."""
    season = M.bp_season_id()
    if p.bp_season_id != season:
        p.bp_season_id = season
        p.bp_xp = 0
        p.bp_premium = False
        p.bp_claimed_free = set()
        p.bp_claimed_premium = set()
        return True
    return False


def monetization_payload(p: "Player") -> dict:
    return {
        "type": "monetization_state",
        "vip": {
            "active": M.is_vip(p.vip_until),
            "secondsLeft": M.vip_seconds_left(p.vip_until),
            "plans": M.VIP_PLANS,
            "canClaimDaily": M.is_vip(p.vip_until) and p.vip_last_daily_claim != M.today_str(),
            "dailyBonusCoins": M.VIP_DAILY_BONUS_COINS,
        },
        "ads": {
            "watchedToday": p.ads_watched_today if p.ads_date == M.today_str() else 0,
            "maxPerDay": M.AD_MAX_PER_DAY,
            "rewardCoins": M.AD_REWARD_COINS,
        },
        "gemPacks": M.GEM_PACKS,
        "battlePass": {
            "seasonId": p.bp_season_id,
            "xp": p.bp_xp,
            "tier": M.bp_tier_from_xp(p.bp_xp),
            "maxTier": M.BP_MAX_TIER,
            "xpPerTier": M.BP_XP_PER_TIER,
            "premium": p.bp_premium,
            "premiumPriceGems": M.BP_PREMIUM_PRICE_GEMS,
            "tiers": M.battle_pass_tiers(),
            "claimedFree": list(p.bp_claimed_free),
            "claimedPremium": list(p.bp_claimed_premium),
        },
    }


def stats_summary(stats: dict) -> dict:
    return {
        **stats,
        "winRate": ST.win_rate(stats),
        "surRate": ST.sur_rate(stats),
        "hakemWinRate": ST.hakem_win_rate(stats),
    }


def stats_payload(p: "Player") -> dict:
    return {
        "type": "stats_state",
        "stats": stats_summary(p.stats),
        "rank": R.rank_info(p.rr),
    }


def match_history_payload(p: "Player") -> dict:
    return {
        "type": "match_history",
        "matches": [
            {k: v for k, v in m.items() if k != "hands"}  # summaries only — replay data fetched on demand
            for m in p.match_history
        ],
    }


def leaderboard_entries() -> list:
    return [
        {
            "playerId": pid,
            "name": pl.name,
            "rr": pl.rr,
            "matchesWon": pl.stats.get("matchesWon", 0),
            "matchesPlayed": pl.stats.get("matchesPlayed", 0),
        }
        for pid, pl in PLAYERS.items()
    ]


def leaderboard_payload(p: "Player") -> dict:
    # NOTE: distinct message type from the Phase 5 RR-based "leaderboard"
    # (get_leaderboard below, used by tournament-panel.js) — this one ranks
    # by career matches won, straight out of Phase 11 stats.
    entries = leaderboard_entries()
    return {
        "type": "stats_leaderboard",
        "top": ST.build_leaderboard(entries),
        "me": ST.leaderboard_position(entries, p.id),
    }


def clan_payload(p: "Player") -> dict:
    clan = CLANS.get(p.clan_id) if p.clan_id else None
    if not clan:
        return {"type": "clan_state", "clan": None}
    return {
        "type": "clan_state",
        "clan": {
            "id": clan.id,
            "name": clan.name,
            "code": clan.code,
            "ownerId": clan.owner_id,
            "level": clan.level,
            "xp": clan.xp,
            "xpNeeded": S.clan_xp_for_level(clan.level),
            "members": [
                {"playerId": mid, "name": PLAYERS[mid].name, "online": PLAYERS[mid].connected}
                for mid in clan.members if mid in PLAYERS
            ],
        },
    }


def i18n_payload(p: "Player") -> dict:
    return {
        "type": "i18n_state",
        "language": p.language,
        "languages": I18N.language_list(),
        "strings": I18N.catalog(p.language),
    }


def region_payload(p: "Player") -> dict:
    return {
        "type": "region_state",
        "region": p.region,
        "regions": REG.region_list(p.language),
    }


def _find_world_cup_participant(pid: str):
    """Returns (bucket_dict, participant_dict, stage) for a player currently
    registered in CURRENT_WORLD_CUP, or (None, None, None)."""
    wc = CURRENT_WORLD_CUP
    if pid in wc.finalists:
        return wc.finalists, wc.finalists[pid], "finals"
    for bucket in wc.regions.values():
        if pid in bucket:
            return bucket, bucket[pid], "qualifiers"
    return None, None, None


def world_cup_payload(p: "Player") -> dict:
    wc = CURRENT_WORLD_CUP
    _, my_part, stage = _find_world_cup_participant(p.id)

    def name_of(pid):
        return PLAYERS[pid].name if pid in PLAYERS else "؟"

    standings = None
    if wc.status == "finals" or wc.status == "finished":
        standings = [
            {"playerId": pid, "name": name_of(pid), "points": part["points"],
             "wins": part["wins"], "losses": part["losses"], "eliminated": part["eliminated"]}
            for pid, part in WC.final_standings(wc.finalists)
        ]
    elif my_part is not None:
        region_bucket = wc.regions.get(p.region, {})
        standings = [
            {"playerId": pid, "name": name_of(pid), "points": part["points"],
             "wins": part["wins"], "losses": part["losses"], "eliminated": part["eliminated"]}
            for pid, part in WC.region_standings(region_bucket)
        ]

    return {
        "type": "world_cup_state",
        "seasonId": wc.season_id,
        "status": wc.status,
        "eligible": WC.is_eligible(p.rr),
        "myStage": stage,
        "myRegistered": my_part is not None,
        "standings": standings,
        "champion": name_of(wc.champion_id) if wc.champion_id else None,
        "myTitles": p.world_cup_titles,
        "totalRegistered": WC.total_registered(wc.regions),
        "minTotalToStart": WC.MIN_TOTAL_TO_START,
    }


async def broadcast_world_cup():
    wc = CURRENT_WORLD_CUP
    all_ids = set(wc.finalists) | {pid for bucket in wc.regions.values() for pid in bucket}
    for pid in all_ids:
        if pid in PLAYERS:
            await send(pid, world_cup_payload(PLAYERS[pid]))


async def finish_world_cup():
    wc = CURRENT_WORLD_CUP
    ranked_ids = [pid for pid, _ in WC.final_standings(wc.finalists)]
    wc.champion_id = ranked_ids[0] if ranked_ids else None
    prizes = WC.prizes_for(ranked_ids)
    for pid, prize in prizes.items():
        p = PLAYERS.get(pid)
        if not p:
            continue
        p.wallet["coins"] += prize["coins"]
        p.wallet["gems"] += prize["gems"]
        if prize["place"] == 1:
            p.world_cup_titles = [WC.champion_title(wc.season_id)] + p.world_cup_titles
        await send(pid, economy_payload(p))
        await send(pid, achievements_payload(p))
    wc.status = "finished"
    await broadcast_world_cup()


def maybe_reset_world_cup():
    """Call opportunistically (e.g. on login). Once a finished World Cup's
    season has rolled over, start a fresh registration period."""
    global CURRENT_WORLD_CUP
    season = WC.season_id()
    if CURRENT_WORLD_CUP.status == "finished" and CURRENT_WORLD_CUP.season_id != season:
        CURRENT_WORLD_CUP = WorldCup(season_id=season)


async def start_world_cup_qualifiers_if_ready():
    wc = CURRENT_WORLD_CUP
    if wc.status == "registration" and WC.total_registered(wc.regions) >= WC.MIN_TOTAL_TO_START:
        wc.status = "qualifiers"
        await broadcast_world_cup()


async def report_world_cup_match(pid: str, won: bool):
    wc = CURRENT_WORLD_CUP
    bucket, participant, stage = _find_world_cup_participant(pid)
    if participant is None:
        return

    if stage == "qualifiers":
        if participant["eliminated"]:
            return
        WC.record_match(participant, won)
        if WC.all_regions_done(wc.regions):
            finalists = {}
            for bucket in wc.regions.values():
                for fid in WC.promote_region(bucket):
                    finalists[fid] = WC.new_participant()
            wc.finalists = finalists
            wc.status = "finals"
        await broadcast_world_cup()

    elif stage == "finals":
        if participant["eliminated"] or wc.status != "finals":
            return
        WC.record_match(participant, won)
        if WC.should_run_cut(wc.finalists):
            eliminated = WC.apply_cut(wc.finalists)
            for eid in eliminated:
                if eid in PLAYERS:
                    await send(eid, {"type": "world_cup_eliminated", "message": I18N.t("worldcup_eliminated", PLAYERS[eid].language)})
        if WC.is_finished(wc.finalists):
            await finish_world_cup()
        else:
            await broadcast_world_cup()


def new_code() -> str:
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if code not in CODE_TO_ROOM:
            return code


# --------------------------------------------------------------- sending ---

async def send(player_id: str, payload: dict):
    p = PLAYERS.get(player_id)
    if not p or not p.ws or not p.connected:
        return
    try:
        await p.ws.send_text(json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


async def broadcast_room(room: Room, payload_fn):
    """payload_fn(seat_or_None) -> dict, called per connected human seat,
    then once more per spectator with seat=None."""
    for seat, pid in room.seats.items():
        if pid and pid != "bot":
            await send(pid, payload_fn(seat))
    for pid in room.spectators:
        await send(pid, payload_fn(None))


def state_for(room: Room, viewer_seat: Optional[str]) -> dict:
    is_spectator = viewer_seat is None
    hand = room.hands.get(viewer_seat, []) if not is_spectator else []
    counts = {s: len(room.hands.get(s, [])) for s in (G.SEATS if is_spectator else [x for x in G.SEATS if x != viewer_seat])}
    partner = room.partner_of(viewer_seat)
    return {
        "type": "game_state",
        "mySeat": viewer_seat,
        "spectating": is_spectator,
        "spectatorCount": len(room.spectators),
        "phase": room.phase,
        "hakem": room.hakem,
        "trump": room.trump,
        "turn": room.turn,
        "hand": hand,
        "handCounts": counts,
        "currentTrick": room.current_trick,
        "trickWinnerSeat": room.trick_winner_seat,
        "tricksWon": room.tricks_won,
        "roundsWon": room.rounds_won,
        "handWinnerTeam": room.hand_winner_team,
        "matchWinnerTeam": room.match_winner_team,
        "seatNames": {s: room.name_of(s) for s in G.SEATS},
        "partnerConnected": room.is_seat_connected(partner) if partner else True,
    }


async def broadcast_room_wait(room: Room):
    """Send every human currently seated in a not-yet-started private room the
    full 4-seat lobby state: who's in each seat (name or None for open),
    and which seat *they* are in / whether they're the host."""
    save_room_state(room)
    await RT.publish_room_update(room.id)
    seat_names = {
        s: (PLAYERS[pid].name if pid and pid != "bot" and PLAYERS.get(pid) else None)
        for s, pid in room.seats.items()
    }
    for seat, pid in room.seats.items():
        if pid and pid != "bot":
            await send(pid, {
                "type": "room_wait",
                "code": room.code,
                "seats": seat_names,
                "mySeat": seat,
                "isHost": seat == "south",
            })


async def broadcast_state(room: Room):
    save_room_state(room)
    await RT.publish_room_update(room.id)
    await broadcast_room(room, lambda seat: state_for(room, seat))


async def broadcast_toast(room: Room, message: str):
    await broadcast_room(room, lambda seat: {"type": "toast", "message": message})


async def broadcast_chat(room: Room, event: dict):
    room.chat_log.append(event)
    room.chat_log[:] = room.chat_log[-50:]
    await broadcast_room(room, lambda seat: {"type": "chat", **event})


async def voice_remove(room: Room, player_id: str):
    """Phase 14 — take a player out of a room's voice chat (mic toggled
    off, they left the room, or they disconnected) and tell whoever's
    left so their browsers can tear down that one peer connection.
    Safe to call even if the player was never in voice."""
    if player_id not in room.voice_participants:
        return
    room.voice_participants.discard(player_id)
    for pid in list(room.voice_participants):
        await send(pid, {"type": "voice_peer_left", "playerId": player_id})


MAX_CHAT_LEN = 200
QUICK_CHAT_PHRASES = ["دمت گرم!", "آفرین :)", "بد شانسی!", "حکم خوبی بود", "دوباره بازی می‌کنیم؟", "خیلی خوب بود!"]


# ------------------------------------------------------------- game flow ---

def deal_hand(room: Room, hakem: str):
    room.deck = G.shuffle(G.create_deck())
    room.hands = {s: [] for s in G.SEATS}
    room.hands[hakem] = G.sort_hand(room.deck[:5], None)
    room.deck = room.deck[5:]
    room.hakem = hakem
    room.trump = None
    room.phase = "choosing-trump"
    room.current_trick = []
    room.trick_leader = None
    room.turn = hakem
    room.tricks_won = {"A": 0, "B": 0}
    room.hand_winner_team = None
    room.trick_winner_seat = None
    room.hand_log = []  # Phase 11: fresh trick log for this hand


def finish_trump_selection(room: Room, suit: str):
    room.trump = suit
    hakem = room.hakem
    room.hands[hakem] = G.sort_hand(room.hands[hakem] + room.deck[:8], suit)
    room.deck = room.deck[8:]
    rest = [s for s in G.SEATS if s != hakem]
    for s in rest:
        room.hands[s] = G.sort_hand(room.deck[:13], suit)
        room.deck = room.deck[13:]
    room.phase = "playing"
    room.turn = hakem
    room.trick_leader = hakem


async def schedule_seat_decision(room: Room, seat: str, kind: str):
    """kind: 'trump' or 'play'. Bots act after a short delay; disconnected
    humans get a grace period before the bot covers for them."""
    token = room.bump_token()
    pid = room.seats.get(seat)
    if pid == "bot":
        asyncio.create_task(_bot_or_grace_act(room, seat, kind, token, delay=BOT_THINK_SECONDS))
    elif not room.is_seat_connected(seat):
        asyncio.create_task(_bot_or_grace_act(room, seat, kind, token, delay=GRACE_SECONDS))
    # else: human is connected — we just wait for their websocket message.


async def _bot_or_grace_act(room: Room, seat: str, kind: str, token: int, delay: float):
    await asyncio.sleep(delay)
    async with RT.room_lock(room):
        if room.turn_token != token:
            return  # stale — a real move (or reconnect+move) already happened
        if kind == "trump" and not (room.phase == "choosing-trump" and room.turn == seat):
            return
        if kind == "play" and not (room.phase == "playing" and room.turn == seat):
            return
        if kind == "trump":
            suit = G.ai_choose_trump(room.hands[seat])
            await _do_choose_trump(room, seat, suit)
        else:
            card = G.ai_choose_card(room.hands[seat], room.current_trick, room.trump, seat)
            await _do_play_card(room, seat, card)


async def _do_choose_trump(room: Room, seat: str, suit: str):
    finish_trump_selection(room, suit)
    await broadcast_state(room)
    await broadcast_toast(room, f"{room.name_of(seat)} حکم را «{G.SUITS[suit]['name']}» انتخاب کرد")
    await schedule_seat_decision(room, room.turn, "play")


async def _record_decision(room: Room, seat: str, hands_snapshot: dict, trick_snapshot: list,
                            card: dict, tricks_snapshot: dict):
    """Runs classify_decision's real minimax search in a thread and stashes
    the result — see the call site in _do_play_card for why this is a
    background task rather than something awaited inline."""
    tag = await asyncio.to_thread(
        ST.classify_decision, hands_snapshot, trick_snapshot, card, room.trump, seat, tricks_snapshot,
    )
    room.decisions.setdefault(seat, []).append({"tag": tag})


async def _await_pending_analysis(room: Room):
    """Called right before building the post-match summary so a still-running
    background classify_decision() lands in it instead of being dropped.
    Individually time-boxed so one slow search can't hang match-end."""
    tasks, room.analysis_tasks = room.analysis_tasks, []
    for task in tasks:
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except Exception:
            pass


async def _do_play_card(room: Room, seat: str, card: dict):
    hand = room.hands[seat]

    # Phase 11/15 — snapshot this decision (human seats only) before the hand
    # is mutated, for the post-match "AI coach" summary. classify_decision
    # now runs a real minimax search (hokm_minimax), so it's fired as a
    # background task (thread) instead of awaited here — it never delays
    # this player's move or anyone else's turn. room.analysis_tasks is
    # awaited once, right before the post-match summary is built, so a slow
    # search still lands in the summary instead of being silently dropped.
    if seat in room.human_seats():
        hands_snapshot = {s: list(h) for s, h in room.hands.items()}
        trick_snapshot = list(room.current_trick)
        tricks_snapshot = dict(room.tricks_won)
        room.analysis_tasks.append(asyncio.create_task(
            _record_decision(room, seat, hands_snapshot, trick_snapshot, card, tricks_snapshot)
        ))

    hand[:] = [c for c in hand if not (c["suit"] == card["suit"] and c["rank"] == card["rank"])]
    room.current_trick.append({"seat": seat, "card": card})

    if len(room.current_trick) < 4:
        room.turn = G.next_seat(room.turn)
        await broadcast_state(room)
        await schedule_seat_decision(room, room.turn, "play")
    else:
        led_suit = room.current_trick[0]["card"]["suit"]
        winner_seat = G.resolve_trick_winner(room.current_trick, led_suit, room.trump)
        room.trick_winner_seat = winner_seat
        room.turn = None
        await broadcast_state(room)
        token = room.bump_token()
        asyncio.create_task(_finish_trick_after_delay(room, winner_seat, token))


async def _finish_trick_after_delay(room: Room, winner_seat: str, token: int):
    await asyncio.sleep(TRICK_RESOLVE_DELAY)
    async with RT.room_lock(room):
        if room.turn_token != token:
            return
        team = G.TEAM[winner_seat]
        room.tricks_won[team] += 1

        # Phase 11 — record the finished trick (before it's cleared below)
        # for this hand's replay.
        room.hand_log.append({"trick": list(room.current_trick), "winnerSeat": winner_seat, "team": team})

        # Phase 6: credit the human(s) on the winning team with a trick,
        # and the hakem (if human) with a "won a trick while hakem" tick.
        for seat in room.human_seats():
            pid = room.seats.get(seat)
            p = PLAYERS.get(pid) if pid else None
            if p and G.TEAM[seat] == team:
                E.bump_mission_progress(p.missions, "tricks", 1)

        room.trick_leader = winner_seat
        room.turn = winner_seat
        room.current_trick = []
        room.trick_winner_seat = None

        total_played = room.tricks_won["A"] + room.tricks_won["B"]
        if room.tricks_won["A"] >= 7 or room.tricks_won["B"] >= 7 or total_played >= 13:
            winner_team = "A" if room.tricks_won["A"] > room.tricks_won["B"] else "B"
            room.rounds_won[winner_team] += 1
            room.hand_winner_team = winner_team

            # Phase 11 — freeze this hand's tricks into the match replay.
            room.match_log.append(ST.build_hand_record(
                len(room.match_log) + 1, room.hakem, room.trump,
                room.tricks_won, winner_team, room.hand_log,
            ))

            was_sur = room.tricks_won[winner_team] == 7 and room.tricks_won["A" if winner_team == "B" else "B"] == 0
            if was_sur:
                for seat in room.human_seats():
                    pid = room.seats.get(seat)
                    p = PLAYERS.get(pid) if pid else None
                    if p and G.TEAM[seat] == winner_team:
                        E.bump_mission_progress(p.missions, "sur", 1)

            if room.hakem and G.TEAM[room.hakem] == winner_team:
                hakem_pid = room.seats.get(room.hakem)
                hakem_p = PLAYERS.get(hakem_pid) if hakem_pid else None
                if hakem_p:
                    E.bump_mission_progress(hakem_p.missions, "hakem_wins", 1)

            if room.rounds_won[winner_team] >= G.TARGET_ROUNDS:
                room.match_winner_team = winner_team
                room.phase = "match-end"
                await broadcast_state(room)
                await apply_rank_changes(room, winner_team)
            else:
                room.phase = "hand-end"
                await broadcast_state(room)
        else:
            await broadcast_state(room)
            await schedule_seat_decision(room, room.turn, "play")


async def apply_rank_changes(room: Room, winner_team: str):
    """Real 2v2: humans can now sit on either team (south+north as team A,
    west+east as team B), so win/loss is worked out per human seat against
    that seat's own team, instead of assuming team A is always the humans.
    Updates each connected human's RR *and* their economy wallet/missions,
    and tells them what changed."""
    await _await_pending_analysis(room)
    for seat in room.human_seats():
        pid = room.seats.get(seat)
        p = PLAYERS.get(pid) if pid else None
        if not p:
            continue
        won = winner_team == G.TEAM[seat]

        # Phase 5 — rank
        rank_result = R.apply_result(p.rr, won, win_streak=p.win_streak)
        p.rr = rank_result["rr"]
        p.max_rr = max(p.max_rr, p.rr)
        p.win_streak = p.win_streak + 1 if won else 0
        await send(pid, {"type": "rank_update", **rank_result})

        # Phase 11 — freeze this match's replay + a heuristic "AI coach"
        # summary of this player's card choices, fold it into career
        # stats, and stash it in their match history.
        analysis = ST.summarize_analysis(room.decisions.get(seat, []))
        match_record = ST.build_match_record(
            room.match_id, time.time(), seat, won, room.rounds_won, room.match_log, analysis,
        )
        p.match_history = ST.cap_history([match_record] + p.match_history)
        p.stats = ST.record_match(p.stats, match_log=room.match_log, seat=seat, won=won, win_streak_after=p.win_streak)
        await send(pid, {"type": "match_recorded", "matchId": room.match_id, "analysis": analysis, "stats": stats_summary(p.stats)})

        # Phase 6 — economy: match reward, "played"/"win" missions, XP/level
        # Phase 10 — VIP boosts coins/XP from this same reward before it's applied
        reward = E.match_reward(won, win_streak=p.win_streak)
        reward = M.apply_reward_multiplier(reward, p.vip_until)
        p.wallet["coins"] += reward["coins"]
        p.wallet["gems"] += reward["gems"]
        xp_result = E.add_xp(p.wallet["xp"], p.wallet["level"], reward["xp"])
        p.wallet.update(xp_result)
        E.bump_mission_progress(p.missions, "played", 1)
        if won:
            E.bump_mission_progress(p.missions, "wins", 1)

        # Phase 10 — battle pass: every match's XP also feeds the season track
        check_bp_season(p)
        bp_tier_before = M.bp_tier_from_xp(p.bp_xp)
        p.bp_xp = min(p.bp_xp + reward["xp"], M.BP_MAX_TIER * M.BP_XP_PER_TIER)
        bp_tier_after = M.bp_tier_from_xp(p.bp_xp)

        await send(pid, {
            "type": "economy_update",
            "reason": "match_end",
            "reward": reward,
            "leveledUp": xp_result["levelsGained"] > 0,
            "wallet": p.wallet,
            "missions": p.missions,
        })
        if bp_tier_after > bp_tier_before:
            await send(pid, {"type": "battle_pass_tier_up", "tier": bp_tier_after})
            await send(pid, monetization_payload(p))

        # Phase 13 — a match can push several achievements (wins, tricks,
        # sur, hakem, streak, rank, level) past their target at once; send
        # the refreshed list so the UI can highlight anything newly claimable.
        await send(pid, achievements_payload(p))

        # Phase 7 — clan XP: every member's match nudges their clan along
        if p.clan_id and p.clan_id in CLANS:
            clan = CLANS[p.clan_id]
            gain = S.CLAN_XP_PER_MATCH + (S.CLAN_XP_PER_WIN_BONUS if won else 0)
            clan_result = S.add_clan_xp(clan.xp, clan.level, gain)
            clan.xp, clan.level = clan_result["xp"], clan_result["level"]
            for mid in clan.members:
                if mid in PLAYERS:
                    await send(mid, clan_payload(PLAYERS[mid]))

        # Phase 8 — tournaments: report this match's result if the player
        # currently has an active tournament running
        if p.active_tournament and p.active_tournament in TOURNAMENTS:
            await report_tournament_match(TOURNAMENTS[p.active_tournament], pid, won)

        # Phase 12 — World Cup: feed this match into qualifiers/finals too,
        # if the player is currently registered in the live championship
        await report_world_cup_match(pid, won)

        save_player(p)  # match end is the highest-value moment to persist — on top of the periodic autosave


def tournament_payload(tour: "Tournament") -> dict:
    ranked = T.standings(tour.participants)
    return {
        "type": "tournament_state",
        "id": tour.id,
        "name": tour.name,
        "size": tour.size,
        "mode": tour.mode,
        "status": tour.status,
        "ownerId": tour.owner_id,
        "standings": [
            {
                "playerId": pid,
                "name": PLAYERS[pid].name if pid in PLAYERS else "؟",
                "points": part["points"],
                "wins": part["wins"],
                "losses": part["losses"],
                "eliminated": part["eliminated"],
            }
            for pid, part in ranked
        ],
    }


async def broadcast_tournament(tour: "Tournament"):
    payload = tournament_payload(tour)
    for pid in tour.participants:
        await send(pid, payload)


async def report_tournament_match(tour: "Tournament", player_id: str, won: bool):
    part = tour.participants.get(player_id)
    if not part or part["eliminated"] or tour.status != "active":
        return
    T.record_match(part, won)

    if tour.mode == "knockout" and T.should_run_knockout_cut(tour.participants):
        eliminated = T.apply_knockout_cut(tour.participants)
        for pid in eliminated:
            if pid in PLAYERS:
                PLAYERS[pid].active_tournament = None
                await send(pid, {"type": "tournament_eliminated", "tournamentId": tour.id})

    if T.is_finished(tour.participants, tour.mode):
        await finish_tournament(tour)
    else:
        await broadcast_tournament(tour)


async def finish_tournament(tour: "Tournament"):
    tour.status = "finished"
    ranked_ids = [pid for pid, _ in T.standings(tour.participants)]
    prizes = T.prizes_for(tour.size, ranked_ids)
    for pid, prize in prizes.items():
        p = PLAYERS.get(pid)
        if not p:
            continue
        p.wallet["coins"] += prize["coins"]
        p.wallet["gems"] += prize["gems"]
        p.active_tournament = None
        await send(pid, {"type": "tournament_finished", "tournamentId": tour.id, "place": prize["place"], "prize": prize})
        await send(pid, economy_payload(p))
    await broadcast_tournament(tour)


async def maybe_cover_pending_decision(room: Room, seat: str):
    """Called right when a seat's connection drops. If it's currently that
    seat's decision to make (trump or card) and no grace/bot task exists for
    it yet (because they were still connected when it was scheduled), start
    the grace/bot fallback now so the match doesn't stall forever."""
    if room.phase == "choosing-trump" and room.hakem == seat and room.turn == seat:
        await schedule_seat_decision(room, seat, "trump")
    elif room.phase == "playing" and room.turn == seat:
        await schedule_seat_decision(room, seat, "play")


async def start_match(room: Room):
    room.rounds_won = {"A": 0, "B": 0}
    room.match_id = uuid.uuid4().hex[:10]                   # Phase 11: id for this match's replay/history entry
    room.match_log = []                                    # Phase 11: fresh replay for this match
    room.decisions = {s: [] for s in room.human_seats()}    # Phase 11: fresh decision log for AI analysis
    room.analysis_tasks = []    # Phase 15: drop any leftover tasks from a previous match
    hakem = random.choice(G.SEATS)
    deal_hand(room, hakem)
    room.phase = "choosing-trump"
    await broadcast_state(room)
    await schedule_seat_decision(room, hakem, "trump")


# --------------------------------------------------------- room lifecycle --

async def start_game_between(pids: list):
    """Seats 1-4 real players (south+north = team A, west+east = team B) in
    fill order and pads whatever seats are left with bots, so this covers
    the old 2-human+2-bot MVP shape as well as a real 4-human 2v2 match."""
    seats = {}
    order = list(SEAT_FILL_ORDER)
    for pid in pids:
        seats[order.pop(0)] = pid
    for empty_seat in order:
        seats[empty_seat] = "bot"
    room = Room(id=str(uuid.uuid4()), seats=seats)
    ROOMS[room.id] = room
    for seat, pid in seats.items():
        if pid != "bot":
            PLAYERS[pid].room_id = room.id
            PLAYERS[pid].seat = seat
    async with RT.room_lock(room):
        await start_match(room)


async def _mm_retry_after_grace(player_id: str):
    """If try_match_queue() couldn't seat this player right away, check
    again once the bot-fill timeout has elapsed, so they're not stuck
    waiting forever just because nobody else happens to join afterward."""
    await asyncio.sleep(QUICK_MATCH_BOT_FILL_SECONDS + 0.5)
    if player_id in MM_QUEUE:
        await try_match_queue()


def _drop_stale_queue_entries():
    for pid in [p for p in MM_QUEUE if not (PLAYERS.get(p) and PLAYERS[p].connected)]:
        MM_QUEUE.remove(pid)
        MM_QUEUE_JOINED_AT.pop(pid, None)


def _pick_next_group(pool: list, size: int) -> list:
    """Picks the next `size` players to seat together out of `pool` (a
    snapshot of MM_QUEUE, in queue order). If any active tournament has
    at least `size` of its own participants currently queued, those are
    picked first (oldest-queued of that tournament first) — so a
    tournament match is actually played against fellow participants,
    not whoever else happened to be online. Otherwise falls back to
    plain FIFO (the first `size` players in the queue)."""
    by_tour = {}
    for pid in pool:
        tid = PLAYERS[pid].active_tournament if PLAYERS.get(pid) else None
        if tid and tid in TOURNAMENTS:
            by_tour.setdefault(tid, []).append(pid)
    for tid, members in by_tour.items():
        if len(members) >= size:
            return members[:size]
    return pool[:size]


async def try_match_queue():
    """Real 2v2: as soon as 4 humans are waiting, seat all 4 together —
    no bots at all. Below that, whoever has waited past
    QUICK_MATCH_BOT_FILL_SECONDS gets started anyway with bots padding the
    remaining seats, so a lone player never waits forever just to play.
    Tournament participants are preferentially grouped with each other
    (see _pick_next_group) so a tournament match is genuinely played
    against other people in the same tournament whenever enough of them
    are queued up at once."""
    _drop_stale_queue_entries()

    while len(MM_QUEUE) >= 4:
        four = _pick_next_group(list(MM_QUEUE), 4)
        for pid in four:
            MM_QUEUE.remove(pid)
            MM_QUEUE_JOINED_AT.pop(pid, None)
        random.shuffle(four)  # random teams, not "who queued together"
        await start_game_between(four)
        _drop_stale_queue_entries()

    now = time.time()
    while MM_QUEUE and (now - MM_QUEUE_JOINED_AT.get(MM_QUEUE[0], now)) >= QUICK_MATCH_BOT_FILL_SECONDS:
        group = _pick_next_group(list(MM_QUEUE), 4)  # 1-3 players who've waited long enough; bots cover the rest
        for pid in group:
            MM_QUEUE.remove(pid)
            MM_QUEUE_JOINED_AT.pop(pid, None)
        random.shuffle(group)
        await start_game_between(group)
        _drop_stale_queue_entries()


# ------------------------------------------------------------- ws handler --

async def handle_message(player_id: str, msg: dict):
    p = PLAYERS[player_id]
    t = msg.get("type")

    # Phase 9 — throttle: no legitimate client sends dozens of messages
    # a second. Over the limit, the message is silently dropped instead
    # of processed (cheap defence against flooding, scripted or not).
    allowed, p.action_log = SEC.check_rate_limit(p.action_log)
    if not allowed:
        return

    if t == "quick_match":
        if player_id not in MM_QUEUE:
            MM_QUEUE.append(player_id)
            MM_QUEUE_JOINED_AT[player_id] = time.time()
            asyncio.create_task(_mm_retry_after_grace(player_id))
        await send(player_id, {"type": "screen", "name": "matchmaking"})
        await try_match_queue()
        return

    if t == "cancel_matchmaking":
        if player_id in MM_QUEUE:
            MM_QUEUE.remove(player_id)
        MM_QUEUE_JOINED_AT.pop(player_id, None)
        await send(player_id, {"type": "screen", "name": "lobby"})
        return

    if t == "create_room":
        code = new_code()
        room = Room(id=str(uuid.uuid4()), code=code, seats={"south": player_id, "north": None, "west": None, "east": None})
        ROOMS[room.id] = room
        CODE_TO_ROOM[code] = room.id
        p.room_id, p.seat = room.id, "south"
        await broadcast_room_wait(room)
        return

    if t == "join_room":
        code = (msg.get("code") or "").strip().upper()
        room = _hydrate_room_by_code(code)
        open_seat = next((s for s in ["north", "east", "west"] if room and room.seats.get(s) is None), None) if room else None
        if not room or room.phase != "waiting" or not open_seat:
            await send(player_id, {"type": "error", "message": I18N.t("room_code_invalid_or_full", p.language)})
            return
        room.seats[open_seat] = player_id
        p.room_id, p.seat = room.id, open_seat
        await broadcast_room_wait(room)
        if all(room.seats.get(s) is not None for s in G.SEATS):
            async with RT.room_lock(room):
                await start_match(room)
        return

    if t == "start_with_bots":
        room = _get_room(p.room_id)
        if not room or room.phase != "waiting" or room.seats.get("south") != player_id:
            return  # only the host, and only before the match has started
        for s in G.SEATS:
            if room.seats.get(s) is None:
                room.seats[s] = "bot"
        if room.code:
            CODE_TO_ROOM.pop(room.code, None)
        async with RT.room_lock(room):
            await start_match(room)
        return

    if t == "leave_room":
        room = _get_room(p.room_id)
        if room:
            await voice_remove(room, player_id)
        if room and room.phase == "waiting":
            if room.seats.get("south") == player_id:
                # host left before the match started: the room is gone for everyone
                if room.code:
                    CODE_TO_ROOM.pop(room.code, None)
                ROOMS.pop(room.id, None)
                for s, pid in room.seats.items():
                    if pid and pid != "bot" and pid != player_id and PLAYERS.get(pid):
                        PLAYERS[pid].room_id, PLAYERS[pid].seat = None, None
                        await send(pid, {"type": "error", "message": I18N.t("room_host_left", PLAYERS[pid].language)})
                        await send(pid, {"type": "screen", "name": "lobby"})
            else:
                # a guest left before the match started: free their seat, room stays open
                for s, pid in list(room.seats.items()):
                    if pid == player_id:
                        room.seats[s] = None
                await broadcast_room_wait(room)
        p.room_id, p.seat = None, None
        await send(player_id, {"type": "screen", "name": "lobby"})
        return

    if t == "choose_trump":
        room = _get_room(p.room_id)
        if not room or p.seat != room.hakem or room.phase != "choosing-trump":
            return
        suit = msg.get("suit")
        if suit not in G.SUIT_ORDER:
            return
        async with RT.room_lock(room):
            await _do_choose_trump(room, p.seat, suit)
        return

    if t == "play_card":
        room = _get_room(p.room_id)
        if not room or room.turn != p.seat or room.phase != "playing":
            return
        card = msg.get("card") or {}
        hand = room.hands.get(p.seat, [])
        match = next((c for c in hand if c["suit"] == card.get("suit") and c["rank"] == card.get("rank")), None)
        if not match:
            return
        async with RT.room_lock(room):
            if not G.is_legal_play(hand, room.current_trick, match):
                await send(player_id, {"type": "toast", "message": I18N.t("must_follow_suit", p.language)})
                return
            await _do_play_card(room, p.seat, match)
        return

    if t == "next_hand":
        room = _get_room(p.room_id)
        if not room or room.phase != "hand-end" or p.seat not in room.human_seats():
            return
        async with RT.room_lock(room):
            await start_match_or_next_hand(room)
        return

    if t == "new_match":
        room = _get_room(p.room_id)
        if not room or room.phase != "match-end" or p.seat not in room.human_seats():
            return
        async with RT.room_lock(room):
            await start_match(room)
        return

    if t == "ping":
        await send(player_id, {"type": "pong", "ts": msg.get("ts")})
        return

    # ---------------------------------------------------------- Phase 6 --

    if t == "get_economy":
        check_daily_missions(p)
        await send(player_id, economy_payload(p))
        return

    if t == "claim_mission":
        result = E.claim_mission(p.wallet, p.missions, msg.get("missionId"))
        await send(player_id, {"type": "claim_mission_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
        return

    if t == "spin_wheel":
        result = E.spin_wheel(p.wallet, p.last_wheel_spin)
        if result.get("ok"):
            p.last_wheel_spin = result["lastSpinDate"]
        await send(player_id, {"type": "spin_wheel_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
        return

    if t == "buy_item":
        result = E.buy_item(p.wallet, p.inventory, msg.get("itemId"))
        await send(player_id, {"type": "buy_item_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
        return

    if t == "open_box":
        result = E.open_box(p.wallet, msg.get("boxType"))
        await send(player_id, {"type": "open_box_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
        return

    # ---------------------------------------------------------- Phase 13 --

    if t == "get_achievements":
        await send(player_id, achievements_payload(p))
        return

    if t == "claim_achievement":
        metrics = achievement_metrics(p)
        result = ACH.claim_achievement(p.wallet, p.achievements_claimed, metrics, msg.get("achievementId"))
        if result.get("ok"):
            xp_result = E.add_xp(p.wallet["xp"], p.wallet["level"], result["reward"]["xp"])
            p.wallet.update(xp_result)
        await send(player_id, {"type": "claim_achievement_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
            await send(player_id, achievements_payload(p))
        return

    # --------------------------------------------------------- Phase 10 --

    if t == "get_monetization":
        check_bp_season(p)
        await send(player_id, monetization_payload(p))
        return

    if t == "watch_ad":
        result = M.watch_ad(p.wallet, p.ads_watched_today, p.ads_date)
        if result.get("ok"):
            p.ads_watched_today = result["adsWatchedToday"]
            p.ads_date = result["adsDate"]
        await send(player_id, {"type": "watch_ad_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
            await send(player_id, monetization_payload(p))
        return

    if t == "buy_vip":
        # Real-money path is request_payment below (Zarinpal, verified
        # server-to-server). This instant-grant handler only remains live
        # when HOKM_DEV_FREE_PURCHASES=1, for local UI testing — flip that
        # off before any real launch.
        if os.environ.get("HOKM_DEV_FREE_PURCHASES", "1") != "1":
            await send(player_id, {"type": "buy_vip_result", "ok": False, "error": I18N.t("must_use_real_payment", p.language)})
            return
        result = M.apply_vip_purchase(p.vip_until, msg.get("planId"))
        if result.get("ok"):
            p.vip_until = result["vipUntil"]
        await send(player_id, {"type": "buy_vip_result", **result})
        if result.get("ok"):
            await send(player_id, monetization_payload(p))
        return

    if t == "claim_vip_daily":
        result = M.claim_vip_daily_bonus(p.wallet, p.vip_until, p.vip_last_daily_claim)
        if result.get("ok"):
            p.vip_last_daily_claim = result["claimDate"]
        await send(player_id, {"type": "claim_vip_daily_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
            await send(player_id, monetization_payload(p))
        return

    if t == "buy_gem_pack":
        # Same as buy_vip above — real path is request_payment; this stays
        # only for local testing while HOKM_DEV_FREE_PURCHASES=1.
        if os.environ.get("HOKM_DEV_FREE_PURCHASES", "1") != "1":
            await send(player_id, {"type": "buy_gem_pack_result", "ok": False, "error": I18N.t("must_use_real_payment", p.language)})
            return
        result = M.grant_gem_pack(p.wallet, msg.get("packId"))
        await send(player_id, {"type": "buy_gem_pack_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
        return

    if t == "request_payment":
        # The real-money path: starts a genuine Zarinpal payment session
        # (sandbox by default — see hokm_payments.py) and hands the client
        # a URL to open. The purchase is only granted once Zarinpal
        # confirms it server-to-server at /pay/callback below — never here.
        kind = msg.get("kind")  # "vip" | "gems"
        item_id = msg.get("itemId")
        if kind == "vip":
            item = next((x for x in M.VIP_PLANS if x["id"] == item_id), None)
        elif kind == "gems":
            item = next((x for x in M.GEM_PACKS if x["id"] == item_id), None)
        else:
            item = None
        if not item:
            await send(player_id, {"type": "request_payment_result", "ok": False, "error": I18N.t("payment_item_not_found", p.language)})
            return
        base_url = os.environ.get("HOKM_PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
        callback_url = f"{base_url}/pay/callback"
        pay_result = PAY.request_payment(item["priceToman"], f"Hokm — {item_id}", callback_url, email=p.email)
        if not pay_result.get("ok"):
            await send(player_id, {"type": "request_payment_result", "ok": False, "error": str(pay_result.get("error"))})
            return
        PENDING_PAYMENTS[pay_result["authority"]] = {
            "player_id": player_id, "kind": kind, "item_id": item_id,
            "amount_toman": item["priceToman"], "created_at": time.time(),
        }
        await send(player_id, {"type": "request_payment_result", "ok": True, "payUrl": pay_result["pay_url"]})
        return

    if t == "buy_battle_pass_premium":
        check_bp_season(p)
        result = M.buy_battle_pass_premium(p.wallet, p.bp_premium)
        if result.get("ok"):
            p.bp_premium = True
        await send(player_id, {"type": "buy_battle_pass_premium_result", **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
            await send(player_id, monetization_payload(p))
        return

    if t == "claim_bp_reward":
        check_bp_season(p)
        tier = msg.get("tier")
        track = msg.get("track")
        if not isinstance(tier, int):
            return
        result = M.claim_bp_reward(
            p.wallet, p.inventory, p.bp_xp, p.bp_premium,
            p.bp_claimed_free, p.bp_claimed_premium, tier, track,
        )
        await send(player_id, {"type": "claim_bp_reward_result", "tier": tier, "track": track, **result})
        if result.get("ok"):
            await send(player_id, economy_payload(p))
            await send(player_id, monetization_payload(p))
        return

    # ---------------------------------------------------------- Phase 7 --

    if t == "spectate_room":
        code = (msg.get("code") or "").strip().upper()
        room = _hydrate_room_by_code(code)
        if not room:
            await send(player_id, {"type": "error", "message": I18N.t("room_not_found", p.language)})
            return
        room.spectators.add(player_id)
        p.room_id, p.seat = room.id, None
        await send(player_id, state_for(room, None))
        await broadcast_toast(room, f"{p.name} به عنوان تماشاگر پیوست")
        return

    if t == "leave_spectate":
        room = _get_room(p.room_id)
        if room:
            await voice_remove(room, player_id)
            room.spectators.discard(player_id)
        p.room_id = None
        await send(player_id, {"type": "screen", "name": "lobby"})
        return

    if t == "chat_message":
        room = _get_room(p.room_id)
        if not room:
            return
        if SEC.is_muted(p.mute_until):
            await send(player_id, {"type": "muted", "until": p.mute_until})
            return
        text = (msg.get("text") or "").strip()
        if not text or len(text) > MAX_CHAT_LEN:
            return
        await broadcast_chat(room, {"kind": "text", "from": p.name, "seat": p.seat, "playerId": player_id, "text": text})
        return

    if t == "quick_chat":
        room = _get_room(p.room_id)
        if not room:
            return
        if SEC.is_muted(p.mute_until):
            await send(player_id, {"type": "muted", "until": p.mute_until})
            return
        idx = msg.get("phraseIndex")
        if not isinstance(idx, int) or not (0 <= idx < len(QUICK_CHAT_PHRASES)):
            return
        await broadcast_chat(room, {"kind": "text", "from": p.name, "seat": p.seat, "playerId": player_id, "text": QUICK_CHAT_PHRASES[idx]})
        return

    if t == "emoji":
        room = _get_room(p.room_id)
        if not room:
            return
        if SEC.is_muted(p.mute_until):
            await send(player_id, {"type": "muted", "until": p.mute_until})
            return
        emoji = (msg.get("emoji") or "")[:8]
        if not emoji:
            return
        await broadcast_chat(room, {"kind": "emoji", "from": p.name, "seat": p.seat, "playerId": player_id, "emoji": emoji})
        return

    # ------------------------------------------------------ Phase 14: voice chat --
    # The server is a dumb signaling relay only — it never sees, stores,
    # or forwards any actual audio. It just introduces peers to each
    # other (voice_join/voice_leave) and passes along the WebRTC
    # handshake messages (webrtc_offer/webrtc_answer/webrtc_ice) that
    # the browsers use to open a *direct* peer-to-peer audio connection
    # with one another. Once that connection is up, audio never touches
    # this server again.

    if t == "voice_join":
        room = _get_room(p.room_id)
        if not room:
            return
        if SEC.is_muted(p.mute_until):
            await send(player_id, {"type": "muted", "until": p.mute_until})
            return
        existing = [
            {"playerId": pid, "name": PLAYERS[pid].name}
            for pid in room.voice_participants
            if pid != player_id and pid in PLAYERS
        ]
        room.voice_participants.add(player_id)
        # Tell the joiner who's already in the call — THEY create the
        # offer to each of these (avoids both sides racing to offer at
        # once ("glare"), since only one side of a mesh link ever needs
        # to initiate it).
        await send(player_id, {"type": "voice_joined", "peers": existing})
        # Tell everyone already in the call that a new peer is coming
        # and to expect (and answer) an offer from them.
        for pid in room.voice_participants:
            if pid != player_id:
                await send(pid, {"type": "voice_peer_joined", "playerId": player_id, "name": p.name})
        return

    if t == "voice_leave":
        room = _get_room(p.room_id)
        if room:
            await voice_remove(room, player_id)
        return

    if t in ("webrtc_offer", "webrtc_answer", "webrtc_ice"):
        room = _get_room(p.room_id)
        target_id = msg.get("targetId")
        if not room or not target_id or target_id not in room.voice_participants:
            return
        if player_id not in room.voice_participants:
            return
        payload = {"type": t, "fromId": player_id, "fromName": p.name}
        if t == "webrtc_ice":
            payload["candidate"] = msg.get("candidate")
        else:
            payload["sdp"] = msg.get("sdp")
        await send(target_id, payload)
        return

    # ---------------------------------------------------------- Phase 9: reports --

    if t == "report_player":
        target_id = msg.get("playerId")
        reason = msg.get("reason")
        error = SEC.validate_report(reason, target_id, player_id)
        if error:
            await send(player_id, {"type": "report_error", "message": error})
            return
        target = PLAYERS.get(target_id)
        if not target:
            await send(player_id, {"type": "report_error", "message": I18N.t("player_not_found", p.language)})
            return
        result = SEC.add_report(target.reports_received, player_id, reason)
        target.reports_received = result["reports"]
        if result["shouldMute"] and not SEC.is_muted(target.mute_until):
            target.mute_until = time.time() + SEC.AUTO_MUTE_SECONDS
            await send(target_id, {
                "type": "muted", "until": target.mute_until,
                "reason": "گزارش‌های متعدد بازیکنان دیگر — چت شما موقتاً محدود شد",
            })
        await send(player_id, {"type": "report_sent", "playerId": target_id})
        return

    if t == "add_friend":
        target_id = msg.get("playerId")
        if target_id and target_id in PLAYERS and target_id != player_id:
            p.friends.add(target_id)
            await send(player_id, {"type": "friend_added", "playerId": target_id, "name": PLAYERS[target_id].name})
        return

    if t == "get_friends":
        online = [{"playerId": fid, "name": PLAYERS[fid].name, "online": PLAYERS[fid].connected}
                  for fid in p.friends if fid in PLAYERS]
        await send(player_id, {"type": "friends_list", "friends": online})
        return

    # ---------------------------------------------------------- Phase 7: clan --

    if t == "create_clan":
        if p.clan_id:
            await send(player_id, {"type": "clan_error", "message": I18N.t("already_in_clan", p.language)})
            return
        error = S.validate_clan_name(msg.get("name"))
        if error:
            await send(player_id, {"type": "clan_error", "message": error})
            return
        clan_id = str(uuid.uuid4())
        code = S.new_clan_code()
        while code in CLAN_CODE_TO_ID:
            code = S.new_clan_code()
        clan = Clan(id=clan_id, name=msg["name"].strip(), code=code, owner_id=player_id, members={player_id})
        CLANS[clan_id] = clan
        CLAN_CODE_TO_ID[code] = clan_id
        p.clan_id = clan_id
        await send(player_id, clan_payload(p))
        return

    if t == "join_clan":
        if p.clan_id:
            await send(player_id, {"type": "clan_error", "message": I18N.t("leave_clan_first", p.language)})
            return
        code = (msg.get("code") or "").strip().upper()
        clan_id = CLAN_CODE_TO_ID.get(code)
        clan = CLANS.get(clan_id) if clan_id else None
        if not clan:
            await send(player_id, {"type": "clan_error", "message": I18N.t("clan_code_not_found", p.language)})
            return
        if len(clan.members) >= S.CLAN_MAX_MEMBERS:
            await send(player_id, {"type": "clan_error", "message": I18N.t("clan_full", p.language)})
            return
        clan.members.add(player_id)
        p.clan_id = clan.id
        for mid in clan.members:
            if mid in PLAYERS:
                await send(mid, clan_payload(PLAYERS[mid]))
        return

    if t == "leave_clan":
        if not p.clan_id or p.clan_id not in CLANS:
            await send(player_id, {"type": "clan_error", "message": I18N.t("not_in_any_clan", p.language)})
            return
        clan = CLANS[p.clan_id]
        clan.members.discard(player_id)
        p.clan_id = None
        if not clan.members:
            CLANS.pop(clan.id, None)
            CLAN_CODE_TO_ID.pop(clan.code, None)
        elif clan.owner_id == player_id:
            clan.owner_id = next(iter(clan.members))
        await send(player_id, clan_payload(p))
        for mid in clan.members:
            if mid in PLAYERS:
                await send(mid, clan_payload(PLAYERS[mid]))
        return

    if t == "get_clan":
        await send(player_id, clan_payload(p))
        return

    # ---------------------------------------------------------- Phase 7: gift --

    if t == "send_gift":
        target_id = msg.get("playerId")
        amount = msg.get("amount")
        if target_id not in p.friends:
            await send(player_id, {"type": "gift_error", "message": I18N.t("gift_friends_only", p.language)})
            return
        target = PLAYERS.get(target_id)
        if not target:
            await send(player_id, {"type": "gift_error", "message": I18N.t("player_offline", p.language)})
            return
        error = S.can_send_gift(p.last_gift_date, p.wallet["coins"], amount)
        if error:
            await send(player_id, {"type": "gift_error", "message": error})
            return
        amount = int(amount)
        p.wallet["coins"] -= amount
        p.last_gift_date = S.today_str()
        target.wallet["coins"] += amount
        await send(player_id, {"type": "gift_sent", "playerId": target_id, "name": target.name, "amount": amount})
        await send(player_id, economy_payload(p))
        await send(target_id, {"type": "gift_received", "playerId": player_id, "name": p.name, "amount": amount})
        await send(target_id, economy_payload(target))
        return

    # ------------------------------------------------------- Phase 11 --

    if t == "get_stats":
        await send(player_id, stats_payload(p))
        return

    if t == "get_match_history":
        await send(player_id, match_history_payload(p))
        return

    if t == "get_replay":
        match = ST.find_match(p.match_history, msg.get("matchId"))
        await send(player_id, {"type": "replay", "match": match})
        return

    if t == "suggest_move":
        room = _get_room(p.room_id)
        if not room or room.phase != "playing" or room.turn != p.seat or p.seat not in room.human_seats():
            await send(player_id, {"type": "suggestion", "card": None, "reason": None})
            return
        hands_snapshot = {s: list(h) for s, h in room.hands.items()}
        trick_snapshot = list(room.current_trick)
        tricks_snapshot = dict(room.tricks_won)
        suggestion = await asyncio.to_thread(
            ST.suggest_move, hands_snapshot, trick_snapshot, room.trump, p.seat, tricks_snapshot,
        )
        await send(player_id, {"type": "suggestion", **suggestion})
        return

    if t == "get_stats_leaderboard":
        await send(player_id, leaderboard_payload(p))
        return

    # ---------------------------------------------------------- leaderboard --

    if t == "get_leaderboard":
        ranked = sorted(
            (pl for pl in PLAYERS.values() if pl.connected),
            key=lambda pl: pl.rr, reverse=True,
        )[:20]
        await send(player_id, {
            "type": "leaderboard",
            "players": [
                {"playerId": pl.id, "name": pl.name, "rr": pl.rr, "rank": R.rank_info(pl.rr)}
                for pl in ranked
            ],
        })
        return

    # ------------------------------------------------------- Phase 8: tournaments --

    if t == "list_tournaments":
        open_tours = [tr for tr in TOURNAMENTS.values() if tr.status == "registration"]
        await send(player_id, {
            "type": "tournament_list",
            "tournaments": [
                {"id": tr.id, "name": tr.name, "size": tr.size, "mode": tr.mode,
                 "joined": len(tr.participants), "status": tr.status}
                for tr in open_tours
            ],
        })
        return

    if t == "create_tournament":
        name, size, mode = msg.get("name"), msg.get("size"), msg.get("mode", "league")
        error = T.validate_new_tournament(name, size, mode)
        if error:
            await send(player_id, {"type": "tournament_error", "message": error})
            return
        tour_id = str(uuid.uuid4())
        tour = Tournament(id=tour_id, name=name.strip(), size=int(size), mode=mode, owner_id=player_id)
        tour.participants[player_id] = T.new_participant()
        TOURNAMENTS[tour_id] = tour
        p.active_tournament = tour_id
        await send(player_id, tournament_payload(tour))
        return

    if t == "join_tournament":
        tour = TOURNAMENTS.get(msg.get("tournamentId"))
        if not tour or tour.status != "registration":
            await send(player_id, {"type": "tournament_error", "message": I18N.t("tournament_not_open", p.language)})
            return
        if p.active_tournament:
            await send(player_id, {"type": "tournament_error", "message": I18N.t("already_in_tournament", p.language)})
            return
        if len(tour.participants) >= tour.size:
            await send(player_id, {"type": "tournament_error", "message": I18N.t("tournament_full", p.language)})
            return
        tour.participants[player_id] = T.new_participant()
        p.active_tournament = tour.id
        if len(tour.participants) >= tour.size:
            tour.status = "active"
        await broadcast_tournament(tour)
        return

    if t == "leave_tournament":
        tour = TOURNAMENTS.get(p.active_tournament) if p.active_tournament else None
        if tour and tour.status == "registration":
            tour.participants.pop(player_id, None)
            p.active_tournament = None
            if not tour.participants:
                TOURNAMENTS.pop(tour.id, None)
            await send(player_id, {"type": "tournament_state", "id": None, "standings": []})
        return

    if t == "start_tournament":
        tour = TOURNAMENTS.get(msg.get("tournamentId"))
        if tour and tour.owner_id == player_id and tour.status == "registration" and len(tour.participants) >= 2:
            tour.status = "active"
            await broadcast_tournament(tour)
        return

    if t == "get_tournament":
        tour = TOURNAMENTS.get(msg.get("tournamentId") or p.active_tournament)
        if tour:
            await send(player_id, tournament_payload(tour))
        return

    # --------------------------------------------------- Phase 12: language --

    if t == "set_language":
        p.language = I18N.normalize_lang(msg.get("lang"))
        await send(player_id, i18n_payload(p))
        await send(player_id, region_payload(p))
        return

    # ----------------------------------------------------- Phase 12: region --

    if t == "set_region":
        region = msg.get("region")
        if not REG.is_valid_region(region):
            await send(player_id, {"type": "region_error", "message": I18N.t("region_invalid", p.language)})
            return
        p.region = region
        await send(player_id, region_payload(p))
        return

    if t == "get_regional_leaderboard":
        region = REG.normalize_region(msg.get("region") or p.region)
        entries = leaderboard_entries()
        region_of = {pid: pl.region for pid, pl in PLAYERS.items()}
        top = REG.regional_leaderboard(entries, region_of, region)[:20]
        await send(player_id, {
            "type": "regional_leaderboard",
            "region": region,
            "top": [{**e, "rank": R.rank_info(e["rr"])} for e in top],
        })
        return

    # -------------------------------------------------- Phase 12: world cup --

    if t == "get_world_cup":
        await send(player_id, world_cup_payload(p))
        return

    if t == "join_world_cup":
        wc = CURRENT_WORLD_CUP
        if not WC.is_eligible(p.rr):
            await send(player_id, {"type": "world_cup_error", "message": I18N.t("worldcup_not_eligible", p.language)})
            return
        if wc.status != "registration":
            await send(player_id, {"type": "world_cup_error", "message": I18N.t("worldcup_not_registration", p.language)})
            return
        _, existing, _ = _find_world_cup_participant(player_id)
        if existing is not None:
            await send(player_id, {"type": "world_cup_error", "message": I18N.t("worldcup_already_joined", p.language)})
            return
        region = REG.normalize_region(msg.get("region") or p.region)
        wc.regions.setdefault(region, {})[player_id] = WC.new_participant()
        await send(player_id, world_cup_payload(p))
        await start_world_cup_qualifiers_if_ready()
        return


async def start_match_or_next_hand(room: Room):
    deal_hand(room, G.next_seat(room.hakem))
    await broadcast_state(room)
    await schedule_seat_decision(room, room.hakem, "trump")


@app.get("/")
async def root():
    """Serves the game page itself, so people open http://localhost:8000
    in a browser instead of double-clicking the HTML file. That matters:
    some browsers (Safari in particular, and some Chrome security modes)
    block or restrict WebSocket connections made from a page opened via
    file://, which silently breaks login with no error message. Serving
    the real page from the same origin the WebSocket connects to avoids
    that entirely, and is also just the normal way to run a web app."""
    return FileResponse(os.path.join(_STATIC_DIR, "hokm-phase4-online.html"))


@app.get("/status")
async def status():
    return {"status": "ok", "rooms": len(ROOMS), "queue": len(MM_QUEUE)}


# The HTML pulls these in with plain relative <script src="..."> tags,
# so serving each at the matching top-level path is all that's needed —
# no changes to the HTML itself. Listed explicitly (rather than mounting
# the whole directory as static) so server.py's source and hokm.db never
# become downloadable by anyone who guesses the filename.
for _panel_file in (
    "economy-panel.js", "social-panel.js", "tournament-panel.js",
    "monetization-panel.js", "stats-panel.js", "worldcup-panel.js",
    "achievements-panel.js", "voice-panel.js",
):
    def _make_panel_route(filename):
        async def _serve():
            return FileResponse(os.path.join(_STATIC_DIR, filename))
        return _serve
    app.get(f"/{_panel_file}")(_make_panel_route(_panel_file))


@app.get("/pay/callback")
async def pay_callback(Authority: str = "", Status: str = ""):
    """Zarinpal redirects the buyer's browser here after they finish (or
    cancel) paying. This is the ONLY place a purchase actually gets
    granted — confirmed server-to-server via PAY.verify_payment, not
    trusted off anything the client claims."""
    from fastapi.responses import HTMLResponse

    pending = PENDING_PAYMENTS.pop(Authority, None)
    if not pending:
        return HTMLResponse("<h2>پرداخت یافت نشد یا قبلاً پردازش شده.</h2>")
    if Status != "OK":
        return HTMLResponse("<h2>پرداخت لغو شد. به بازی برگرد و دوباره تلاش کن.</h2>")
    if PAY.is_expired(pending["created_at"]):
        return HTMLResponse("<h2>مهلت این پرداخت تمام شده.</h2>")

    result = PAY.verify_payment(Authority, pending["amount_toman"])
    p = PLAYERS.get(pending["player_id"])
    if not result.get("ok") or not p:
        return HTMLResponse(f"<h2>تایید پرداخت ناموفق بود: {result.get('error')}</h2>")

    if pending["kind"] == "vip":
        grant = M.apply_vip_purchase(p.vip_until, pending["item_id"])
        if grant.get("ok"):
            p.vip_until = grant["vipUntil"]
            await send(pending["player_id"], {"type": "buy_vip_result", **grant})
            await send(pending["player_id"], monetization_payload(p))
    elif pending["kind"] == "gems":
        grant = M.grant_gem_pack(p.wallet, pending["item_id"])
        if grant.get("ok"):
            await send(pending["player_id"], {"type": "buy_gem_pack_result", **grant})
            await send(pending["player_id"], economy_payload(p))
    save_player(p)
    return HTMLResponse(f"<h2>پرداخت موفق ✅ (کد پیگیری: {result.get('ref_id')})</h2><p>می‌تونی این تب رو ببندی و به بازی برگردی.</p>")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    player_id = None
    try:
        first_raw = await ws.receive_text()
        first = json.loads(first_raw)
        # Phase 12 — first message may carry the client's language pref
        # (from localStorage) so even pre-login errors come back localized.
        pre_lang = I18N.normalize_lang(first.get("lang") or I18N.DEFAULT_LANG)

        if first.get("type") == "reconnect":
            client_ip = ws.client.host if ws.client else "unknown"
            if SEC.is_reconnect_locked_out(RECONNECT_FAILS.get(client_ip, [])):
                await ws.send_text(json.dumps({"type": "error", "message": I18N.t("too_many_reconnect_fails", pre_lang)}))
                await ws.close()
                return
            token = first.get("session_token")
            verified_player_id, expired = AUTH.verify_session_token(token)
            if expired:
                player_id = None
            else:
                # Either a genuine unexpired JWT, or a legacy pre-JWT
                # random token issued before this upgrade — both are safe
                # to resolve via the dict: a legacy token only matches if
                # it's the exact random value we originally handed out,
                # same security property JWT verification adds
                # cryptographically for new tokens. This player's *next*
                # login/reconnect gets a real JWT (see the login_ok
                # branches below), so the fallback naturally disappears.
                player_id = SESSION_TO_PLAYER.get(token)
            p = PLAYERS.get(player_id) if player_id else None
            if not p:
                RECONNECT_FAILS[client_ip] = SEC.record_failed_reconnect(RECONNECT_FAILS.get(client_ip, []))
                error_key = "session_expired" if expired else "session_not_found"
                await ws.send_text(json.dumps({"type": "error", "message": I18N.t(error_key, pre_lang)}))
                await ws.close()
                return
            p.ws = ws
            p.connected = True
            if verified_player_id is None:
                # This session reconnected with a legacy pre-JWT token —
                # upgrade it to a real signed JWT now so it (and every
                # reconnect after this one) is cryptographically verifiable
                # going forward, same as any session issued by the current
                # login code.
                new_token = AUTH.issue_session_token(player_id)
                SESSION_TO_PLAYER.pop(token, None)
                SESSION_TO_PLAYER[new_token] = player_id
                p.session_token = new_token
                save_player(p)
            season_change = check_season(p)
            missions_refreshed = check_daily_missions(p)
            maybe_reset_world_cup()
            await send(player_id, {"type": "login_ok", "player_id": p.id, "session_token": p.session_token, "name": p.name, "rank": R.rank_info(p.rr)})
            if season_change:
                await send(player_id, {"type": "season_reset", **season_change})
            await send(player_id, economy_payload(p))
            await send(player_id, clan_payload(p))
            check_bp_season(p)
            await send(player_id, monetization_payload(p))
            await send(player_id, stats_payload(p))
            await send(player_id, match_history_payload(p))
            await send(player_id, i18n_payload(p))
            await send(player_id, region_payload(p))
            await send(player_id, world_cup_payload(p))
            await send(player_id, achievements_payload(p))
            room = _get_room(p.room_id) if p.room_id else None
            if room:
                async with RT.room_lock(room):
                    await broadcast_state(room)
            else:
                await send(player_id, {"type": "screen", "name": "lobby"})

        elif first.get("type") == "login":
            name = (first.get("name") or "").strip() or f"مهمان{random.randint(1000, 9999)}"
            player_id = str(uuid.uuid4())
            token = AUTH.issue_session_token(player_id)
            language = pre_lang
            region = REG.normalize_region(first.get("region") or REG.DEFAULT_REGION)
            PLAYERS[player_id] = Player(id=player_id, session_token=token, name=name, ws=ws, connected=True,
                                         language=language, region=region)
            SESSION_TO_PLAYER[token] = player_id
            p = PLAYERS[player_id]
            save_player(p)
            check_daily_missions(p)
            maybe_reset_world_cup()
            await send(player_id, {"type": "login_ok", "player_id": player_id, "session_token": token, "name": name, "rank": R.rank_info(p.rr)})
            await send(player_id, economy_payload(p))
            await send(player_id, clan_payload(p))
            check_bp_season(p)
            await send(player_id, monetization_payload(p))
            await send(player_id, stats_payload(p))
            await send(player_id, match_history_payload(p))
            await send(player_id, i18n_payload(p))
            await send(player_id, region_payload(p))
            await send(player_id, world_cup_payload(p))
            await send(player_id, achievements_payload(p))
            await send(player_id, {"type": "screen", "name": "lobby"})

        elif first.get("type") == "login_google":
            if not AUTH.is_configured():
                await ws.send_text(json.dumps({"type": "error", "message": I18N.t("google_login_not_configured", pre_lang)}))
                await ws.close()
                return
            claims = AUTH.verify_google_id_token(first.get("id_token") or "")
            if not claims:
                await ws.send_text(json.dumps({"type": "error", "message": I18N.t("google_login_failed", pre_lang)}))
                await ws.close()
                return
            google_id = claims["sub"]
            existing_player_id = GOOGLE_TO_PLAYER.get(google_id)
            if existing_player_id and existing_player_id in PLAYERS:
                # Same Google account seen before — resume that player's real
                # progress, even though this is a brand-new browser/device
                # with no session_token in localStorage.
                player_id = existing_player_id
                p = PLAYERS[player_id]
                token = AUTH.issue_session_token(player_id)
                p.session_token = token
                p.ws = ws
                p.connected = True
                SESSION_TO_PLAYER[token] = player_id
                season_change = check_season(p)
                check_daily_missions(p)
            else:
                player_id = str(uuid.uuid4())
                token = AUTH.issue_session_token(player_id)
                p = Player(id=player_id, session_token=token, name=claims["name"], ws=ws, connected=True,
                           language=pre_lang, region=REG.normalize_region(first.get("region") or REG.DEFAULT_REGION),
                           google_id=google_id, email=claims.get("email"))
                PLAYERS[player_id] = p
                SESSION_TO_PLAYER[token] = player_id
                GOOGLE_TO_PLAYER[google_id] = player_id
                season_change = None
                check_daily_missions(p)
            save_player(p)
            maybe_reset_world_cup()
            await send(player_id, {"type": "login_ok", "player_id": player_id, "session_token": token, "name": p.name, "rank": R.rank_info(p.rr)})
            if season_change:
                await send(player_id, {"type": "season_reset", **season_change})
            await send(player_id, economy_payload(p))
            await send(player_id, clan_payload(p))
            check_bp_season(p)
            await send(player_id, monetization_payload(p))
            await send(player_id, stats_payload(p))
            await send(player_id, match_history_payload(p))
            await send(player_id, i18n_payload(p))
            await send(player_id, region_payload(p))
            await send(player_id, world_cup_payload(p))
            await send(player_id, achievements_payload(p))
            await send(player_id, {"type": "screen", "name": "lobby"})

        else:
            await ws.send_text(json.dumps({"type": "error", "message": I18N.t("must_login_first", pre_lang)}))
            await ws.close()
            return

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            await handle_message(player_id, msg)

    except WebSocketDisconnect:
        pass
    finally:
        if player_id and player_id in PLAYERS:
            p = PLAYERS[player_id]
            p.connected = False
            p.ws = None
            save_player(p)
            if player_id in MM_QUEUE:
                MM_QUEUE.remove(player_id)
            room = _get_room(p.room_id) if p.room_id else None
            if room:
                await voice_remove(room, player_id)
                if player_id in room.spectators:
                    room.spectators.discard(player_id)
                elif room.phase == "waiting":
                    if room.seats.get("south") == player_id:
                        if room.code:
                            CODE_TO_ROOM.pop(room.code, None)
                        ROOMS.pop(room.id, None)
                        for s, pid in room.seats.items():
                            if pid and pid != "bot" and pid != player_id and PLAYERS.get(pid):
                                PLAYERS[pid].room_id, PLAYERS[pid].seat = None, None
                                await send(pid, {"type": "error", "message": I18N.t("room_host_left", PLAYERS[pid].language)})
                                await send(pid, {"type": "screen", "name": "lobby"})
                    else:
                        for s, pid in list(room.seats.items()):
                            if pid == player_id:
                                room.seats[s] = None
                        await broadcast_room_wait(room)
                else:
                    async with RT.room_lock(room):
                        if p.seat:
                            await maybe_cover_pending_decision(room, p.seat)
                        await broadcast_state(room)