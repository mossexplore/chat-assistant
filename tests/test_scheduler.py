from dataclasses import replace

import pytest

from chat_message_agent.config import AppConfig, ConfigManager
from chat_message_agent.models import ChatMessage, HistoryQueryResult
from chat_message_agent.processor import NoOpMessageProcessor
from chat_message_agent.scheduler import QueryScheduler
from chat_message_agent.state import StateStore


def result(ids, *, max_id=None):
    messages = tuple(
        ChatMessage(msg_id=str(value), server_send_time=0, content=str(value)) for value in ids
    )
    return HistoryQueryResult(
        success=True,
        result_code="0",
        result_context="",
        status_code=200,
        messages=messages,
        max_message_id=max_id,
        min_message_id=str(ids[0]) if ids else None,
        total_count=len(messages),
    )


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def query_history_messages(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


class Collector:
    def __init__(self, fail_on=None):
        self.ids = []
        self.fail_on = fail_on

    def process(self, message):
        if message.msg_id == self.fail_on:
            raise RuntimeError("processor failed")
        self.ids.append(message.msg_id)


def make_scheduler(tmp_path, client, processor=None, *, count=2, max_pages=100):
    manager = ConfigManager(tmp_path)
    manager.load()
    config = AppConfig(
        scheduled_query_enabled=True,
        target_group_id="999",
        initial_query_count=count,
    )
    manager.save(
        {
            "schema_version": config.schema_version,
            "cli_prefix": config.cli_prefix,
            "scheduled_query_enabled": config.scheduled_query_enabled,
            "target_group_id": config.target_group_id,
            "query_interval_seconds": config.query_interval_seconds,
            "initial_query_count": config.initial_query_count,
        }
    )
    state = StateStore(tmp_path)
    state.load()
    scheduler = QueryScheduler(
        manager,
        state,
        processor or NoOpMessageProcessor(),
        client_factory=lambda _prefix: client,
        max_pages=max_pages,
    )
    return scheduler, state, config


def test_initial_query_sorts_deduplicates_and_saves_cursor(tmp_path):
    client = FakeClient([result([3, 1, 3, 2], max_id="3")])
    collector = Collector()
    scheduler, state, config = make_scheduler(tmp_path, client, collector, count=10)
    scheduler.run_query_cycle(config)
    assert collector.ids == ["1", "2", "3"]
    assert state.get_cursor("999") == "3"
    assert client.calls == [{"group_id": "999", "query_count": 10}]


def test_incremental_query_filters_cursor_and_paginates(tmp_path):
    client = FakeClient([result([10, 11]), result([11, 12]), result([])])
    collector = Collector()
    scheduler, state, config = make_scheduler(tmp_path, client, collector, count=2)
    state.set_cursor("999", "10")
    scheduler.run_query_cycle(config)
    assert collector.ids == ["11", "12"]
    assert state.get_cursor("999") == "12"
    assert all(call["query_direction"] == 1 for call in client.calls)
    assert [call["message_id"] for call in client.calls] == ["10", "11", "12"]


def test_processor_failure_does_not_advance_page_cursor(tmp_path):
    client = FakeClient([result([11, 12])])
    scheduler, state, config = make_scheduler(tmp_path, client, Collector(fail_on="12"))
    state.set_cursor("999", "10")
    with pytest.raises(RuntimeError):
        scheduler.run_query_cycle(config)
    assert state.get_cursor("999") == "10"


def test_page_limit_stops_infinite_full_pages(tmp_path):
    client = FakeClient([result([11]), result([12])])
    scheduler, state, config = make_scheduler(tmp_path, client, count=1, max_pages=2)
    state.set_cursor("999", "10")
    scheduler.run_query_cycle(config)
    assert len(client.calls) == 2
    assert state.get_cursor("999") == "12"


def test_group_switch_uses_independent_cursor(tmp_path):
    client = FakeClient([result([], max_id=None)])
    scheduler, state, config = make_scheduler(tmp_path, client)
    state.set_cursor("999", "10")
    state.set_cursor("888", "25")
    scheduler.run_query_cycle(replace(config, target_group_id="888"))
    assert client.calls[0]["message_id"] == "25"
