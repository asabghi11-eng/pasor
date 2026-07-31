"""
Hokm security & anti-cheat — Phase 9.

Honest note on scope: this backend is an in-memory MVP with no real
accounts yet (login is just a display name; session_token is the de
facto credential) and no database. That shapes which phase-9 items
apply now vs. later:

  - رمزنگاری (encryption): there's no secret at rest to encrypt —
    session tokens live only in the PLAYERS dict in memory, never
    touch disk. The security work that actually matters *today* is
    (a) always deploying behind TLS (wss://, terminated by the reverse
    proxy or uvicorn's --ssl-* flags in production) so tokens can't be
    sniffed in transit, and (b) making the token itself hard to
    brute-force, which is what `reconnect lockout` below is for. Once
    real accounts + a database exist, password hashing (argon2/bcrypt)
    belongs here too.

  - Anti Cheat: the game is already server-authoritative — dealing,
    legal-play checks and scoring all happen in hokm_game.py on the
    server and are never trusted from the client. That predates this
    file and remains the single biggest anti-cheat win a card game can
    have. What this file adds on top is message-rate throttling: no
    client, human or scripted, has a legitimate reason to send dozens
    of messages a second.

  - تشخیص ربات (bot/abuse detection): gameplay skill alone can't prove
    "this is a bot" — a strong human and a strong script look the same
    on that axis. What a rate limiter *can* catch is the actual abuse
    pattern that matters here: message flooding, whether it comes from
    a script or a broken client.

  - گزارش بازیکن (player reports): players can report a bad actor;
    enough distinct reports against the same target in a short window
    trigger an automatic temporary chat mute, so abuse doesn't have to
    wait on a human moderator before something happens.

Pure functions only (no I/O, no globals) — server.py owns the
Player.action_log / mute_until / reports_received fields and the
module-level reconnect-attempt dict, and calls into this module to
decide what to do with them.
"""

import time

# ------------------------------------------------------------ rate limit --

ACTION_WINDOW_SECONDS = 10
ACTION_MAX_IN_WINDOW = 25   # ~2.5 actions/sec sustained is already generous for a card game


def check_rate_limit(timestamps: list, now: float = None) -> tuple:
    """timestamps: past action unix-times for one player (any order).
    Returns (allowed, updated_timestamps) — caller stores the returned
    list back onto the player, replacing the old one."""
    now = now if now is not None else time.time()
    cutoff = now - ACTION_WINDOW_SECONDS
    recent = [t for t in timestamps if t > cutoff]
    allowed = len(recent) < ACTION_MAX_IN_WINDOW
    if allowed:
        recent.append(now)
    return allowed, recent


# ------------------------------------------------------- reconnect lockout --
# Protects the session_token itself (the app's only credential) against
# an attacker guessing tokens by hammering {"type": "reconnect"}.

RECONNECT_FAIL_WINDOW_SECONDS = 300
RECONNECT_FAIL_MAX = 8            # 8 wrong tokens in 5 minutes from one IP -> locked out


def record_failed_reconnect(timestamps: list, now: float = None) -> list:
    now = now if now is not None else time.time()
    cutoff = now - RECONNECT_FAIL_WINDOW_SECONDS
    recent = [t for t in timestamps if t > cutoff]
    recent.append(now)
    return recent


def is_reconnect_locked_out(timestamps: list, now: float = None) -> bool:
    now = now if now is not None else time.time()
    cutoff = now - RECONNECT_FAIL_WINDOW_SECONDS
    recent = [t for t in timestamps if t > cutoff]
    return len(recent) >= RECONNECT_FAIL_MAX


# ------------------------------------------------------------- reports --

REPORT_REASONS = ("cheating", "abusive_chat", "afk", "smurfing", "other")
REPORT_DEDUPE_SECONDS = 3600     # same reporter -> same target counts once per hour
REPORT_WINDOW_SECONDS = 3600
REPORT_MUTE_THRESHOLD = 3        # distinct reporters within the window
AUTO_MUTE_SECONDS = 900          # 15 minutes


def validate_report(reason: str, target_id: str, reporter_id: str) -> str:
    """Returns an error message in Persian, or '' if the report is fine."""
    if not target_id:
        return "بازیکن هدف مشخص نیست"
    if target_id == reporter_id:
        return "نمی‌تونی خودت رو گزارش کنی"
    if reason not in REPORT_REASONS:
        return "دلیل گزارش نامعتبر است"
    return ""


def add_report(reports: list, reporter_id: str, reason: str, now: float = None) -> dict:
    """reports: list of {"reporterId", "reason", "ts"} against one
    target player. Appends the new report (deduping repeats from the
    same reporter within REPORT_DEDUPE_SECONDS) and reports back
    whether this should trigger an auto-mute.

    Returns {"reports": <updated list>, "shouldMute": bool, "reporterCount": int}.
    """
    now = now if now is not None else time.time()
    recent_from_reporter = [
        r for r in reports
        if r["reporterId"] == reporter_id and now - r["ts"] < REPORT_DEDUPE_SECONDS
    ]
    if not recent_from_reporter:
        reports = reports + [{"reporterId": reporter_id, "reason": reason, "ts": now}]
    window_reports = [r for r in reports if now - r["ts"] < REPORT_WINDOW_SECONDS]
    distinct_reporters = {r["reporterId"] for r in window_reports}
    return {
        "reports": reports,
        "shouldMute": len(distinct_reporters) >= REPORT_MUTE_THRESHOLD,
        "reporterCount": len(distinct_reporters),
    }


def is_muted(mute_until: float, now: float = None) -> bool:
    now = now if now is not None else time.time()
    return bool(mute_until) and mute_until > now
