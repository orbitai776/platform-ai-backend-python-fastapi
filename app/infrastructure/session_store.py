from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

try:
    import redis.asyncio as redis_async
except Exception:  # pragma: no cover - optional dependency import guard
    redis_async = None

LOGGER = logging.getLogger(__name__)

IN_MEMORY_CHAT_SESSIONS: dict[str, tuple[float, dict[str, Any]]] = {}
_REDIS_CLIENT: Any | None = None
_REDIS_INIT_LOCK = asyncio.Lock()


async def _get_redis_client() -> Any | None:
    global _REDIS_CLIENT

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url or redis_async is None:
        return None

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    async with _REDIS_INIT_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT

        candidate = redis_async.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=3,
            socket_connect_timeout=3,
        )
        try:
            await candidate.ping()
        except Exception:
            LOGGER.exception("Redis ping failed, fallback to in-memory store")
            return None

        _REDIS_CLIENT = candidate
        return _REDIS_CLIENT


def _redis_key(session_id: str) -> str:
    return f"chat:session:{session_id}"


def _ttl_seconds() -> int:
    raw = os.getenv("SESSION_TTL_SECONDS", "86400").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 86400


def _now_ts() -> float:
    return time.time()


def _cleanup_memory_expired() -> None:
    now = _now_ts()
    expired = [session_id for session_id, (expires_at, _) in IN_MEMORY_CHAT_SESSIONS.items() if expires_at <= now]
    for session_id in expired:
        IN_MEMORY_CHAT_SESSIONS.pop(session_id, None)


async def get_chat_session(session_id: str) -> dict[str, Any] | None:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        try:
            value = await redis_client.get(_redis_key(session_id))
        except Exception:
            LOGGER.exception("Redis get failed for session_id=%s", session_id)
            value = None
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            LOGGER.exception("Redis session decode failed for session_id=%s", session_id)
            return None

    _cleanup_memory_expired()
    memory_entry = IN_MEMORY_CHAT_SESSIONS.get(session_id)
    if memory_entry is None:
        return None
    _, data = memory_entry
    return data


async def save_chat_session(session_id: str, session_data: dict[str, Any]) -> None:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        payload = json.dumps(session_data, ensure_ascii=False)
        try:
            await redis_client.set(_redis_key(session_id), payload, ex=_ttl_seconds())
        except Exception:
            LOGGER.exception("Redis set failed for session_id=%s", session_id)
        return

    _cleanup_memory_expired()
    IN_MEMORY_CHAT_SESSIONS[session_id] = (_now_ts() + _ttl_seconds(), session_data)


async def delete_chat_session(session_id: str) -> bool:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        try:
            deleted_count = await redis_client.delete(_redis_key(session_id))
        except Exception:
            LOGGER.exception("Redis delete failed for session_id=%s", session_id)
            return False
        return bool(deleted_count)

    _cleanup_memory_expired()
    if session_id not in IN_MEMORY_CHAT_SESSIONS:
        return False

    del IN_MEMORY_CHAT_SESSIONS[session_id]
    return True
