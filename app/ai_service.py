from __future__ import annotations

import json
import os
from json import JSONDecodeError
from typing import Any

import httpx
from dotenv import load_dotenv

from app.schemas import MODEL_AI, SYSTEM_PROMPT

load_dotenv()


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


def error_message_from_exception(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, (KeyError, IndexError, TypeError, JSONDecodeError)):
        return f"Định dạng dữ liệu trả về từ upstream không hợp lệ: {exc}"
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        return f"Upstream trả về lỗi HTTP: {status_code}"
    if isinstance(exc, httpx.RequestError):
        return f"Lỗi mạng khi gọi upstream: {exc}"
    return f"Lỗi không mong đợi: {exc}"


async def call_extractor(query: str, schema_payload: dict[str, Any]) -> dict[str, Any]:
    openai_url = os.getenv("OPENAI_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    model_name = os.getenv("OPENAI_MODEL", MODEL_AI)

    if not openai_url or not openai_api_key:
        raise ValueError("Thiếu biến môi trường OPENAI_URL hoặc OPENAI_API_KEY")

    body = {
        "model": model_name,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": query}],
            },
        ],
        "text": schema_payload,
    }

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(openai_url, json=body, headers=headers)
        response.raise_for_status()

    payload = response.json()
    output_text = _extract_output_text(payload)
    content = json.loads(output_text)

    return {
        "content": content,
        "usage": payload.get("usage"),
    }
