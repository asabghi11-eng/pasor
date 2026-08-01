import asyncio
from contextlib import asynccontextmanager

_refresh_hook = None


async def init():
    """Initialize realtime backend (No-Op)."""
    return


async def close():
    """Shutdown realtime backend (No-Op)."""
    return


def is_enabled() -> bool:
    """Redis backend disabled."""
    return False


def set_refresh_hook(func):
    global _refresh_hook
    _refresh_hook = func


async def start_listener(callback):
    """No listener when Redis is disabled."""
    return


async def publish_room_update(room_id):
    """Nothing to publish in single-server mode."""
    return


@asynccontextmanager
async def room_lock(room):
    """
    Per-room async lock.
    Creates a lock on first use.
    """
    if not hasattr(room, "_rt_lock"):
        room._rt_lock = asyncio.Lock()

    async with room._rt_lock:
        yield