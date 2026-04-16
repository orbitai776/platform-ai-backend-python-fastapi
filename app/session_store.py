from __future__ import annotations

import json
import os
from typing import Any

try:
    import redis.asyncio as redis_async
except Exception:  # pragma: no cover - optional dependency import guard
    redis_async = None

IN_MEMORY_CHAT_SESSIONS: dict[str, dict[str, Any]] = {}
_REDIS_CLIENT: Any | None = None


async def _get_redis_client() -> Any | None:
    global _REDIS_CLIENT

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url or redis_async is None:
        return None

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    candidate = redis_async.from_url(redis_url, encoding="utf-8", decode_responses=True)
    try:
        await candidate.ping()
    except Exception:
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


async def get_chat_session(session_id: str) -> dict[str, Any] | None:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        value = await redis_client.get(_redis_key(session_id))
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    return IN_MEMORY_CHAT_SESSIONS.get(session_id)


async def save_chat_session(session_id: str, session_data: dict[str, Any]) -> None:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        payload = json.dumps(session_data, ensure_ascii=False)
        await redis_client.set(_redis_key(session_id), payload, ex=_ttl_seconds())
        return

    IN_MEMORY_CHAT_SESSIONS[session_id] = session_data


async def delete_chat_session(session_id: str) -> bool:
    redis_client = await _get_redis_client()
    if redis_client is not None:
        deleted_count = await redis_client.delete(_redis_key(session_id))
        return bool(deleted_count)

    if session_id not in IN_MEMORY_CHAT_SESSIONS:
        return False

    del IN_MEMORY_CHAT_SESSIONS[session_id]
    return True
