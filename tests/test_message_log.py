from datetime import UTC, datetime

from chat_message_agent.message_log import FileMessageRecordWriter
from chat_message_agent.models import ChatMessage


def test_full_message_log_uses_required_field_order_and_escaping(tmp_path):
    writer = FileMessageRecordWriter(
        tmp_path,
        clock=lambda: datetime(2026, 8, 8, 12, 34, 56, 123000, tzinfo=UTC),
    )
    content = "完整|消息\n第二行\\末尾" + "很长" * 3000
    writer.write(
        "fallback-group",
        ChatMessage(
            msg_id="101",
            group_type="2",
            content_type="text",
            server_send_time=1723111111,
            group_id="987654321",
            sender="alice",
            receiver="group",
            content=content,
        ),
    )
    line = (tmp_path / "logs" / "messages.log").read_text(encoding="utf-8")
    assert line.startswith(
        "2026-08-08T12:34:56.123+00:00|101|2|text|1723111111|"
        "987654321|alice|group|"
    )
    assert "完整\\|消息\\n第二行\\\\末尾" in line
    assert "很长" * 3000 in line
    assert line.count("\n") == 1


def test_full_message_log_uses_target_group_when_response_omits_group_id(tmp_path):
    writer = FileMessageRecordWriter(
        tmp_path,
        clock=lambda: datetime(2026, 8, 8, tzinfo=UTC),
    )
    writer.write("123456", ChatMessage(msg_id="1", content="hello"))
    fields = (tmp_path / "logs" / "messages.log").read_text(encoding="utf-8").split("|")
    assert fields[5] == "123456"
