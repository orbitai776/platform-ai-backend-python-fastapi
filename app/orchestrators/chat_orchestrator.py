from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException

from app.agents.contracts import AgentContext
from app.agents.registry import DEFAULT_DOMAIN_NAME, AgentRegistry, get_agent_registry
from app.api.v1.schemas import ChatMessage, ChatStateData, ChatStatus, ChatTurnData
from app.infrastructure.session_store import get_chat_session, save_chat_session


@dataclass(frozen=True)
class StartSessionResult:
    session_id: str
    session: dict[str, object]
    domain_name: str


class ChatOrchestrator:
    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry

    def list_domains(self) -> list[str]:
        return self._registry.list_domains()

    async def start_session(self, requested_domain: str | None = None) -> StartSessionResult:
        selected = (requested_domain or DEFAULT_DOMAIN_NAME).strip().lower() or DEFAULT_DOMAIN_NAME
        bundle = self._registry.get_bundle(selected)
        session_id = str(uuid4())
        session: dict[str, object] = {
            "domain_name": bundle.domain_agent.domain_name,
            "slots": bundle.domain_agent.default_slots(),
            "history": [],
            "llm_cache": {},
            "stagnation_count": 0,
            "turn_count": 0,
        }
        await save_chat_session(session_id, session)
        return StartSessionResult(session_id=session_id, session=session, domain_name=bundle.domain_agent.domain_name)

    async def build_initial_turn(self, session_id: str) -> ChatTurnData:
        session = await get_chat_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy phiên chat",
            )

        selected = str(session.get("domain_name") or DEFAULT_DOMAIN_NAME)
        bundle = self._registry.get_bundle(selected)
        slots = dict(session.get("slots", bundle.domain_agent.default_slots()))
        domain_result = bundle.domain_agent.process_turn(
            slots=slots,
            turn_count=int(session.get("turn_count", 0)),
            stagnation_count=int(session.get("stagnation_count", 0)),
        )

        history = list(session.get("history", []))
        history.append({"role": "assistant", "content": domain_result.reply})
        session["history"] = history[-20:]
        await save_chat_session(session_id, session)

        return ChatTurnData(
            session_id=session_id,
            service_name=bundle.domain_agent.domain_name,
            reply=domain_result.reply,
            status=ChatStatus(domain_result.status),
            missing_slots=domain_result.missing_slots,
            filled_slots=slots,
            last_extracted=None,
        )

    async def run_turn(self, session_id: str, message: str) -> ChatTurnData:
        session = await get_chat_session(session_id)
        if not session:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Không tìm thấy phiên chat. Phiên có thể đã hết hạn hoặc đã mất sau khi server reload/restart "
                    "(đang dùng in-memory store). Hãy tạo phiên mới hoặc cấu hình REDIS_URL để lưu bền vững."
                ),
            )

        requested_domain = str(session.get("domain_name") or DEFAULT_DOMAIN_NAME)
        planner_decision = await self._registry.planner.decide_domain(message, requested_domain=requested_domain)
        bundle = self._registry.get_bundle(planner_decision.domain_name)

        session["domain_name"] = bundle.domain_agent.domain_name
        session["turn_count"] = int(session.get("turn_count", 0)) + 1
        history = list(session.get("history", []))
        history.append({"role": "user", "content": message})
        session["history"] = history

        previous_slots = dict(session.get("slots", bundle.domain_agent.default_slots()))
        context = AgentContext(
            message=message,
            turn_count=int(session["turn_count"]),
            history=history,
            current_slots=previous_slots,
            llm_cache=session.get("llm_cache") if isinstance(session.get("llm_cache"), dict) else {},
        )
        extracted = await bundle.slot_filling_agent.extract(context)
        next_slots = bundle.domain_agent.merge_slots(previous_slots, extracted.slot_update)
        session["slots"] = next_slots
        session["llm_cache"] = context.llm_cache or {}

        progress = next_slots != previous_slots
        if progress:
            session["stagnation_count"] = 0
        else:
            session["stagnation_count"] = int(session.get("stagnation_count", 0)) + 1

        domain_result = bundle.domain_agent.process_turn(
            slots=next_slots,
            turn_count=int(session["turn_count"]),
            stagnation_count=int(session.get("stagnation_count", 0)),
        )

        history.append({"role": "assistant", "content": domain_result.reply})
        session["history"] = history[-20:]
        await save_chat_session(session_id, session)

        return ChatTurnData(
            session_id=session_id,
            service_name=bundle.domain_agent.domain_name,
            reply=domain_result.reply,
            status=ChatStatus(domain_result.status),
            missing_slots=domain_result.missing_slots,
            filled_slots=next_slots,
            last_extracted=extracted.slot_update,
        )

    async def build_chat_state(self, session_id: str) -> ChatStateData | None:
        session = await get_chat_session(session_id)
        if not session:
            return None

        selected = str(session.get("domain_name") or DEFAULT_DOMAIN_NAME)
        bundle = self._registry.get_bundle(selected)
        slots = dict(session.get("slots", bundle.domain_agent.default_slots()))
        missing = bundle.domain_agent.missing_slots(slots)
        history = [ChatMessage(**item) for item in list(session.get("history", []))]

        return ChatStateData(
            session_id=session_id,
            service_name=bundle.domain_agent.domain_name,
            status=ChatStatus.completed if not missing else ChatStatus.collecting,
            missing_slots=missing,
            filled_slots=slots,
            history=history,
        )


_DEFAULT_ORCHESTRATOR: ChatOrchestrator | None = None


def get_chat_orchestrator() -> ChatOrchestrator:
    global _DEFAULT_ORCHESTRATOR
    if _DEFAULT_ORCHESTRATOR is not None:
        return _DEFAULT_ORCHESTRATOR
    _DEFAULT_ORCHESTRATOR = ChatOrchestrator(registry=get_agent_registry())
    return _DEFAULT_ORCHESTRATOR
