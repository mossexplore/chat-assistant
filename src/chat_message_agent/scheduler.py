from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime

from .cli_client import ChatCliClient
from .config import AppConfig, ConfigManager
from .errors import CliError
from .message_content import content_for_logging
from .message_log import MessageRecordWriter, NoOpMessageRecordWriter
from .models import ChatMessage
from .processor import MessageProcessor
from .state import StateStore

LOGGER = logging.getLogger(__name__)


def _id_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdecimal() else (1, value)


def _message_key(message: ChatMessage) -> tuple[tuple[int, int | str], tuple[int, int | str]]:
    timestamp = str(message.server_send_time)
    return _id_key(timestamp), _id_key(message.msg_id)


def _is_after(value: str, cursor: str) -> bool:
    return _id_key(value) > _id_key(cursor)


class QueryScheduler:
    def __init__(
        self,
        config_manager: ConfigManager,
        state_store: StateStore,
        processor: MessageProcessor,
        *,
        client_factory: Callable[[str], ChatCliClient] = ChatCliClient,
        message_record_writer: MessageRecordWriter | None = None,
        max_pages: int = 100,
    ) -> None:
        self.config_manager = config_manager
        self.state_store = state_store
        self.processor = processor
        self.client_factory = client_factory
        self.message_record_writer = message_record_writer or NoOpMessageRecordWriter()
        self.max_pages = max_pages
        self._changed = threading.Event()
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None
        self._status_lock = threading.Lock()
        self._last_query_at: str | None = None
        self._last_error: str | None = None
        self._running_query = False
        self.config_manager.subscribe(self.notify_config_changed)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stopping.clear()
        self._thread = threading.Thread(target=self._run, name="query-scheduler", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 35) -> None:
        self._stopping.set()
        self._changed.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                LOGGER.warning("event=scheduler_stop_timeout")

    def notify_config_changed(self, _config: AppConfig) -> None:
        self._changed.set()

    def status(self) -> dict[str, object]:
        with self._status_lock:
            return {
                "scheduler_running": bool(self._thread and self._thread.is_alive()),
                "query_running": self._running_query,
                "last_query_at": self._last_query_at,
                "last_error": self._last_error,
            }

    def _run(self) -> None:
        run_immediately = self.config_manager.snapshot().scheduled_query_enabled
        try:
            while not self._stopping.is_set():
                config = self.config_manager.snapshot()
                if not config.scheduled_query_enabled:
                    self._changed.clear()
                    latest = self.config_manager.snapshot()
                    if latest != config:
                        run_immediately = latest.scheduled_query_enabled
                        continue
                    self._changed.wait()
                    run_immediately = self.config_manager.snapshot().scheduled_query_enabled
                    continue
                if run_immediately:
                    self._safe_query(config)
                    run_immediately = False
                    continue

                self._changed.clear()
                latest = self.config_manager.snapshot()
                if latest != config:
                    run_immediately = (
                        latest.scheduled_query_enabled and not config.scheduled_query_enabled
                    )
                    continue
                changed = self._changed.wait(config.query_interval_seconds)
                if self._stopping.is_set():
                    break
                if changed:
                    new_config = self.config_manager.snapshot()
                    run_immediately = (
                        new_config.scheduled_query_enabled
                        and not config.scheduled_query_enabled
                    )
                else:
                    run_immediately = True
        except Exception:
            LOGGER.exception("event=scheduler_loop_crashed")

    def _safe_query(self, config: AppConfig) -> None:
        with self._status_lock:
            self._running_query = True
            self._last_error = None
        try:
            for group_id in config.target_group_ids:
                current = self.config_manager.snapshot()
                if self._stopping.is_set() or not current.scheduled_query_enabled:
                    break
                if group_id not in current.target_group_ids:
                    continue
                try:
                    self.run_group_query(config, group_id)
                except Exception as exc:
                    self._log_failure(group_id, exc)
                    with self._status_lock:
                        self._last_error = str(exc)[:500]
        except Exception:
            LOGGER.exception("event=query_cycle_unexpected_error")
        finally:
            with self._status_lock:
                self._running_query = False
                self._last_query_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    def run_query_cycle(self, config: AppConfig | None = None) -> None:
        config = config or self.config_manager.snapshot()
        for group_id in config.target_group_ids:
            self.run_group_query(config, group_id)

    def run_group_query(self, config: AppConfig, group_id: str) -> None:
        cursor = self.state_store.get_cursor(group_id)
        if cursor is None:
            result = self._client().query_history_messages(
                group_id=group_id,
                query_count=config.initial_query_count,
            )
            messages = self._ordered_unique(result.messages)
            self._process(group_id, messages)
            new_cursor = result.max_message_id or self._max_message_id(messages)
            if new_cursor:
                self.state_store.set_cursor(group_id, new_cursor)
            self._log_complete(group_id, len(messages), "initial")
            return

        for _page_number in range(1, self.max_pages + 1):
            result = self._client().query_history_messages(
                group_id=group_id,
                query_count=config.initial_query_count,
                message_id=cursor,
                query_direction=1,
            )
            messages = [
                item
                for item in self._ordered_unique(result.messages)
                if item.msg_id and _is_after(item.msg_id, cursor)
            ]
            self._process(group_id, messages)
            new_cursor = self._max_message_id(messages)
            if new_cursor:
                self.state_store.set_cursor(group_id, new_cursor)
            self._log_complete(group_id, len(messages), "incremental")

            if len(result.messages) < config.initial_query_count or not new_cursor:
                return
            cursor = new_cursor
            current = self.config_manager.snapshot()
            if (
                not current.scheduled_query_enabled
                or group_id not in current.target_group_ids
            ):
                return
        LOGGER.error(
            "event=history_query_page_limit group_id=%s max_pages=%s",
            group_id,
            self.max_pages,
        )

    def _client(self) -> ChatCliClient:
        return self.client_factory(self.config_manager.snapshot().cli_prefix)

    @staticmethod
    def _ordered_unique(messages: tuple[ChatMessage, ...]) -> list[ChatMessage]:
        unique: dict[str, ChatMessage] = {}
        for message in messages:
            if message.msg_id and message.msg_id not in unique:
                unique[message.msg_id] = message
        return sorted(unique.values(), key=_message_key)

    def _process(self, group_id: str, messages: list[ChatMessage]) -> None:
        for message in messages:
            self.processor.process(message)
            if self.config_manager.snapshot().log_group_message_content:
                self.message_record_writer.write(group_id, message)
                log_content = content_for_logging(message)
                content = log_content[:4096]
                if len(log_content) > 4096:
                    content += "…"
                LOGGER.info(
                    "event=group_message group_id=%s msg_id=%s content=%s",
                    group_id,
                    message.msg_id,
                    json.dumps(content, ensure_ascii=False),
                )

    @staticmethod
    def _log_failure(group_id: str, exc: Exception) -> None:
        category = exc.category if isinstance(exc, CliError) else type(exc).__name__
        exit_code = exc.exit_code if isinstance(exc, CliError) else None
        LOGGER.error(
            "event=history_query_failed group_id=%s error_category=%s exit_code=%s error=%s",
            group_id,
            category,
            exit_code,
            str(exc)[:500],
        )

    @staticmethod
    def _max_message_id(messages: list[ChatMessage]) -> str | None:
        values = [message.msg_id for message in messages if message.msg_id]
        return max(values, key=_id_key) if values else None

    @staticmethod
    def _log_complete(group_id: str, count: int, query_type: str) -> None:
        LOGGER.info(
            "event=history_query_completed group_id=%s message_count=%s query_type=%s",
            group_id,
            count,
            query_type,
        )
