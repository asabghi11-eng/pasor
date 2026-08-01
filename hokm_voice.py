"""
hokm_voice.py — voice chat (چت صوتی), the "voice-chat" item from the
remaining-work list.

Honest note on architecture, up front:
A Hokm room only ever has up to 4 human seats + a handful of spectators.
For a group that small, a full SFU (Selective Forwarding Unit — a media
server that every participant's audio flows *through*) is more
infrastructure than the problem needs. What this module implements
instead is **mesh WebRTC**: every participant opens a direct
peer-to-peer RTCPeerConnection with every other participant (at most
4 people online at once = 6 connections total), and audio flows
browser-to-browser, never through this server. server.py's only job
is *signaling* — relaying the SDP offers/answers and ICE candidates
that two browsers need to exchange before they can find each other —
which is exactly what the new voice_join / voice_leave / voice_signal
websocket messages in server.py do. This module holds the small
amount of pure logic around that: which ICE servers to hand the
client, and validating that a signaling payload is actually a
signaling payload before the server relays it to a stranger's browser.

STUN vs. TURN (why this matters for Iranian users specifically):
STUN just tells a browser its own public IP:port so two peers *behind
ordinary NATs* can connect directly — that's free, and Google's public
STUN servers (used below) are enough for most home/office networks.
TURN is different: it's a relay server that forwards the actual audio
when direct connection fails outright (common on carrier-grade NAT,
which a lot of mobile networks use, Iranian mobile carriers included).
TURN isn't free to run at scale (it's paying for someone's bandwidth),
so it's not something this module can respond with out of the box —
it's genuinely an infrastructure decision for whoever deploys this
server. What this module DOES do: if you set HOKM_TURN_URL (+
HOKM_TURN_USERNAME + HOKM_TURN_CREDENTIAL) as environment variables —
pointing at any standard TURN server (coturn is the common
self-hosted option; Twilio/Xirsys/Cloudflare also sell hosted TURN by
the GB) — it's automatically added to the ICE server list sent to
every client. Without it, voice chat still works for most players,
just not the ones stuck behind the strictest NATs.

Pure functions only (no I/O, no globals) — server.py owns
Room.voice_participants and calls into this module to build the ICE
server list and validate signaling payloads before relaying them.
"""

import os

# ------------------------------------------------------------- ICE servers --

_PUBLIC_STUN_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
]


def ice_servers() -> list:
    """STUN servers always included; a TURN server is added on top if
    the deployer configured one via environment variables. Sent to the
    client fresh on every voice_join, so changing the env vars and
    restarting the server is enough to roll out a new TURN server —
    no client update needed."""
    servers = list(_PUBLIC_STUN_SERVERS)
    turn_url = os.environ.get("HOKM_TURN_URL", "").strip()
    if turn_url:
        entry = {"urls": turn_url}
        username = os.environ.get("HOKM_TURN_USERNAME", "").strip()
        credential = os.environ.get("HOKM_TURN_CREDENTIAL", "").strip()
        if username:
            entry["username"] = username
        if credential:
            entry["credential"] = credential
        servers.append(entry)
    return servers


# --------------------------------------------------------- room capacity --

# A Hokm room has 4 seats + spectators, but voice is capped independently
# of seating so a room that somehow accumulated a lot of spectators can't
# turn into an unbounded mesh (6 connections at 4 people is already the
# most any single peer has to maintain; this is a hard safety ceiling,
# not a normal-case limit).
MAX_VOICE_PARTICIPANTS_PER_ROOM = 8


# ------------------------------------------------------ signal validation --

# Generous but bounded — a real SDP offer/answer is typically a few KB;
# ICE candidates are a single short line. This isn't a codec-aware
# check (this server never parses SDP, on purpose — it's just a
# pipe), just a sanity ceiling so the signaling channel can't be used
# to shove arbitrary large payloads at another player's browser.
MAX_SIGNAL_PAYLOAD_CHARS = 20_000

_ALLOWED_SIGNAL_TYPES = {"offer", "answer", "candidate"}


def validate_signal(signal) -> bool:
    """True if `signal` looks like a well-formed WebRTC signaling
    message worth relaying as-is. server.py never inspects the SDP
    contents itself — this is deliberately a shape/size check, not a
    semantic one; the two browsers negotiate the actual media."""
    if not isinstance(signal, dict):
        return False
    kind = signal.get("type")
    if kind not in _ALLOWED_SIGNAL_TYPES:
        return False
    if len(str(signal)) > MAX_SIGNAL_PAYLOAD_CHARS:
        return False
    if kind in ("offer", "answer"):
        return isinstance(signal.get("sdp"), str) and bool(signal["sdp"])
    if kind == "candidate":
        # candidate itself may legitimately be None (end-of-candidates
        # signal) — only reject if the key is missing entirely/wrong type.
        return "candidate" in signal
    return False
