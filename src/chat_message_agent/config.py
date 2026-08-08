from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .errors import PersistenceError, ValidationError
from .storage import atomic_write_json

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AppConfig:
    schema_version: int = 1
    cli_prefix: str = "chat-cli"
    scheduled_query_enabled: bool = False
    target_group_id: str = ""
    query_interval_seconds: int = 30
    initial_query_count: int = 20


KNOWN_FIELDS = {item.name for item in fields(AppConfig)}


def validate_config(value: Any) -> AppConfig:
    if not isinstance(value, dict):
        raise ValidationError("配置必须是 JSON 对象", errors={"_": "必须是 JSON 对象"})

    errors: dict[str, str] = {}
    required = KNOWN_FIELDS - {"schema_version"}
    for name in required:
        if name not in value:
            errors[name] = "缺少此字段"

    schema_version = value.get("schema_version", 1)
    cli_prefix = value.get("cli_prefix")
    enabled = value.get("scheduled_query_enabled")
    group_id = value.get("target_group_id")
    interval = value.get("query_interval_seconds")
    count = value.get("initial_query_count")

    if type(schema_version) is not int or schema_version < 1:
        errors["schema_version"] = "必须是大于等于 1 的整数"
    if not isinstance(cli_prefix, str) or not cli_prefix.strip():
        errors["cli_prefix"] = "消息命令前缀不能为空"
    elif any(char in cli_prefix for char in ("\n", "\r", "|", ">", "<", ";", "&")):
        errors["cli_prefix"] = "只能填写一个可执行文件名或绝对路径，不能包含命令操作符"
    if type(enabled) is not bool:
        errors["scheduled_query_enabled"] = "必须是布尔值"
    if not isinstance(group_id, str):
        errors["target_group_id"] = "必须是字符串"
    elif enabled is True and (not group_id or not group_id.isdecimal()):
        errors["target_group_id"] = "启用定时查询时必须填写数字群组 ID"
    if type(interval) is not int or not 5 <= interval <= 86400:
        errors["query_interval_seconds"] = "必须是 5 到 86400 之间的整数"
    if type(count) is not int or not 1 <= count <= 100:
        errors["initial_query_count"] = "必须是 1 到 100 之间的整数"
    if errors:
        raise ValidationError("配置校验失败", errors=errors)

    return AppConfig(
        schema_version=schema_version,
        cli_prefix=cli_prefix.strip(),
        scheduled_query_enabled=enabled,
        target_group_id=group_id,
        query_interval_seconds=interval,
        initial_query_count=count,
    )


class ConfigManager:
    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "config.json"
        self._lock = threading.RLock()
        self._config = AppConfig()
        self._extras: dict[str, Any] = {}
        self._listeners: list[Callable[[AppConfig], None]] = []
        self.load_error: str | None = None

    def load(self) -> AppConfig:
        if not self.path.exists():
            try:
                self._persist(AppConfig(), {})
            except PersistenceError as exc:
                self.load_error = f"无法创建默认配置，当前配置无法持久化：{exc}"
                LOGGER.error(self.load_error)
            return self.snapshot()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            config = validate_config(raw)
        except (OSError, json.JSONDecodeError, UnicodeError, ValidationError) as exc:
            self.load_error = f"配置文件读取失败，当前使用安全默认配置：{exc}"
            LOGGER.error(self.load_error)
            with self._lock:
                self._config = AppConfig()
                self._extras = {}
            return self.snapshot()
        with self._lock:
            self._config = config
            self._extras = {key: val for key, val in raw.items() if key not in KNOWN_FIELDS}
            self.load_error = None
        return config

    def snapshot(self) -> AppConfig:
        with self._lock:
            return self._config

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return {**self._extras, **asdict(self._config)}

    def subscribe(self, listener: Callable[[AppConfig], None]) -> None:
        with self._lock:
            self._listeners.append(listener)

    def save(self, raw: Any) -> AppConfig:
        config = validate_config(raw)
        with self._lock:
            extras = {**self._extras, **{k: v for k, v in raw.items() if k not in KNOWN_FIELDS}}
        self._persist(config, extras)
        with self._lock:
            self._config = config
            self._extras = extras
            self.load_error = None
            listeners = tuple(self._listeners)
        for listener in listeners:
            try:
                listener(config)
            except Exception:
                LOGGER.exception("event=config_listener_failed")
        return config

    def _persist(self, config: AppConfig, extras: dict[str, Any]) -> None:
        try:
            atomic_write_json(self.path, {**extras, **asdict(config)})
        except PersistenceError:
            raise
