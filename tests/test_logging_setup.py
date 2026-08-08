import logging

from chat_message_agent.logging_setup import LOG_FORMAT, setup_logging


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


def test_operations_log_is_separate_from_app_log(tmp_path):
    root = logging.getLogger()
    operations = logging.getLogger("operations")
    previous_root_handlers = root.handlers[:]
    previous_operations_handlers = operations.handlers[:]
    previous_operations_level = operations.level
    previous_operations_propagate = operations.propagate

    try:
        setup_logging(tmp_path)
        logging.getLogger("operations").info("config_updated changed_fields=initial_query_count")
        logging.getLogger("scheduler").info("[123] sender ➔ content")
        for logger in (root, operations):
            for handler in logger.handlers:
                handler.flush()

        app_log = (tmp_path / "logs" / "app.log").read_text(encoding="utf-8")
        operations_log = (tmp_path / "logs" / "operations.log").read_text(
            encoding="utf-8"
        )
        assert "[123] sender ➔ content" in app_log
        assert "config_updated" not in app_log
        assert "config_updated changed_fields=initial_query_count" in operations_log
        assert "[123] sender ➔ content" not in operations_log
    finally:
        for handler in root.handlers + operations.handlers:
            if handler not in previous_root_handlers + previous_operations_handlers:
                handler.close()
        root.handlers[:] = previous_root_handlers
        operations.handlers[:] = previous_operations_handlers
        operations.setLevel(previous_operations_level)
        operations.propagate = previous_operations_propagate
