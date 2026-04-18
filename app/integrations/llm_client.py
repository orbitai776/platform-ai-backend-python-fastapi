from __future__ import annotations

from typing import Any, Callable

from app.integrations.openai_extractor import call_extractor


class LLMClient:
    async def extract_structured(
        self,
        message: str,
        schema_payload: dict[str, Any],
        *,
        system_prompt: str,
        validate_slot_data: bool = False,
        slot_validator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError


class OpenAILLMClient(LLMClient):
    async def extract_structured(
        self,
        message: str,
        schema_payload: dict[str, Any],
        *,
        system_prompt: str,
        validate_slot_data: bool = False,
        slot_validator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return await call_extractor(
            message,
            schema_payload,
            validate_slot_data=validate_slot_data,
            system_prompt=system_prompt,
            slot_validator=slot_validator,
        )


_DEFAULT_LLM_CLIENT: LLMClient = OpenAILLMClient()


def get_default_llm_client() -> LLMClient:
    return _DEFAULT_LLM_CLIENT
