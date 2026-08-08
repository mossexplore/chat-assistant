from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol

from .errors import PersistenceError
from .message_content import content_for_logging
from .models import ChatMessage


class MessageRecordWriter(Protocol):
    def write(self, group_id: str, message: ChatMessage) -> None: ...


class NoOpMessageRecordWriter:
    def write(self, group_id: str, message: ChatMessage) -> None:
        """Test/default extension point that intentionally writes nothing."""


class FileMessageRecordWriter:
    def __init__(
        self,
        data_dir: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = data_dir / "logs" / "messages.log"
        self._clock = clock or (lambda: datetime.now().astimezone())
        self._lock = threading.Lock()

    def write(self, group_id: str, message: ChatMessage) -> None:
        recorded_at = self._clock().isoformat(timespec="milliseconds")
        fields = (
            recorded_at,
            message.msg_id,
            message.group_type,
            message.content_type,
            message.server_send_time,
            message.group_id or group_id,
            message.sender,
            message.receiver,
            content_for_logging(message),
        )
        line = "|".join(_escape_field(value) for value in fields) + "\n"
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8", newline="") as stream:
                    stream.write(line)
        except OSError as exc:
            raise PersistenceError(f"无法写入完整消息日志 {self.path}: {exc}") from exc


def _escape_field(value: object) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )
