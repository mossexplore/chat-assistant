from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .errors import PersistenceError
from .storage import atomic_write_json

LOGGER = logging.getLogger(__name__)


class StateStore:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "runtime_state.json"
        self._lock = threading.RLock()
        self._state: dict[str, Any] = {"schema_version": 1, "group_cursors": {}}

    def load(self) -> None:
        if not self.path.exists():
            try:
                atomic_write_json(self.path, self._state)
            except PersistenceError as exc:
                LOGGER.error("event=state_create_failed error=%s", exc)
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("状态文件结构无效")
            cursors = raw.get("group_cursors")
            if not isinstance(cursors, dict):
                raise ValueError("状态文件结构无效")
            clean: dict[str, dict[str, str]] = {}
            for group_id, item in cursors.items():
                if isinstance(group_id, str) and isinstance(item, dict):
                    message_id = item.get("message_id")
                    if isinstance(message_id, str) and message_id:
                        clean[group_id] = {
                            "message_id": message_id,
                            "updated_at": str(item.get("updated_at", "")),
                        }
            with self._lock:
                self._state = {"schema_version": 1, "group_cursors": clean}
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            LOGGER.error("event=state_load_failed error=%s", exc)
            with self._lock:
                self._state = {"schema_version": 1, "group_cursors": {}}

    def get_cursor(self, group_id: str) -> str | None:
        with self._lock:
            item = self._state["group_cursors"].get(group_id)
            return item["message_id"] if item else None

    def set_cursor(self, group_id: str, message_id: str) -> None:
        with self._lock:
            new_state = {
                "schema_version": 1,
                "group_cursors": {
                    **self._state["group_cursors"],
                    group_id: {
                        "message_id": str(message_id),
                        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                },
            }
            atomic_write_json(self.path, new_state)
            self._state = new_state
