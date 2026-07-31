"""
hokm_storage.py — persistence for player progress: SQLite by default,
PostgreSQL when you actually need multi-instance scale.

Problem this solves: server.py used to keep every player (rank, coins,
gems, missions, stats, match history, ...) only in a Python dict in
memory. Restart the process (a deploy, a crash, a free-tier host
recycling your app) and everyone's progress was gone.

Fix: a database row per player, written after any meaningful change and
reloaded at startup. It plugs into the *existing* guest session flow
instead of replacing it: the browser already stores its session_token in
localStorage and sends {"type": "reconnect", "session_token": ...}
whenever it opens the page — that keeps working across restarts now.

Two backends, same four-function interface (init_db / save_player /
load_all_players / close) — server.py never needs to know or care which
one is active:

  - SQLite (default, unchanged behaviour): a single local file, no
    external service, no monthly cost. Fine for one server process.
    This is what you get if you don't set DATABASE_URL.

  - PostgreSQL (opt-in): set the DATABASE_URL env var (the standard
    "postgresql://user:pass@host:5432/dbname" form — exactly what
    Render/Railway/Supabase/Neon hand you when you create a Postgres
    instance) and this module switches over automatically. This is
    the one that actually matters once you run more than one server
    process/instance: SQLite is a single local file, so two processes
    on two machines (or even two containers on the same host with
    separate disks) can't see each other's writes. Postgres is a real
    network service every instance talks to, so player state stays
    consistent no matter which instance a websocket lands on.

    Needs psycopg2-binary installed (see requirements.txt — it's
    listed but only imported lazily here, so a machine without it
    installed still runs fine on SQLite).

Scope, honestly stated, still applies either way: this persists
PLAYERS (progression) only. Rooms/live matches are intentionally NOT
persisted — a match in progress when the server restarts is lost,
same as before. Fine for an MVP; true mid-match failover would need
room state to move into the database too, which is a separate, bigger
piece of work than swapping the storage engine.
"""
import json
import os
import sqlite3
import threading
import time

DB_PATH = os.environ.get("HOKM_DB_PATH", os.path.join(os.path.dirname(__file__), "hokm.db"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_lock = threading.Lock()
_conn = None              # sqlite3.Connection, when on the SQLite backend
_pg_pool = None            # psycopg2 pool, when on the Postgres backend
BACKEND = "postgres" if DATABASE_URL else "sqlite"


# =============================================================== sqlite ===

def _sqlite_init():
    global _conn
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY,
            session_token TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_players_token ON players(session_token)")
    _conn.commit()


def _sqlite_save(player_id, session_token, data):
    payload = json.dumps(data, ensure_ascii=False)
    with _lock:
        _conn.execute(
            "INSERT INTO players (id, session_token, data, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET session_token=excluded.session_token,"
            " data=excluded.data, updated_at=excluded.updated_at",
            (player_id, session_token, payload, time.time()),
        )
        _conn.commit()


def _sqlite_load_all():
    with _lock:
        rows = _conn.execute("SELECT id, session_token, data FROM players").fetchall()
    out = []
    for pid, token, raw in rows:
        try:
            out.append((pid, token, json.loads(raw)))
        except json.JSONDecodeError:
            continue  # skip a corrupted row rather than crash startup
    return out


def _sqlite_close():
    global _conn
    if _conn is not None:
        with _lock:
            _conn.commit()
            _conn.close()
        _conn = None


# ============================================================= postgres ===

def _pg_init():
    global _pg_pool
    try:
        import psycopg2
        import psycopg2.pool
    except ImportError as e:
        raise RuntimeError(
            "DATABASE_URL is set but psycopg2-binary isn't installed — "
            "run: pip install psycopg2-binary"
        ) from e

    _pg_pool = psycopg2.pool.SimpleConnectionPool(1, 10, dsn=DATABASE_URL)
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    session_token TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_players_token ON players(session_token)")
        conn.commit()
    finally:
        _pg_pool.putconn(conn)


def _pg_save(player_id, session_token, data):
    payload = json.dumps(data, ensure_ascii=False)
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO players (id, session_token, data, updated_at) VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET session_token=EXCLUDED.session_token,"
                " data=EXCLUDED.data, updated_at=EXCLUDED.updated_at",
                (player_id, session_token, payload, time.time()),
            )
        conn.commit()
    finally:
        _pg_pool.putconn(conn)


def _pg_load_all():
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, session_token, data FROM players")
            rows = cur.fetchall()
    finally:
        _pg_pool.putconn(conn)
    out = []
    for pid, token, raw in rows:
        try:
            # psycopg2 already decodes JSONB into a dict; a plain str
            # would only happen against an older TEXT column, so handle
            # both rather than assume.
            out.append((pid, token, raw if isinstance(raw, dict) else json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _pg_close():
    global _pg_pool
    if _pg_pool is not None:
        _pg_pool.closeall()
        _pg_pool = None


# ================================================================ public ==
# The four functions server.py actually calls. Which backend they hit is
# decided once, at import time, by whether DATABASE_URL is set — nothing
# else in server.py changes either way.

def init_db():
    if BACKEND == "postgres":
        _pg_init()
    else:
        _sqlite_init()


def save_player(player_id: str, session_token: str, data: dict):
    """Upsert one player's serialized state. Cheap enough to call after
    any meaningful change (match end, purchase, ...) as well as on a
    periodic autosave loop."""
    if BACKEND == "postgres":
        if _pg_pool is None:
            return
        _pg_save(player_id, session_token, data)
    else:
        if _conn is None:
            return
        _sqlite_save(player_id, session_token, data)


def load_all_players():
    """Returns a list of (player_id, session_token, data_dict) for every
    saved player, read back at server startup."""
    if BACKEND == "postgres":
        if _pg_pool is None:
            return []
        return _pg_load_all()
    if _conn is None:
        return []
    return _sqlite_load_all()


def close():
    if BACKEND == "postgres":
        _pg_close()
    else:
        _sqlite_close()
