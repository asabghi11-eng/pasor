"""
hokm_auth.py — real Google Sign-In, server-side verification only.

server.py already had the calling code for this (the `login_google`
branch of the websocket handler) but the module itself was missing
from the project, so the server couldn't even start (ImportError on
`import hokm_auth as AUTH`). This file fills that gap.

How it works, honestly stated:
  - The BROWSER does the actual Google sign-in (Google Identity
    Services JS, loaded from Google's site) and gets back a signed
    "ID token" (a JWT) from Google — this file never sees a password,
    because there isn't one; Google owns that.
  - The browser sends that ID token to us over the websocket
    ({"type": "login_google", "id_token": "..."}).
  - `verify_google_id_token` asks Google's own library to check the
    token's signature against Google's public keys and its audience
    (aud) against OUR client ID. If that passes, the claims (sub,
    email, name, ...) are genuine and came from Google — we're not
    trusting anything the client asserted about itself.

Setup (free, no cost, ~10 minutes):
  1. https://console.cloud.google.com/ → create a project (or reuse
     one) → "APIs & Services" → "Credentials" → "Create Credentials"
     → "OAuth client ID" → Application type: "Web application".
  2. Add your page's origin under "Authorized JavaScript origins"
     (e.g. http://localhost:8000 for local testing, or your Render
     URL once deployed).
  3. Copy the generated Client ID and set it as an environment
     variable before starting the server:
         export GOOGLE_CLIENT_ID="xxxxxxxxxx.apps.googleusercontent.com"
  4. That's it server-side. The frontend also needs a small bit of
     Google Identity Services wiring to actually get an id_token in
     the first place — see hokm-phase4-online.html's loginGoogle()
     function, which currently just logs the person in as a guest
     and is the next piece to wire up to this.

Without GOOGLE_CLIENT_ID set, is_configured() returns False and
server.py cleanly tells the client Google login isn't available yet
(see the "google_login_not_configured" i18n string) instead of
crashing — guest login keeps working regardless.

---

Session tokens (added after the above): every login (guest or Google)
used to hand the browser a bare `str(uuid.uuid4())` as its
session_token — random and unguessable, but not a *verifiable*
credential: it carried no expiry, and nothing about the string itself
proved the server issued it. It only "worked" because server.py kept
a matching {token: player_id} dict in memory (SESSION_TO_PLAYER) —
fine for one process, but not something you can check without that
dict, and a leaked token stayed valid forever.

issue_session_token()/verify_session_token() below replace that with
real signed JWTs (HS256): the token itself now carries the player_id
(`sub`) and an expiry (`exp`), and verify_session_token cryptographically
checks the signature before trusting either. server.py still also
checks the token against SESSION_TO_PLAYER / Player.session_token on
top of that (see the "reconnect" branch of ws_endpoint) — that second
check is what makes issuing a *new* token on next login invalidate the
old one (a JWT is only as revocable as whatever you compare it against
after verifying it, so we still compare).

Signing secret: set HOKM_JWT_SECRET yourself for anything beyond local
testing — it's REQUIRED once you run more than one server process
(e.g. behind a load balancer, or the PostgreSQL multi-instance setup
in hokm_storage.py) since every instance must share the same secret to
verify each other's tokens. If it's not set, a secret is generated
once and cached in a local file (.jwt_secret, next to this module) so
sessions still survive a restart on a single-instance/local setup
without any manual setup — same "just works" MVP spirit as hokm.db.
On a read-only filesystem where even that can't be written, it falls
back to an in-memory secret for that process's lifetime (sessions
won't survive a restart there, which is a strict improvement over
crashing).
"""
import os
import secrets
import time

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()


def is_configured() -> bool:
    return bool(GOOGLE_CLIENT_ID)


def verify_google_id_token(id_token_str: str) -> dict | None:
    """Verifies a Google-issued ID token server-side. Returns the
    token's claims dict (at least "sub", "name"; usually "email") on
    success, or None if the token is missing, malformed, expired, not
    meant for our client ID, or not actually signed by Google.

    Lazily imports google-auth so the rest of the server can run
    (and every other feature keep working) even on a machine where
    that optional dependency hasn't been installed yet.
    """
    if not id_token_str or not is_configured():
        return None
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
    except ImportError:
        # google-auth isn't installed — see requirements.txt. Fail
        # closed (no login) rather than pretend this succeeded.
        return None

    try:
        claims = google_id_token.verify_oauth2_token(
            id_token_str, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception:
        # Any verification failure (bad signature, expired, wrong
        # audience, malformed token, network error reaching Google's
        # public keys, ...) — never trust an unverifiable token.
        return None

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        return None
    if not claims.get("sub"):
        return None
    claims.setdefault("name", claims.get("email", "کاربر گوگل"))
    return claims


# ------------------------------------------------------- session (JWT) --

SESSION_TTL_DAYS = int(os.environ.get("HOKM_SESSION_TTL_DAYS", 90))
_JWT_SECRET_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".jwt_secret")
_jwt_secret_cache: str | None = None


def _jwt_secret() -> str:
    """Resolves the signing secret once per process and caches it:
    HOKM_JWT_SECRET env var first, else a value persisted in
    .jwt_secret (created on first use), else an in-memory-only
    fallback if the filesystem is read-only. See the module docstring
    for why each of these matters."""
    global _jwt_secret_cache
    if _jwt_secret_cache:
        return _jwt_secret_cache

    env_secret = os.environ.get("HOKM_JWT_SECRET", "").strip()
    if env_secret:
        _jwt_secret_cache = env_secret
        return _jwt_secret_cache

    try:
        if os.path.exists(_JWT_SECRET_PATH):
            with open(_JWT_SECRET_PATH, "r") as f:
                existing = f.read().strip()
            if existing:
                _jwt_secret_cache = existing
                return _jwt_secret_cache
        generated = secrets.token_hex(32)
        with open(_JWT_SECRET_PATH, "w") as f:
            f.write(generated)
        _jwt_secret_cache = generated
    except OSError:
        # Read-only filesystem or similar — still work for this process's
        # lifetime rather than crash; sessions just won't survive a restart.
        _jwt_secret_cache = secrets.token_hex(32)

    return _jwt_secret_cache


def issue_session_token(player_id: str) -> str:
    """Issues a signed JWT session token for this player_id — call this
    on every login/reconnect-with-new-token, exactly where
    `str(uuid.uuid4())` used to be called in server.py."""
    import jwt  # PyJWT — see requirements.txt

    now = int(time.time())
    claims = {
        "sub": player_id,
        "iat": now,
        "exp": now + SESSION_TTL_DAYS * 86400,
    }
    return jwt.encode(claims, _jwt_secret(), algorithm="HS256")


def verify_session_token(token: str) -> tuple:
    """Verifies a session token's signature and expiry.

    Returns (player_id, expired):
      - (player_id, False)  — valid, unexpired, genuinely issued by us.
      - (None, True)        — signature checks out but it's expired.
      - (None, False)       — missing, malformed, or not signed by us
                               (never trust these — could be forged).

    This only proves the token is authentic and fresh; it does NOT by
    itself prove it's still the player's *current* session (server.py
    additionally compares it against the stored Player.session_token,
    which is what makes issuing a new token on next login invalidate
    this one — a JWT alone doesn't give you revocation).
    """
    if not token:
        return None, False
    try:
        import jwt
    except ImportError:
        # PyJWT isn't installed — fail closed (no session survives),
        # same "fail closed" stance as verify_google_id_token above.
        return None, False

    try:
        claims = jwt.decode(token, _jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, True
    except Exception:
        return None, False

    player_id = claims.get("sub")
    if not player_id:
        return None, False
    return player_id, False
