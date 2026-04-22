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
_OPENAI_CLIENT_CONFIG: tuple[str, str | None, float] | None = None
_OPENAI_CLIENT_LOCK = asyncio.Lock()
_JSON_SCHEMA_HINT_KEYS = {
    "$schema",
    "$defs",
    "type",
    "properties",
    "required",
    "items",
    "enum",
    "oneOf",
    "anyOf",
    "allOf",
    "additionalProperties",
}


def _looks_like_json_schema(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in _JSON_SCHEMA_HINT_KEYS)


def _infer_schema_from_value(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if not value:
            return {"type": "string"}
        if _looks_like_json_schema(value):
            return _normalize_json_schema_node(value)
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {key: _infer_schema_from_value(item) for key, item in value.items()},
        }

    if isinstance(value, list):
        if not value:
            return {"type": "array", "items": {"type": "string"}}
        return {"type": "array", "items": _infer_schema_from_value(value[0])}

    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    return {"type": "string"}


def _normalize_json_schema_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_normalize_json_schema_node(item) for item in node]

    if not isinstance(node, dict):
        return {"type": "string"}

    normalized: dict[str, Any] = {}
    for key, value in node.items():
        if key in {"properties", "$defs", "definitions", "patternProperties"} and isinstance(value, dict):
            normalized[key] = {
                child_key: _normalize_json_schema_node(child_value)
                for child_key, child_value in value.items()
            }
        elif key in {"items", "contains", "if", "then", "else", "propertyNames", "not"} and isinstance(
            value, (dict, list)
        ):
            normalized[key] = _normalize_json_schema_node(value)
        elif key in {"oneOf", "anyOf", "allOf", "prefixItems"} and isinstance(value, list):
            normalized[key] = [_normalize_json_schema_node(item) for item in value]
        elif key == "additionalProperties" and isinstance(value, dict):
            normalized[key] = _normalize_json_schema_node(value)
        else:
            normalized[key] = value

    properties = normalized.get("properties")
    if isinstance(properties, dict):
        normalized["properties"] = {
            key: value if isinstance(value, dict) else _infer_schema_from_value(value)
            for key, value in properties.items()
        }

    schema_keywords = {"$ref", "enum", "const", "oneOf", "anyOf", "allOf", "not"}
    if "type" not in normalized and not any(keyword in normalized for keyword in schema_keywords):
        if isinstance(normalized.get("properties"), dict) or "required" in normalized:
            normalized["type"] = "object"
        elif "items" in normalized:
            normalized["type"] = "array"
        else:
            normalized["type"] = "string"

    if normalized.get("type") == "object":
        if not isinstance(normalized.get("properties"), dict):
            normalized["properties"] = {}
        if "additionalProperties" not in normalized:
            normalized["additionalProperties"] = False
        property_keys = list(normalized["properties"].keys())
        required = normalized.get("required")
        if isinstance(required, list):
            required_set = {item for item in required if isinstance(item, str)}
            for key in property_keys:
                required_set.add(key)
            normalized["required"] = [key for key in property_keys if key in required_set]
        else:
            normalized["required"] = property_keys

    if normalized.get("type") == "array":
        items = normalized.get("items")
        if not isinstance(items, dict):
            normalized["items"] = {"type": "string"}

    return normalized


def _normalize_text_payload(schema_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(schema_payload, dict):
        raise ValueError("schema_payload phải là object")

    if "format" in schema_payload and isinstance(schema_payload["format"], dict):
        return {"format": schema_payload["format"]}

    text_payload = schema_payload.get("text")
    if isinstance(text_payload, dict) and isinstance(text_payload.get("format"), dict):
        return {"format": text_payload["format"]}

    # Backward-compatible behavior for dynamic endpoint payloads.
    # If the payload is already a JSON schema, keep it as-is.
    # Otherwise treat it as a shorthand property map from Swagger/examples.
    schema_object = schema_payload
    if not _looks_like_json_schema(schema_payload):
        schema_object = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                key: _infer_schema_from_value(value)
                for key, value in schema_payload.items()
            },
        }
    schema_object = _normalize_json_schema_node(schema_object)

    return {
        "format": {
            "type": "json_schema",
            "name": "dynamic_schema",
            "strict": True,
            "schema": schema_object,
        }
    }


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


def _normalize_openai_base_url(base_url: str | None) -> str | None:
    if base_url is None:
        return None

    normalized = base_url.strip().rstrip("/")
    if not normalized:
        return None

    # AsyncOpenAI expects base URL at API root (for example: .../v1).
    if normalized.endswith("/responses"):
        normalized = normalized[: -len("/responses")]
    return normalized


async def _get_openai_client(api_key: str, base_url: str | None, timeout: float) -> AsyncOpenAI:
    global _OPENAI_CLIENT
    global _OPENAI_CLIENT_CONFIG

    target_config = (api_key, base_url, timeout)

    if _OPENAI_CLIENT is not None and _OPENAI_CLIENT_CONFIG == target_config:
        return _OPENAI_CLIENT

    async with _OPENAI_CLIENT_LOCK:
        if _OPENAI_CLIENT is None or _OPENAI_CLIENT_CONFIG != target_config:
            _OPENAI_CLIENT = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=timeout,
            )
            _OPENAI_CLIENT_CONFIG = target_config
    return _OPENAI_CLIENT


def _extract_api_status_message(exc: APIStatusError) -> str | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None

    try:
        payload = response.json()
    except Exception:
        return None

    if isinstance(payload, dict):
        error_obj = payload.get("error")
        if isinstance(error_obj, dict):
            message = error_obj.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    return None


def error_message_from_exception(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, (KeyError, IndexError, TypeError, JSONDecodeError)):
        return f"Định dạng dữ liệu trả về từ upstream không hợp lệ: {exc}"
    if isinstance(exc, APIStatusError):
        detail = _extract_api_status_message(exc)
        if detail:
            return f"OpenAI trả về lỗi HTTP: {exc.status_code} - {detail}"
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
    openai_base_url = _normalize_openai_base_url(os.getenv("OPENAI_BASE_URL"))
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
            from app.domain.tourist.slots import TouristSlotData

            content = TouristSlotData.model_validate(content).model_dump(mode="python")

    return {
        "content": content,
        "usage": payload.get("usage"),
    }