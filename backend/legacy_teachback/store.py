"""
In-memory per-session pub/sub for pushing tool results to the browser over
Server-Sent Events. Fine for a hackathon demo (single process, no restart
mid-session); swap for Redis pub/sub if this ever needs multiple workers.
"""
import asyncio
import time

_SESSIONS: dict[str, dict] = {}
_TTL_SECONDS = 60 * 30  # abandoned sessions are dropped after 30 min


def create_session() -> str:
    import uuid
    sid = uuid.uuid4().hex
    _SESSIONS[sid] = {"queue": asyncio.Queue(), "created": time.time(), "data": {}}
    return sid


def _get(session_id: str) -> dict | None:
    _gc()
    return _SESSIONS.get(session_id)


def _gc():
    now = time.time()
    dead = [sid for sid, s in _SESSIONS.items() if now - s["created"] > _TTL_SECONDS]
    for sid in dead:
        _SESSIONS.pop(sid, None)


def exists(session_id: str) -> bool:
    return _get(session_id) is not None


def set_data(session_id: str, key: str, value) -> None:
    s = _get(session_id)
    if s is not None:
        s["data"][key] = value


def get_data(session_id: str, key: str):
    s = _get(session_id)
    return s["data"].get(key) if s else None


async def publish(session_id: str, event: dict) -> None:
    s = _get(session_id)
    if s is not None:
        await s["queue"].put(event)


async def stream(session_id: str):
    """Async generator of SSE-formatted strings for this session's queue."""
    s = _get(session_id)
    if s is None:
        yield 'event: error\ndata: {"message": "unknown session_id"}\n\n'
        return
    queue: asyncio.Queue = s["queue"]
    import json
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=15.0)
            yield f"data: {json.dumps(event)}\n\n"
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
        if not exists(session_id):
            break
