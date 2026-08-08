import json

import pytest

from chat_message_agent.cli_parser import parse_history_result, parse_send_result
from chat_message_agent.errors import ChatServiceError, CliOutputParseError


def test_parse_send_pure_json():
    result = parse_send_result(
        json.dumps(
            {
                "resultCode": "0",
                "resultContext": "ok",
                "respData": {"msgId": "90071992547409930", "serverSendTime": 12},
            }
        )
    )
    assert result.success
    assert result.message_ids == ("90071992547409930",)
    assert result.server_send_time == 12


def test_parse_status_and_body_output_with_unicode():
    result = parse_send_result(
        'status_code: 200\nresp_body: {"resultCode":"0","resultContext":"成功",'
        '"respData":[{"msgId":"1"}]}'
    )
    assert result.status_code == 200
    assert result.result_context == "成功"


def test_parse_history_models_and_defaults():
    result = parse_history_result(
        json.dumps(
            {
                "resultCode": 0,
                "resultContext": "",
                "respData": {
                    "chatInfo": [
                        {"msgId": "10", "content": "你好", "atAccountList": ["alice"]},
                        {"msgId": "12", "serverSendTime": 4},
                    ],
                    "totalCount": 2,
                },
            }
        )
    )
    assert result.max_message_id == "12"
    assert result.min_message_id == "10"
    assert result.messages[0].sender == ""
    assert result.messages[0].at_account_list == ("alice",)


def test_parse_history_success_without_new_messages_or_chat_info():
    result = parse_history_result(
        json.dumps(
            {
                "respData": {
                    "maxMsgId": 0,
                    "minMsgId": 0,
                    "msgTotalCount": 0,
                },
                "resultCode": "0",
                "resultContext": "Operate Success",
                "sno": None,
            }
        )
    )
    assert result.success
    assert result.messages == ()
    assert result.total_count == 0
    assert result.max_message_id == "0"
    assert result.min_message_id == "0"


def test_parse_history_requires_messages_when_total_count_is_positive():
    output = json.dumps(
        {
            "respData": {"maxMsgId": 10, "minMsgId": 10, "msgTotalCount": 1},
            "resultCode": "0",
            "resultContext": "Operate Success",
        }
    )
    with pytest.raises(CliOutputParseError, match="缺少 respData.chatInfo"):
        parse_history_result(output)


@pytest.mark.parametrize(
    "output,error_type",
    [
        ("not-json", CliOutputParseError),
        ('{"resultCode":"0"}', CliOutputParseError),
        ('{"resultCode":"9","resultContext":"denied","respData":{}}', ChatServiceError),
    ],
)
def test_parse_failures(output, error_type):
    with pytest.raises(error_type):
        parse_history_result(output)
