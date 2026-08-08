import json
import subprocess
from pathlib import Path

import pytest

from chat_message_agent.cli_client import ChatCliClient, SubprocessRunner, _decode
from chat_message_agent.errors import (
    CliNotFoundError,
    CliProcessError,
    CliTimeoutError,
    ValidationError,
)


class FakeRunner:
    def __init__(self, response=None):
        self.response = response or json.dumps(
            {"resultCode": "0", "resultContext": "", "respData": {"msgId": "1"}}
        )
        self.calls = []

    def run(self, args, timeout):
        self.calls.append((list(args), timeout))
        return self.response


def test_send_group_builds_argument_array_and_normalizes_file(tmp_path):
    attachment = tmp_path / "文件.txt"
    attachment.write_text("x", encoding="utf-8")
    runner = FakeRunner()
    client = ChatCliClient(r"C:\Program Files\Chat\chat-cli.exe", runner=runner)
    client.send_to_group("987432812330259203", text="你好", file=attachment)
    args, timeout = runner.calls[0]
    assert args[:5] == [
        r"C:\Program Files\Chat\chat-cli.exe",
        "im",
        "send-to-group",
        "--group-id",
        "987432812330259203",
    ]
    assert args[-2:] == ["--file", str(attachment.resolve())]
    assert timeout == 30


def test_send_validation_happens_before_runner(tmp_path):
    runner = FakeRunner()
    client = ChatCliClient("chat-cli", runner=runner)
    with pytest.raises(ValidationError):
        client.send_to_user("alice")
    with pytest.raises(ValidationError):
        client.send_to_user("alice", image=Path(tmp_path / "missing.png"))
    assert runner.calls == []


def test_query_history_incremental_arguments():
    runner = FakeRunner(
        json.dumps(
            {"resultCode": "0", "resultContext": "", "respData": {"chatInfo": []}}
        )
    )
    client = ChatCliClient("chat-cli", runner=runner)
    client.query_history_messages(
        group_id="123", query_count=100, message_id="456", query_direction=1
    )
    assert runner.calls[0][0] == [
        "chat-cli",
        "im",
        "query-history-message",
        "--group-id",
        "123",
        "--query-count",
        "100",
        "--message-id",
        "456",
        "--query-direction",
        "1",
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"group_id": "1", "user_account": "u"},
        {"group_id": "1", "query_count": 0},
        {"group_id": "1", "message_id": "2"},
        {"group_id": "1", "message_id": "2", "query_direction": 3},
    ],
)
def test_query_validation(kwargs):
    with pytest.raises(ValidationError):
        ChatCliClient("chat-cli", runner=FakeRunner()).query_history_messages(**kwargs)


def test_subprocess_runner_maps_not_found(monkeypatch):
    def missing(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(CliNotFoundError):
        SubprocessRunner().run(["missing-cli"], 1)


def test_subprocess_runner_maps_timeout(monkeypatch):
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("chat-cli", 1)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(CliTimeoutError):
        SubprocessRunner().run(["chat-cli"], 1)


def test_subprocess_runner_maps_nonzero_exit(monkeypatch):
    completed = subprocess.CompletedProcess(["chat-cli"], 7, b"", "失败".encode())
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: completed)
    with pytest.raises(CliProcessError) as caught:
        SubprocessRunner().run(["chat-cli"], 1)
    assert caught.value.exit_code == 7
    assert "失败" in str(caught.value)


def test_query_history_logs_count_and_elapsed_seconds_on_one_line(monkeypatch, caplog):
    runner = FakeRunner(
        json.dumps(
            {
                "resultCode": "0",
                "resultContext": "Operate Success",
                "respData": {
                    "chatInfo": [
                        {"msgId": "1", "content": "one"},
                        {"msgId": "2", "content": "two"},
                    ],
                    "msgTotalCount": 2,
                },
            }
        )
    )
    timestamps = iter((10.0, 18.092))
    monkeypatch.setattr(
        "chat_message_agent.cli_client.time.perf_counter", lambda: next(timestamps)
    )
    with caplog.at_level("INFO"):
        ChatCliClient("chat-cli", runner=runner).query_history_messages(
            group_id="987432812330259203",
            query_count=2,
        )
    matching = [record for record in caplog.records if "elapsed_seconds" in record.getMessage()]
    assert len(matching) == 1
    assert matching[0].name == "cliclient"
    assert matching[0].getMessage() == (
        "[987432812330259203] count=2 elapsed_seconds=8.092"
    )


def test_cli_client_logs_timeout_elapsed_seconds(monkeypatch, caplog):
    class TimeoutRunner:
        def run(self, _args, _timeout):
            raise CliTimeoutError("timeout")

    timestamps = iter((20.0, 50.25))
    monkeypatch.setattr(
        "chat_message_agent.cli_client.time.perf_counter", lambda: next(timestamps)
    )
    with caplog.at_level("ERROR"), pytest.raises(CliTimeoutError):
        ChatCliClient("chat-cli", runner=TimeoutRunner()).send_to_group("123", text="hello")
    assert "operation=send-to-group failed" in caplog.text
    assert "elapsed_seconds=30.250" in caplog.text
    assert "error_category=cli_timeout" in caplog.text


def test_decode_falls_back_to_system_encoding(monkeypatch):
    monkeypatch.setattr(
        "chat_message_agent.cli_client.locale.getpreferredencoding", lambda _: "latin1"
    )
    assert _decode(b"caf\xe9") == "café"
