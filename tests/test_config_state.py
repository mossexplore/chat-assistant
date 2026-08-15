import json

import pytest

import chat_message_agent.config as config_module
from chat_message_agent.config import AppConfig, ConfigManager
from chat_message_agent.errors import PersistenceError, ValidationError
from chat_message_agent.state import StateStore


def valid_config(**changes):
    value = {
        "schema_version": 2,
        "cli_prefix": "chat-cli",
        "scheduled_query_enabled": False,
        "target_group_ids": [],
        "log_group_message_content": False,
        "query_interval_seconds": 60,
        "initial_query_count": 2,
    }
    value.update(changes)
    return value


def test_config_creates_defaults_and_preserves_unknown_fields(tmp_path):
    manager = ConfigManager(tmp_path)
    assert manager.load() == AppConfig()
    saved_defaults = json.loads(manager.path.read_text(encoding="utf-8"))
    assert saved_defaults["schema_version"] == 2
    assert saved_defaults["query_interval_seconds"] == 60
    assert saved_defaults["initial_query_count"] == 2
    manager.save({**valid_config(), "future_option": {"enabled": True}})
    manager.save(valid_config(query_interval_seconds=60))
    saved = json.loads(manager.path.read_text(encoding="utf-8"))
    assert saved["future_option"] == {"enabled": True}


def test_invalid_config_does_not_replace_existing_file(tmp_path):
    manager = ConfigManager(tmp_path)
    manager.load()
    original = manager.path.read_bytes()
    with pytest.raises(ValidationError):
        manager.save(valid_config(scheduled_query_enabled=True, target_group_ids=["12x"]))
    assert manager.path.read_bytes() == original


def test_damaged_config_is_preserved_and_reported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    manager = ConfigManager(tmp_path)
    assert manager.load() == AppConfig()
    assert manager.load_error
    assert path.read_text(encoding="utf-8") == "{broken"


def test_unwritable_default_config_starts_with_visible_error(tmp_path, monkeypatch):
    def fail_write(_path, _data):
        raise PersistenceError("目录不可写")

    monkeypatch.setattr(config_module, "atomic_write_json", fail_write)
    manager = ConfigManager(tmp_path)
    assert manager.load() == AppConfig()
    assert "无法创建默认配置" in manager.load_error


def test_config_notifies_after_successful_persistence(tmp_path):
    manager = ConfigManager(tmp_path)
    manager.load()
    notified = []
    manager.subscribe(notified.append)
    config = manager.save(valid_config(query_interval_seconds=45))
    assert notified == [config]


def test_legacy_single_group_config_is_migrated(tmp_path):
    legacy = {
        "schema_version": 1,
        "cli_prefix": "chat-cli",
        "scheduled_query_enabled": True,
        "target_group_id": "90071992547409931",
        "query_interval_seconds": 30,
        "initial_query_count": 20,
    }
    (tmp_path / "config.json").write_text(json.dumps(legacy), encoding="utf-8")
    manager = ConfigManager(tmp_path)
    config = manager.load()
    assert config.schema_version == 2
    assert config.target_group_ids == ("90071992547409931",)
    assert config.log_group_message_content is False
    saved = json.loads(manager.path.read_text(encoding="utf-8"))
    assert saved["target_group_ids"] == ["90071992547409931"]
    assert "target_group_id" not in saved


def test_group_ids_are_trimmed_and_deduplicated(tmp_path):
    manager = ConfigManager(tmp_path)
    manager.load()
    config = manager.save(
        valid_config(target_group_ids=[" 123 ", "456", "123"])
    )
    assert config.target_group_ids == ("123", "456")


def test_state_stores_independent_string_cursors(tmp_path):
    state = StateStore(tmp_path)
    state.load()
    state.set_cursor("100", "90071992547409931")
    state.set_cursor("200", "7")
    restored = StateStore(tmp_path)
    restored.load()
    assert restored.get_cursor("100") == "90071992547409931"
    assert restored.get_cursor("200") == "7"


def test_state_can_clear_one_group_cursor(tmp_path):
    state = StateStore(tmp_path)
    state.load()
    state.set_cursor("100", "10")
    state.set_cursor("200", "20")

    state.clear_cursor("100")

    restored = StateStore(tmp_path)
    restored.load()
    assert restored.get_cursor("100") is None
    assert restored.get_cursor("200") == "20"


def test_damaged_state_recovers_on_next_write(tmp_path):
    (tmp_path / "runtime_state.json").write_text("[]", encoding="utf-8")
    state = StateStore(tmp_path)
    state.load()
    assert state.get_cursor("1") is None
    state.set_cursor("1", "2")
    assert state.get_cursor("1") == "2"
