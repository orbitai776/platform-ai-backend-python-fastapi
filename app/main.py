from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from app.ai_service import call_extractor, error_message_from_exception
from app.chat_service import (
    default_slots,
    extract_slot_update_with_cache,
    merge_slots,
    missing_slots,
    next_question,
    status_from_missing,
)
from app.session_store import delete_chat_session, get_chat_session, save_chat_session
from app.schemas import (
    ChatDeleteData,
    ChatDeleteResponse,
    ChatMessage,
    ChatStartRequest,
    ChatStateData,
    ChatStateResponse,
    ChatTurnData,
    ChatTurnRequest,
    ChatTurnResponse,
    ChatStatus,
    GenerateQueryData,
    GenerateQueryRequest,
    GenerateQueryResponse,
    MAX_TURNS,
)

app = FastAPI(title="Sprint02 Multi-turn Slot Filling", version="1.0.0")
LOGGER = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 4000


def _validate_message(message: str, field_name: str) -> str:
    cleaned = message.strip()
    if not cleaned:
        raise ValueError(f"{field_name} không được để trống")
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"{field_name} vượt quá {MAX_MESSAGE_LENGTH} ký tự")
    return cleaned


def _build_reply(status: ChatStatus, missing: list[str], turn_count: int, stagnation_count: int) -> str:
    if status == ChatStatus.completed:
        return "Đã đủ thông tin. Tôi sẽ tạo truy vấn tìm kiếm tối ưu cho bạn."

    if turn_count >= MAX_TURNS or stagnation_count >= 2:
        remaining = ", ".join(missing)
        return (
            "Mình đang thiếu các thông tin sau: "
            f"{remaining}. Bạn vui lòng gửi đầy đủ các mục này trong một tin nhắn "
            "để mình hoàn tất bộ lọc nhanh hơn."
        )

    return next_question(missing)


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "name": app.title,
        "version": app.version,
        "health": "/health",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "api_prefix": "/api/v1",
    }


async def _run_chat_turn(session_id: str, message: str) -> ChatTurnData:
    message = _validate_message(message, "message")
    session = await get_chat_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=(
                "Không tìm thấy phiên chat. Phiên có thể đã hết hạn hoặc đã mất sau khi server reload/restart "
                "(đang dùng in-memory store). Hãy tạo phiên mới hoặc cấu hình REDIS_URL để lưu bền vững."
            ),
        )

    session["turn_count"] = session.get("turn_count", 0) + 1
    session["history"].append({"role": "user", "content": message})

    previous_slots = dict(session["slots"])
    last_extracted = await extract_slot_update_with_cache(
        message,
        session["slots"],
        session.get("llm_cache"),
    )
    session["slots"] = merge_slots(previous_slots, last_extracted)
    progress = session["slots"] != previous_slots
    if progress:
        session["stagnation_count"] = 0
    else:
        session["stagnation_count"] = session.get("stagnation_count", 0) + 1

    missing = missing_slots(session["slots"])
    status = status_from_missing(missing)

    reply = _build_reply(
        status,
        missing,
        session["turn_count"],
        session.get("stagnation_count", 0),
    )

    session["history"].append({"role": "assistant", "content": reply})
    session["history"] = session["history"][-20:]
    await save_chat_session(session_id, session)

    return ChatTurnData(
        session_id=session_id,
        reply=reply,
        status=status,
        missing_slots=missing,
        filled_slots=session["slots"],
        last_extracted=last_extracted,
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v1/generate-query-dynamic", response_model=GenerateQueryResponse)
async def generate_query_dynamic(payload: GenerateQueryRequest) -> GenerateQueryResponse:
    try:
        query = _validate_message(payload.query, "query")
        result = await call_extractor(query, payload.schema_payload)
        data = GenerateQueryData(content=result["content"], usage=result.get("usage"))
        return GenerateQueryResponse(data=data, error=None)
    except Exception as exc:
        LOGGER.exception("generate_query_dynamic failed")
        return GenerateQueryResponse(data=None, error=error_message_from_exception(exc))


@app.post("/api/v1/chat/start", response_model=ChatTurnResponse)
async def chat_start(payload: ChatStartRequest) -> ChatTurnResponse:
    session_id = str(uuid4())
    session = {
        "slots": default_slots(),
        "history": [],
        "llm_cache": {},
        "stagnation_count": 0,
        "turn_count": 0,
    }
    await save_chat_session(session_id, session)

    if payload.first_message and payload.first_message.strip():
        try:
            first_message = _validate_message(payload.first_message, "first_message")
            data = await _run_chat_turn(session_id, first_message)
            return ChatTurnResponse(data=data, error=None)
        except Exception as exc:
            LOGGER.exception("chat_start failed")
            return ChatTurnResponse(data=None, error=error_message_from_exception(exc))

    missing = missing_slots(session["slots"])
    reply = next_question(missing)
    session["history"].append({"role": "assistant", "content": reply})
    await save_chat_session(session_id, session)

    data = ChatTurnData(
        session_id=session_id,
        reply=reply,
        status=status_from_missing(missing),
        missing_slots=missing,
        filled_slots=session["slots"],
        last_extracted=None,
    )
    return ChatTurnResponse(data=data, error=None)


@app.post("/api/v1/chat/turn", response_model=ChatTurnResponse)
async def chat_turn(payload: ChatTurnRequest) -> ChatTurnResponse:
    try:
        message = _validate_message(payload.message, "message")
        data = await _run_chat_turn(payload.session_id, message)
        return ChatTurnResponse(data=data, error=None)
    except HTTPException as exc:
        return ChatTurnResponse(data=None, error=exc.detail)
    except Exception as exc:
        LOGGER.exception("chat_turn failed")
        return ChatTurnResponse(data=None, error=error_message_from_exception(exc))


@app.get("/api/v1/chat/{session_id}", response_model=ChatStateResponse)
async def chat_state(session_id: str) -> ChatStateResponse:
    session = await get_chat_session(session_id)
    if not session:
        return ChatStateResponse(data=None, error="Không tìm thấy phiên chat")

    missing = missing_slots(session["slots"])
    history = [ChatMessage(**item) for item in session["history"]]
    data = ChatStateData(
        session_id=session_id,
        status=status_from_missing(missing),
        missing_slots=missing,
        filled_slots=session["slots"],
        history=history,
    )
    return ChatStateResponse(data=data, error=None)


@app.delete("/api/v1/chat/{session_id}", response_model=ChatDeleteResponse)
async def chat_delete(session_id: str) -> ChatDeleteResponse:
    deleted = await delete_chat_session(session_id)
    if not deleted:
        return ChatDeleteResponse(data=None, error="Không tìm thấy phiên chat")
    data = ChatDeleteData(session_id=session_id, deleted=True)
    return ChatDeleteResponse(data=data, error=None)
