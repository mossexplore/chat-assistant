from __future__ import annotations

import json
import re
from typing import Any

from .errors import ChatServiceError, CliOutputParseError
from .models import ChatMessage, HistoryQueryResult, SendResult

STATUS_PATTERN = re.compile(r"(?im)^\s*status_code\s*:\s*(\d+)\s*$")
BODY_PATTERN = re.compile(r"(?im)^\s*resp_body\s*:\s*")


def parse_cli_output(output: str) -> tuple[int | None, dict[str, Any]]:
    text = output.strip()
    if not text:
        raise CliOutputParseError("CLI 未返回可解析内容")

    status_match = STATUS_PATTERN.search(text)
    body_match = BODY_PATTERN.search(text)
    status_code = int(status_match.group(1)) if status_match else None
    candidate = text[body_match.end() :].strip() if body_match else text
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        value = _find_json_object(candidate)
    if not isinstance(value, dict):
        raise CliOutputParseError("CLI JSON 顶层必须是对象")
    return status_code, value


def _find_json_object(text: str) -> Any:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
            return value
        except json.JSONDecodeError:
            continue
    raise CliOutputParseError("CLI 输出不是有效 JSON")


def _result_fields(body: dict[str, Any]) -> tuple[str, str, Any]:
    result_code = str(body.get("resultCode", body.get("result_code", "")))
    result_context = str(body.get("resultContext", body.get("result_context", "")))
    if result_code != "0":
        raise ChatServiceError(f"聊天服务返回失败 resultCode={result_code}: {result_context[:300]}")
    if "respData" not in body and "resp_data" not in body:
        raise CliOutputParseError("成功响应缺少 respData")
    return result_code, result_context, body.get("respData", body.get("resp_data"))


def parse_send_result(output: str) -> SendResult:
    status_code, body = parse_cli_output(output)
    result_code, context, data = _result_fields(body)
    items = data if isinstance(data, list) else [data]
    message_ids: list[str] = []
    server_time: str | int | None = None
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("msgId", item.get("messageId", item.get("message_id")))
        if value is not None:
            message_ids.append(str(value))
        if server_time is None:
            server_time = item.get("serverSendTime", item.get("server_send_time"))
    return SendResult(
        success=True,
        result_code=result_code,
        result_context=context,
        status_code=status_code,
        message_ids=tuple(message_ids),
        server_send_time=server_time,
        raw=body,
    )


def parse_history_result(output: str) -> HistoryQueryResult:
    status_code, body = parse_cli_output(output)
    result_code, context, data = _result_fields(body)
    if not isinstance(data, dict):
        raise CliOutputParseError("成功响应的 respData 必须是对象")

    total_count = _message_total_count(data)
    if "chatInfo" not in data:
        if total_count == 0:
            chat_info: Any = []
        else:
            raise CliOutputParseError("有新消息的成功响应缺少 respData.chatInfo")
    else:
        chat_info = data["chatInfo"]

    if isinstance(chat_info, dict):
        for key in ("messages", "messageList", "chatInfoList", "list"):
            if isinstance(chat_info.get(key), list):
                chat_info = chat_info[key]
                break
    if not isinstance(chat_info, list):
        raise CliOutputParseError("respData.chatInfo 必须是消息列表")

    messages = tuple(_to_message(item) for item in chat_info if isinstance(item, dict))
    if total_count is not None and total_count > 0 and not any(
        message.msg_id for message in messages
    ):
        raise CliOutputParseError("msgTotalCount 大于 0，但响应中没有有效消息")
    ids = [message.msg_id for message in messages if message.msg_id]
    max_id = data.get("maxMsgId", data.get("max_message_id"))
    min_id = data.get("minMsgId", data.get("min_message_id"))
    return HistoryQueryResult(
        success=True,
        result_code=result_code,
        result_context=context,
        status_code=status_code,
        messages=messages,
        max_message_id=str(max_id) if max_id is not None else _max_id(ids),
        min_message_id=str(min_id) if min_id is not None else _min_id(ids),
        total_count=total_count if total_count is not None else len(messages),
        raw=body,
    )


def _message_total_count(data: dict[str, Any]) -> int | None:
    for key in ("msgTotalCount", "totalCount", "total_count"):
        if key not in data:
            continue
        value = data[key]
        if type(value) is int and value >= 0:
            return value
        if isinstance(value, str) and value.isdecimal():
            return int(value)
        raise CliOutputParseError(f"respData.{key} 必须是非负整数")
    return None


def _to_message(item: dict[str, Any]) -> ChatMessage:
    at_list = item.get("atAccountList", item.get("at_account_list", []))
    if not isinstance(at_list, list):
        at_list = []
    return ChatMessage(
        msg_id=str(item.get("msgId", item.get("messageId", item.get("msg_id", "")))),
        content=str(item.get("content", "")),
        group_type=str(item.get("groupType", item.get("group_type", ""))),
        content_type=str(item.get("contentType", item.get("content_type", ""))),
        sender=str(item.get("sender", item.get("senderAccount", ""))),
        receiver=str(item.get("receiver", item.get("receiverAccount", ""))),
        group_id=str(item.get("groupId", item.get("group_id", ""))),
        server_send_time=item.get("serverSendTime", item.get("server_send_time", "")),
        at=bool(item.get("at", item.get("isAt", False))),
        at_account_list=tuple(str(value) for value in at_list),
        raw=item,
    )


def _id_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdecimal() else (1, value)


def _max_id(values: list[str]) -> str | None:
    return max(values, key=_id_key) if values else None


def _min_id(values: list[str]) -> str | None:
    return min(values, key=_id_key) if values else None
