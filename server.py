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

Run locally:
    pip install -r requirements.txt --break-system-packages
    uvicorn server:app --reload --port 8000

Then point the client (see hokm-phase4-online.html) at
ws://localhost:8000/ws
"""

import asyncio
import datetime
import json
import os
import random
import string
import uuid
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import hokm_game as G
import hokm_ranks as R
import hokm_economy as E
import hokm_social as S
import hokm_tournament as T

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

GRACE_SECONDS = float(os.environ.get("HOKM_GRACE_SECONDS", 20))          # how long we wait for a disconnected human before a bot covers their turn
BOT_THINK_SECONDS = float(os.environ.get("HOKM_BOT_THINK_SECONDS", 1.1))  # cosmetic delay so bot moves don't feel instant
TRICK_RESOLVE_DELAY = float(os.environ.get("HOKM_TRICK_RESOLVE_DELAY", 1.3))  # time the "who won the trick" highlight stays up

SEAT_HUMANS = ["south", "north"]                 # the 2 real-player seats in this MVP
SEAT_BOTS = {"west": "امیر", "east": "رضا"}       # bot display names, matching the original client


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


PLAYERS: dict[str, Player] = {}
SESSION_TO_PLAYER: dict[str, str] = {}
MM_QUEUE: list[str] = []          # player_ids waiting for quick match
ROOMS: dict[str, "Room"] = {}
CODE_TO_ROOM: dict[str, str] = {}
CLANS: dict[str, Clan] = {}
CLAN_CODE_TO_ID: dict[str, str] = {}
TOURNAMENTS: dict[str, Tournament] = {}


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

    # Phase 7 — social
    spectators: set = field(default_factory=set)  # player_ids watching, no seat
    chat_log: list = field(default_factory=list)   # last 50 chat/emoji events

    def seat_of(self, player_id: str) -> Optional[str]:
        for seat, pid in self.seats.items():
            if pid == player_id:
                return seat
        return None

    def human_seat_ids(self):
        return {s: pid for s, pid in self.seats.items() if pid != "bot"}

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
    partner = ("north" if viewer_seat == "south" else "south") if viewer_seat in SEAT_HUMANS else None
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
        "partnerConnected": room.is_seat_connected(partner) if partner in SEAT_HUMANS else True,
    }


async def broadcast_state(room: Room):
    await broadcast_room(room, lambda seat: state_for(room, seat))


async def broadcast_toast(room: Room, message: str):
    await broadcast_room(room, lambda seat: {"type": "toast", "message": message})


async def broadcast_chat(room: Room, event: dict):
    room.chat_log.append(event)
    room.chat_log[:] = room.chat_log[-50:]
    await broadcast_room(room, lambda seat: {"type": "chat", **event})


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
    async with room.lock:
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


async def _do_play_card(room: Room, seat: str, card: dict):
    hand = room.hands[seat]
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
    async with room.lock:
        if room.turn_token != token:
            return
        team = G.TEAM[winner_seat]
        room.tricks_won[team] += 1

        # Phase 6: credit the human(s) on the winning team with a trick,
        # and the hakem (if human) with a "won a trick while hakem" tick.
        for seat in SEAT_HUMANS:
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

            was_sur = room.tricks_won[winner_team] == 7 and room.tricks_won["A" if winner_team == "B" else "B"] == 0
            if was_sur:
                for seat in SEAT_HUMANS:
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
    """South+north are always the two real players (partnered as team A;
    west/east bots are team B), so both humans win or lose together.
    Updates each connected human's RR *and* their economy wallet/missions,
    and tells them what changed."""
    won = winner_team == "A"
    for seat in SEAT_HUMANS:
        pid = room.seats.get(seat)
        p = PLAYERS.get(pid) if pid else None
        if not p:
            continue

        # Phase 5 — rank
        rank_result = R.apply_result(p.rr, won, win_streak=p.win_streak)
        p.rr = rank_result["rr"]
        p.win_streak = p.win_streak + 1 if won else 0
        await send(pid, {"type": "rank_update", **rank_result})

        # Phase 6 — economy: match reward, "played"/"win" missions, XP/level
        reward = E.match_reward(won, win_streak=p.win_streak)
        p.wallet["coins"] += reward["coins"]
        p.wallet["gems"] += reward["gems"]
        xp_result = E.add_xp(p.wallet["xp"], p.wallet["level"], reward["xp"])
        p.wallet.update(xp_result)
        E.bump_mission_progress(p.missions, "played", 1)
        if won:
            E.bump_mission_progress(p.missions, "wins", 1)

        await send(pid, {
            "type": "economy_update",
            "reason": "match_end",
            "reward": reward,
            "leveledUp": xp_result["levelsGained"] > 0,
            "wallet": p.wallet,
            "missions": p.missions,
        })

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
    hakem = random.choice(G.SEATS)
    deal_hand(room, hakem)
    room.phase = "choosing-trump"
    await broadcast_state(room)
    await schedule_seat_decision(room, hakem, "trump")


# --------------------------------------------------------- room lifecycle --

async def start_game_between(p1: str, p2: str):
    room = Room(id=str(uuid.uuid4()), seats={"south": p1, "north": p2, "west": "bot", "east": "bot"})
    ROOMS[room.id] = room
    for pid, seat in ((p1, "south"), (p2, "north")):
        PLAYERS[pid].room_id = room.id
        PLAYERS[pid].seat = seat
    async with room.lock:
        await start_match(room)


async def try_match_queue():
    while len(MM_QUEUE) >= 2:
        p1 = MM_QUEUE.pop(0)
        p2 = MM_QUEUE.pop(0)
        if not (PLAYERS.get(p1) and PLAYERS[p1].connected):
            continue
        if not (PLAYERS.get(p2) and PLAYERS[p2].connected):
            MM_QUEUE.insert(0, p2)
            continue
        await start_game_between(p1, p2)


# ------------------------------------------------------------- ws handler --

async def handle_message(player_id: str, msg: dict):
    p = PLAYERS[player_id]
    t = msg.get("type")

    if t == "quick_match":
        if player_id not in MM_QUEUE:
            MM_QUEUE.append(player_id)
        await send(player_id, {"type": "screen", "name": "matchmaking"})
        await try_match_queue()
        return

    if t == "cancel_matchmaking":
        if player_id in MM_QUEUE:
            MM_QUEUE.remove(player_id)
        await send(player_id, {"type": "screen", "name": "lobby"})
        return

    if t == "create_room":
        code = new_code()
        room = Room(id=str(uuid.uuid4()), code=code, seats={"south": player_id, "north": None, "west": "bot", "east": "bot"})
        ROOMS[room.id] = room
        CODE_TO_ROOM[code] = room.id
        p.room_id, p.seat = room.id, "south"
        await send(player_id, {"type": "room_wait", "code": code, "friendJoined": False})
        return

    if t == "join_room":
        code = (msg.get("code") or "").strip().upper()
        room_id = CODE_TO_ROOM.get(code)
        room = ROOMS.get(room_id) if room_id else None
        if not room or room.seats.get("north") not in (None,):
            await send(player_id, {"type": "error", "message": "کد اتاق نامعتبره یا اتاق پره"})
            return
        room.seats["north"] = player_id
        p.room_id, p.seat = room.id, "north"
        host_id = room.seats["south"]
        await send(host_id, {"type": "room_wait", "code": code, "friendJoined": True})
        await send(player_id, {"type": "room_wait", "code": code, "friendJoined": True})
        async with room.lock:
            await start_match(room)
        return

    if t == "leave_room":
        room = ROOMS.get(p.room_id)
        if room and room.phase == "waiting" and room.code:
            CODE_TO_ROOM.pop(room.code, None)
            ROOMS.pop(room.id, None)
        p.room_id, p.seat = None, None
        await send(player_id, {"type": "screen", "name": "lobby"})
        return

    if t == "choose_trump":
        room = ROOMS.get(p.room_id)
        if not room or p.seat != room.hakem or room.phase != "choosing-trump":
            return
        suit = msg.get("suit")
        if suit not in G.SUIT_ORDER:
            return
        async with room.lock:
            await _do_choose_trump(room, p.seat, suit)
        return

    if t == "play_card":
        room = ROOMS.get(p.room_id)
        if not room or room.turn != p.seat or room.phase != "playing":
            return
        card = msg.get("card") or {}
        hand = room.hands.get(p.seat, [])
        match = next((c for c in hand if c["suit"] == card.get("suit") and c["rank"] == card.get("rank")), None)
        if not match:
            return
        async with room.lock:
            if not G.is_legal_play(hand, room.current_trick, match):
                await send(player_id, {"type": "toast", "message": "باید همخال بازی کنید"})
                return
            await _do_play_card(room, p.seat, match)
        return

    if t == "next_hand":
        room = ROOMS.get(p.room_id)
        if not room or room.phase != "hand-end" or p.seat not in ("south", "north"):
            return
        async with room.lock:
            await start_match_or_next_hand(room)
        return

    if t == "new_match":
        room = ROOMS.get(p.room_id)
        if not room or room.phase != "match-end" or p.seat not in ("south", "north"):
            return
        async with room.lock:
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

    # ---------------------------------------------------------- Phase 7 --

    if t == "spectate_room":
        code = (msg.get("code") or "").strip().upper()
        room_id = CODE_TO_ROOM.get(code)
        room = ROOMS.get(room_id) if room_id else None
        if not room:
            await send(player_id, {"type": "error", "message": "اتاقی با این کد پیدا نشد"})
            return
        room.spectators.add(player_id)
        p.room_id, p.seat = room.id, None
        await send(player_id, state_for(room, None))
        await broadcast_toast(room, f"{p.name} به عنوان تماشاگر پیوست")
        return

    if t == "leave_spectate":
        room = ROOMS.get(p.room_id)
        if room:
            room.spectators.discard(player_id)
        p.room_id = None
        await send(player_id, {"type": "screen", "name": "lobby"})
        return

    if t == "chat_message":
        room = ROOMS.get(p.room_id)
        if not room:
            return
        text = (msg.get("text") or "").strip()
        if not text or len(text) > MAX_CHAT_LEN:
            return
        await broadcast_chat(room, {"kind": "text", "from": p.name, "seat": p.seat, "text": text})
        return

    if t == "quick_chat":
        room = ROOMS.get(p.room_id)
        if not room:
            return
        idx = msg.get("phraseIndex")
        if not isinstance(idx, int) or not (0 <= idx < len(QUICK_CHAT_PHRASES)):
            return
        await broadcast_chat(room, {"kind": "text", "from": p.name, "seat": p.seat, "text": QUICK_CHAT_PHRASES[idx]})
        return

    if t == "emoji":
        room = ROOMS.get(p.room_id)
        if not room:
            return
        emoji = (msg.get("emoji") or "")[:8]
        if not emoji:
            return
        await broadcast_chat(room, {"kind": "emoji", "from": p.name, "seat": p.seat, "emoji": emoji})
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
            await send(player_id, {"type": "clan_error", "message": "قبلاً عضو یک باشگاه هستی"})
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
            await send(player_id, {"type": "clan_error", "message": "اول باید از باشگاه فعلی خارج شوی"})
            return
        code = (msg.get("code") or "").strip().upper()
        clan_id = CLAN_CODE_TO_ID.get(code)
        clan = CLANS.get(clan_id) if clan_id else None
        if not clan:
            await send(player_id, {"type": "clan_error", "message": "کد باشگاه پیدا نشد"})
            return
        if len(clan.members) >= S.CLAN_MAX_MEMBERS:
            await send(player_id, {"type": "clan_error", "message": "این باشگاه پر است"})
            return
        clan.members.add(player_id)
        p.clan_id = clan.id
        for mid in clan.members:
            if mid in PLAYERS:
                await send(mid, clan_payload(PLAYERS[mid]))
        return

    if t == "leave_clan":
        if not p.clan_id or p.clan_id not in CLANS:
            await send(player_id, {"type": "clan_error", "message": "عضو هیچ باشگاهی نیستی"})
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
            await send(player_id, {"type": "gift_error", "message": "فقط می‌تونی به دوستانت هدیه بدی"})
            return
        target = PLAYERS.get(target_id)
        if not target:
            await send(player_id, {"type": "gift_error", "message": "این بازیکن آنلاین نیست"})
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
            await send(player_id, {"type": "tournament_error", "message": "این تورنمنت برای ثبت‌نام باز نیست"})
            return
        if p.active_tournament:
            await send(player_id, {"type": "tournament_error", "message": "همین الان در یک تورنمنت دیگر هستی"})
            return
        if len(tour.participants) >= tour.size:
            await send(player_id, {"type": "tournament_error", "message": "تورنمنت پر است"})
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


async def start_match_or_next_hand(room: Room):
    deal_hand(room, G.next_seat(room.hakem))
    await broadcast_state(room)
    await schedule_seat_decision(room, room.hakem, "trump")


@app.get("/")
async def root():
    return {"status": "ok", "rooms": len(ROOMS), "queue": len(MM_QUEUE)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    player_id = None
    try:
        first_raw = await ws.receive_text()
        first = json.loads(first_raw)

        if first.get("type") == "reconnect":
            token = first.get("session_token")
            player_id = SESSION_TO_PLAYER.get(token)
            p = PLAYERS.get(player_id) if player_id else None
            if not p:
                await ws.send_text(json.dumps({"type": "error", "message": "نشست پیدا نشد، لطفاً دوباره وارد شو"}))
                await ws.close()
                return
            p.ws = ws
            p.connected = True
            season_change = check_season(p)
            missions_refreshed = check_daily_missions(p)
            await send(player_id, {"type": "login_ok", "player_id": p.id, "session_token": p.session_token, "name": p.name, "rank": R.rank_info(p.rr)})
            if season_change:
                await send(player_id, {"type": "season_reset", **season_change})
            await send(player_id, economy_payload(p))
            await send(player_id, clan_payload(p))
            room = ROOMS.get(p.room_id) if p.room_id else None
            if room:
                async with room.lock:
                    await broadcast_state(room)
            else:
                await send(player_id, {"type": "screen", "name": "lobby"})

        elif first.get("type") == "login":
            name = (first.get("name") or "").strip() or f"مهمان{random.randint(1000, 9999)}"
            player_id = str(uuid.uuid4())
            token = str(uuid.uuid4())
            PLAYERS[player_id] = Player(id=player_id, session_token=token, name=name, ws=ws, connected=True)
            SESSION_TO_PLAYER[token] = player_id
            p = PLAYERS[player_id]
            check_daily_missions(p)
            await send(player_id, {"type": "login_ok", "player_id": player_id, "session_token": token, "name": name, "rank": R.rank_info(p.rr)})
            await send(player_id, economy_payload(p))
            await send(player_id, clan_payload(p))
            await send(player_id, {"type": "screen", "name": "lobby"})

        else:
            await ws.send_text(json.dumps({"type": "error", "message": "لطفاً ابتدا وارد شو"}))
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
            if player_id in MM_QUEUE:
                MM_QUEUE.remove(player_id)
            room = ROOMS.get(p.room_id) if p.room_id else None
            if room:
                if player_id in room.spectators:
                    room.spectators.discard(player_id)
                elif room.phase == "waiting":
                    if room.code:
                        CODE_TO_ROOM.pop(room.code, None)
                    ROOMS.pop(room.id, None)
                else:
                    async with room.lock:
                        if p.seat:
                            await maybe_cover_pending_decision(room, p.seat)
                        await broadcast_state(room)
