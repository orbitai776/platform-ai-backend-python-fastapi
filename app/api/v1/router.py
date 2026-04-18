from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.agents.registry import get_agent_registry
from app.orchestrator import get_chat_orchestrator
from app.api.v1.schemas import (
    ChatDeleteData,
    ChatDeleteResponse,
    ChatStartRequest,
    ChatStateResponse,
    ChatTurnRequest,
    ChatTurnResponse,
    GenerateQueryData,
    GenerateQueryRequest,
    GenerateQueryResponse,
)
from app.infrastructure.session_store import delete_chat_session
from app.integrations.llm_client import get_default_llm_client
from app.integrations.llm_adapter import error_message_from_exception
from app.application.chat_service import (
    build_chat_state,
    build_initial_chat_turn,
    run_chat_turn,
    start_chat_session,
    validate_message,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])
LOGGER = logging.getLogger(__name__)


@router.get("/ai-services")
async def ai_services() -> dict[str, object]:
    orchestrator = get_chat_orchestrator()
    return {
        "services": orchestrator.list_domains(),
        "default": "tourist",
    }


@router.post("/generate-query-dynamic", response_model=GenerateQueryResponse)
async def generate_query_dynamic(payload: GenerateQueryRequest) -> GenerateQueryResponse:
    try:
        query = validate_message(payload.query, "query")
        registry = get_agent_registry()
        extraction_config = registry.get_extraction_config(payload.service_name)
        llm_client = get_default_llm_client()
        result = await llm_client.extract_structured(
            query,
            payload.schema_payload,
            system_prompt=extraction_config.system_prompt,
        )
        data = GenerateQueryData(content=result["content"], usage=result.get("usage"))
        return GenerateQueryResponse(data=data, error=None)
    except Exception as exc:
        LOGGER.exception("generate_query_dynamic failed")
        return GenerateQueryResponse(data=None, error=error_message_from_exception(exc))


@router.post("/chat/start", response_model=ChatTurnResponse)
async def chat_start(payload: ChatStartRequest) -> ChatTurnResponse:
    try:
        session_id, session, service_name = await start_chat_session(payload.service_name)
    except Exception as exc:
        return ChatTurnResponse(data=None, error=error_message_from_exception(exc))

    if payload.first_message and payload.first_message.strip():
        try:
            first_message = validate_message(payload.first_message, "first_message")
            data = await run_chat_turn(session_id, first_message)
            return ChatTurnResponse(data=data, error=None)
        except Exception as exc:
            LOGGER.exception("chat_start failed")
            return ChatTurnResponse(data=None, error=error_message_from_exception(exc))

    data = await build_initial_chat_turn(session_id)
    return ChatTurnResponse(data=data, error=None)


@router.post("/chat/turn", response_model=ChatTurnResponse)
async def chat_turn(payload: ChatTurnRequest) -> ChatTurnResponse:
    try:
        message = validate_message(payload.message, "message")
        data = await run_chat_turn(payload.session_id, message)
        return ChatTurnResponse(data=data, error=None)
    except HTTPException as exc:
        return ChatTurnResponse(data=None, error=exc.detail)
    except Exception as exc:
        LOGGER.exception("chat_turn failed")
        return ChatTurnResponse(data=None, error=error_message_from_exception(exc))


@router.get("/chat/{session_id}", response_model=ChatStateResponse)
async def chat_state(session_id: str) -> ChatStateResponse:
    data = await build_chat_state(session_id)
    if data is None:
        return ChatStateResponse(data=None, error="Không tìm thấy phiên chat")
    return ChatStateResponse(data=data, error=None)


@router.delete("/chat/{session_id}", response_model=ChatDeleteResponse)
async def chat_delete(session_id: str) -> ChatDeleteResponse:
    deleted = await delete_chat_session(session_id)
    if not deleted:
        return ChatDeleteResponse(data=None, error="Không tìm thấy phiên chat")
    data = ChatDeleteData(session_id=session_id, deleted=True)
    return ChatDeleteResponse(data=data, error=None)
