from __future__ import annotations

from app.agents.registry import DEFAULT_DOMAIN_NAME
from app.orchestrator import get_chat_orchestrator
from app.application.config import MAX_MESSAGE_LENGTH


def validate_message(message: str, field_name: str) -> str:
    cleaned = message.strip()
    if not cleaned:
        raise ValueError(f"{field_name} không được để trống")
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"{field_name} vượt quá {MAX_MESSAGE_LENGTH} ký tự")
    return cleaned


def _get_orchestrator():
    return get_chat_orchestrator()


async def run_chat_turn(session_id: str, message: str):
    message = validate_message(message, "message")
    return await _get_orchestrator().run_turn(session_id, message)


async def start_chat_session(service_name: str):
    selected = (service_name or DEFAULT_DOMAIN_NAME).strip().lower() or DEFAULT_DOMAIN_NAME
    result = await _get_orchestrator().start_session(selected)
    session = result.session
    session["service_name"] = result.domain_name
    return result.session_id, session, result.domain_name


async def build_initial_chat_turn(session_id: str):
    return await _get_orchestrator().build_initial_turn(session_id)


async def build_chat_state(session_id: str):
    return await _get_orchestrator().build_chat_state(session_id)
