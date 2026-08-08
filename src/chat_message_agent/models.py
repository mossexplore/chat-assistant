from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ChatMessage:
    msg_id: str
    content: str = ""
    content_type: str = ""
    sender: str = ""
    receiver: str = ""
    group_id: str = ""
    server_send_time: str | int = ""
    at: bool = False
    at_account_list: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

@dataclass(frozen=True, slots=True)
class SendResult:
    success: bool
    result_code: str
    result_context: str
    status_code: int | None
    message_ids: tuple[str, ...] = ()
    server_send_time: str | int | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True, slots=True)
class HistoryQueryResult:
    success: bool
    result_code: str
    result_context: str
    status_code: int | None
    messages: tuple[ChatMessage, ...]
    max_message_id: str | None
    min_message_id: str | None
    total_count: int
    raw: dict[str, Any] = field(default_factory=dict, compare=False)
