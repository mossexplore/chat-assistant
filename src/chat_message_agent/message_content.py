from __future__ import annotations

import json
from typing import Any

from .models import ChatMessage


def content_for_logging(message: ChatMessage) -> str:
    if message.content_type.upper() != "CARD_MSG":
        return message.content
    try:
        payload = json.loads(message.content)
    except (TypeError, json.JSONDecodeError):
        return message.content
    if not isinstance(payload, dict):
        return message.content

    card_context = payload.get("cardContext")
    if not isinstance(card_context, dict):
        return message.content
    reply_content = _nested_content(card_context.get("replyMsg"))
    if reply_content is None:
        return message.content
    quoted_content = _nested_content(card_context.get("preMsg"))
    if quoted_content is None:
        return reply_content
    return f"{reply_content}↩{quoted_content}"


def _nested_content(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    content = value.get("content")
    return content if isinstance(content, str) else None
