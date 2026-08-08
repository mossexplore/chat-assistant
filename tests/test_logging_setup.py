import logging

from chat_message_agent.logging_setup import LOG_FORMAT


def test_app_log_formatter_uses_readable_separators():
    record = logging.LogRecord(
        name="scheduler",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="[987432812330259203] a123456 ➔ 哈哈",
        args=(),
        exc_info=None,
    )
    rendered = logging.Formatter(LOG_FORMAT).format(record)
    assert " - INFO - scheduler - [987432812330259203] a123456 ➔ 哈哈" in rendered
