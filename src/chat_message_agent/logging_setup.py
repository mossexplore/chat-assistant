from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
OPERATIONS_LOGGER_NAME = "operations"


def setup_logging(data_dir: Path) -> None:
    formatter = logging.Formatter(LOG_FORMAT)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    operations = logging.getLogger(OPERATIONS_LOGGER_NAME)
    operations.setLevel(logging.INFO)
    operations.handlers.clear()
    operations.propagate = False
    operations_console = logging.StreamHandler()
    operations_console.setFormatter(formatter)
    operations.addHandler(operations_console)

    try:
        log_dir = data_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        app_file_handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        app_file_handler.setFormatter(formatter)
        root.addHandler(app_file_handler)

        operations_file_handler = RotatingFileHandler(
            log_dir / "operations.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        operations_file_handler.setFormatter(formatter)
        operations.addHandler(operations_file_handler)
    except OSError as exc:
        print(f"警告：无法创建文件日志，将仅使用控制台日志：{exc}", file=sys.stderr)
