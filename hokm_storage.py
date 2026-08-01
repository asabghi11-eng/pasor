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

Scope, honestly stated: this persists both PLAYERS (progression) and
ROOMS (live match state — seats, hands, trump, current trick, score).
A match in progress now survives a server restart/redeploy: on startup
every saved room is reloaded into memory and each seated player's
`room_id`/`seat` (also persisted now) routes their next `reconnect`
straight back into that room instead of dumping them at the lobby.
Same two-backend split as players: fine on SQLite for one process,
needs Postgres once you run more than one server instance so every
instance sees the same rooms.

load_room()/find_room_by_code() below exist for that multi-instance
case specifically: they let an instance that DIDN'T create a room (so
it isn't in that process's in-memory ROOMS/CODE_TO_ROOM dicts) still
find it — by id, or by the 6-char code a friend typed in — instead of
answering "invalid code" just because the request landed on the wrong
process. See hokm_realtime.py for the Redis piece (distributed lock +
live cross-instance push) that this pairs with.
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
    _conn.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            code TEXT,
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    # Older DBs created before `code` existed: add it rather than crash.
    cols = [r[1] for r in _conn.execute("PRAGMA table_info(rooms)").fetchall()]
    if "code" not in cols:
        _conn.execute("ALTER TABLE rooms ADD COLUMN code TEXT")
    _conn.execute("CREATE INDEX IF NOT EXISTS idx_rooms_code ON rooms(code)")
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


def _sqlite_save_room(room_id, data, code=None):
    payload = json.dumps(data, ensure_ascii=False)
    with _lock:
        _conn.execute(
            "INSERT INTO rooms (id, code, data, updated_at) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(id) DO UPDATE SET code=excluded.code,"
            " data=excluded.data, updated_at=excluded.updated_at",
            (room_id, code, payload, time.time()),
        )
        _conn.commit()


def _sqlite_load_all_rooms():
    with _lock:
        rows = _conn.execute("SELECT id, data FROM rooms").fetchall()
    out = []
    for rid, raw in rows:
        try:
            out.append((rid, json.loads(raw)))
        except json.JSONDecodeError:
            continue
    return out


def _sqlite_load_room(room_id):
    with _lock:
        row = _conn.execute("SELECT data FROM rooms WHERE id = ?", (room_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def _sqlite_find_room_by_code(code):
    with _lock:
        row = _conn.execute("SELECT data FROM rooms WHERE code = ?", (code,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except json.JSONDecodeError:
        return None


def _sqlite_delete_room(room_id):
    with _lock:
        _conn.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
        _conn.commit()


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
            # Two instances starting at the same moment (a fresh multi-replica
            # deploy, the exact scenario this multi-instance support exists
            # for) can otherwise both run "CREATE TABLE IF NOT EXISTS" at once
            # and hit a Postgres catalog race (IF NOT EXISTS isn't atomic
            # against concurrent DDL) — a UniqueViolation on pg_type that
            # crashes startup. An advisory lock serializes just this
            # migration step across instances; released automatically when
            # the transaction commits/rolls back below.
            cur.execute("SELECT pg_advisory_lock(727100001)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    id TEXT PRIMARY KEY,
                    session_token TEXT NOT NULL,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_players_token ON players(session_token)")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rooms (
                    id TEXT PRIMARY KEY,
                    code TEXT,
                    data JSONB NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                )
            """)
            # Older DBs created before `code` existed: add it rather than crash.
            cur.execute("ALTER TABLE rooms ADD COLUMN IF NOT EXISTS code TEXT")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_rooms_code ON rooms(code)")
            cur.execute("SELECT pg_advisory_unlock(727100001)")
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


def _pg_save_room(room_id, data, code=None):
    payload = json.dumps(data, ensure_ascii=False)
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rooms (id, code, data, updated_at) VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET code=EXCLUDED.code,"
                " data=EXCLUDED.data, updated_at=EXCLUDED.updated_at",
                (room_id, code, payload, time.time()),
            )
        conn.commit()
    finally:
        _pg_pool.putconn(conn)


def _pg_load_all_rooms():
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, data FROM rooms")
            rows = cur.fetchall()
    finally:
        _pg_pool.putconn(conn)
    out = []
    for rid, raw in rows:
        try:
            out.append((rid, raw if isinstance(raw, dict) else json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _pg_load_room(room_id):
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM rooms WHERE id = %s", (room_id,))
            row = cur.fetchone()
    finally:
        _pg_pool.putconn(conn)
    if not row:
        return None
    raw = row[0]
    try:
        return raw if isinstance(raw, dict) else json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _pg_find_room_by_code(code):
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT data FROM rooms WHERE code = %s", (code,))
            row = cur.fetchone()
    finally:
        _pg_pool.putconn(conn)
    if not row:
        return None
    raw = row[0]
    try:
        return raw if isinstance(raw, dict) else json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def _pg_delete_room(room_id):
    conn = _pg_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM rooms WHERE id = %s", (room_id,))
        conn.commit()
    finally:
        _pg_pool.putconn(conn)


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


def save_room(room_id: str, data: dict, code: str = None):
    """Upsert one room's serialized live-match state. Cheap enough to call
    after every broadcast_state() — i.e. after any deal, trump choice,
    card play, or trick/hand/match resolution. `code` is stored in its own
    indexed column (in addition to being inside `data`, same as before) so
    another server instance can find this room by its 6-char join code
    without having to load and scan every saved room — see
    find_room_by_code()."""
    if BACKEND == "postgres":
        if _pg_pool is None:
            return
        _pg_save_room(room_id, data, code)
    else:
        if _conn is None:
            return
        _sqlite_save_room(room_id, data, code)


def load_all_rooms():
    """Returns a list of (room_id, data_dict) for every saved room, read
    back at server startup so matches in progress survive a restart."""
    if BACKEND == "postgres":
        if _pg_pool is None:
            return []
        return _pg_load_all_rooms()
    if _conn is None:
        return []
    return _sqlite_load_all_rooms()


def load_room(room_id: str):
    """Returns one room's data_dict, or None. Used to lazily pull a room
    into memory on an instance that didn't create it (multi-instance,
    see hokm_realtime.py) and to refresh a room to its latest saved state
    right before a distributed-lock-protected mutation."""
    if BACKEND == "postgres":
        if _pg_pool is None:
            return None
        return _pg_load_room(room_id)
    if _conn is None:
        return None
    return _sqlite_load_room(room_id)


def find_room_by_code(code: str):
    """Returns one room's data_dict by its join code, or None. Lets any
    server instance resolve a friend's room code even if this process
    never created or previously loaded that room (multi-instance)."""
    if not code:
        return None
    if BACKEND == "postgres":
        if _pg_pool is None:
            return None
        return _pg_find_room_by_code(code)
    if _conn is None:
        return None
    return _sqlite_find_room_by_code(code)


def delete_room(room_id: str):
    """Remove a room's persisted row once it's actually gone (host left
    before the match started, etc.) so the table doesn't grow forever."""
    if BACKEND == "postgres":
        if _pg_pool is None:
            return
        _pg_delete_room(room_id)
    else:
        if _conn is None:
            return
        _sqlite_delete_room(room_id)


def close():
    if BACKEND == "postgres":
        _pg_close()
    else:
        _sqlite_close()