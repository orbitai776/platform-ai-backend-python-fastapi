from __future__ import annotations

import asyncio
import json
import os
from json import JSONDecodeError
from typing import Any, Callable

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

MODEL_AI = "gpt-4o-mini"
_DEFAULT_SYSTEM_PROMPT = (
    "You are a strict slot extraction engine. Extract values from the user text and return "
    "ONLY valid JSON that matches the provided schema. Keep unknown fields as null and do "
    "not invent facts."
)

load_dotenv()

_OPENAI_CLIENT: AsyncOpenAI | None = None
_OPENAI_CLIENT_LOCK = asyncio.Lock()


def _normalize_text_payload(schema_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema_payload, dict):
        raise ValueError("schema_payload phải là object")

    if "format" in schema_payload and isinstance(schema_payload["format"], dict):
        return {"format": schema_payload["format"]}

    text_payload = schema_payload.get("text")
    if isinstance(text_payload, dict) and isinstance(text_payload.get("format"), dict):
        return {"format": text_payload["format"]}

    raise ValueError("schema_payload phải có dạng {'format': {...}} hoặc {'text': {'format': {...}}}")


def _extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]

    output = payload["output"]
    for item in output:
        for content_item in item.get("content", []):
            text_value = content_item.get("text")
            if isinstance(text_value, str):
                return text_value
            if content_item.get("type") == "output_text" and isinstance(content_item.get("text"), str):
                return content_item["text"]

    raise KeyError("Cannot find output text in upstream response")


async def _get_openai_client(api_key: str, base_url: str | None, timeout: float) -> AsyncOpenAI:
    global _OPENAI_CLIENT

    if _OPENAI_CLIENT is not None:
        return _OPENAI_CLIENT

    async with _OPENAI_CLIENT_LOCK:
        if _OPENAI_CLIENT is None:
            _OPENAI_CLIENT = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
    return _OPENAI_CLIENT


def error_message_from_exception(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, (KeyError, IndexError, TypeError, JSONDecodeError)):
        return f"Định dạng dữ liệu trả về từ upstream không hợp lệ: {exc}"
    if isinstance(exc, APIStatusError):
        return f"OpenAI trả về lỗi HTTP: {exc.status_code}"
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return f"Lỗi mạng khi gọi OpenAI: {exc}"
    return f"Lỗi không mong đợi: {exc}"


async def call_extractor(
    query: str,
    schema_payload: dict[str, Any],
    validate_slot_data: bool = False,
    system_prompt: str | None = None,
    slot_validator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_base_url = os.getenv("OPENAI_BASE_URL")
    model_name = os.getenv("OPENAI_MODEL", MODEL_AI)
    timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "30"))
    max_retries = max(1, int(os.getenv("OPENAI_MAX_RETRIES", "3")))

    if not openai_api_key:
        raise ValueError("Thiếu biến môi trường OPENAI_API_KEY")

    text_payload = _normalize_text_payload(schema_payload)
    client = await _get_openai_client(openai_api_key, openai_base_url, timeout_seconds)

    response = None
    for attempt in range(1, max_retries + 1):
        try:
            response = await client.responses.create(
                model=model_name,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt or _DEFAULT_SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": query,
                    },
                ],
                text=text_payload,
                temperature=0,
            )
            break
        except APIStatusError as exc:
            retryable = exc.status_code in {408, 409, 429} or exc.status_code >= 500
            if not retryable or attempt >= max_retries:
                raise
        except (APIConnectionError, APITimeoutError):
            if attempt >= max_retries:
                raise

        await asyncio.sleep(min(2**attempt, 5))

    if response is None:
        raise RuntimeError("OpenAI response is empty after retries")

    payload = response.model_dump()
    output_text = getattr(response, "output_text", None) or _extract_output_text(payload)
    content = json.loads(output_text)

    if validate_slot_data:
        if slot_validator is not None:
            content = slot_validator(content)
        else:
            from app.domains.tourist.slots import TouristSlotData

            content = TouristSlotData.model_validate(content).model_dump(mode="python")

    return {
        "content": content,
        "usage": payload.get("usage"),
    }
