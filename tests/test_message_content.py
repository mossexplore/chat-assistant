import json

from chat_message_agent.cli_parser import parse_history_result
from chat_message_agent.message_content import content_for_logging
from chat_message_agent.models import ChatMessage


def quoted_reply_message() -> ChatMessage:
    content = json.dumps(
        {
            "cardContext": {
                "preMsg": {
                    "messageID": "89308543473293353",
                    "nameEN": "Zhang San",
                    "nameZH": "张三",
                    "sender": "a123456",
                    "type": 0,
                    "content": "我知道了，这个就是那样的",
                },
                "replyMsg": {
                    "content": "好的",
                    "type": 0,
                    "PcContent": "<FONT>好的</FONT>",
                },
            },
            "cardType": 65,
            "isShowSource": 0,
        },
        ensure_ascii=False,
    )
    return ChatMessage(msg_id="89308574058460924", content_type="CARD_MSG", content=content)


def test_quoted_card_message_is_rendered_as_reply_and_source():
    message = quoted_reply_message()
    assert content_for_logging(message) == "好的↩我知道了，这个就是那样的"
    assert "cardContext" in message.content


def test_malformed_or_unrelated_content_falls_back_to_original():
    malformed = ChatMessage(msg_id="1", content_type="CARD_MSG", content="{broken")
    plain = ChatMessage(msg_id="2", content_type="TEXT", content="普通消息")
    assert content_for_logging(malformed) == "{broken"
    assert content_for_logging(plain) == "普通消息"


def test_cli_quoted_reply_sample_is_parsed_for_logging():
    quoted = quoted_reply_message()
    output = json.dumps(
        {
            "respData": {
                "chatInfo": [
                    {
                        "at": False,
                        "atAccountList": [],
                        "content": quoted.content,
                        "contentType": "CARD_MSG",
                        "groupId": 987432812330259203,
                        "groupType": 1,
                        "msgId": 89308574058460924,
                        "receiver": "",
                        "sender": "l00976096",
                        "serverSendTime": 1786171481169,
                    }
                ],
                "maxMsgId": 89308574058460924,
                "minMsgId": 89308574058460924,
                "msgTotalCount": 1,
            },
            "resultCode": "0",
            "resultContext": "Operate Success",
            "sno": None,
        }
    )
    message = parse_history_result(output).messages[0]
    assert message.group_type == "1"
    assert content_for_logging(message) == "好的↩我知道了，这个就是那样的"
