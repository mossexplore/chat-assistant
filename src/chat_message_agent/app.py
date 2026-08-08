from __future__ import annotations

import logging
import sys
import threading
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from werkzeug.serving import BaseWSGIServer, make_server

from .config import ConfigManager
from .logging_setup import OPERATIONS_LOGGER_NAME, setup_logging
from .message_log import FileMessageRecordWriter
from .processor import NoOpMessageProcessor
from .scheduler import QueryScheduler
from .state import StateStore
from .version import __version__
from .web.routes import create_web_app

LOGGER = logging.getLogger(__name__)
OPERATIONS_LOGGER = logging.getLogger(OPERATIONS_LOGGER_NAME)


def default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


@dataclass(slots=True)
class Application:
    config_manager: ConfigManager
    state_store: StateStore
    scheduler: QueryScheduler
    server: BaseWSGIServer
    url: str

    def run(self, *, open_browser: bool = True) -> None:
        self.scheduler.start()
        if open_browser:
            threading.Timer(0.35, self._open_browser).start()
        OPERATIONS_LOGGER.info(
            "application_started version=%s url=%s",
            __version__,
            self.url,
        )
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            OPERATIONS_LOGGER.info("shutdown_requested")
        finally:
            self.scheduler.stop()
            self.server.server_close()
            OPERATIONS_LOGGER.info("application_stopped")

    def _open_browser(self) -> None:
        try:
            if not webbrowser.open(self.url, new=2):
                LOGGER.warning("event=browser_open_failed url=%s", self.url)
        except Exception:
            LOGGER.exception("event=browser_open_failed url=%s", self.url)


def build_application(*, data_dir: Path | None = None, port: int = 8765) -> Application:
    data_dir = (data_dir or default_data_dir()).resolve()
    setup_logging(data_dir)
    config_manager = ConfigManager(data_dir)
    config_manager.load()
    state_store = StateStore(data_dir)
    state_store.load()
    scheduler = QueryScheduler(
        config_manager,
        state_store,
        NoOpMessageProcessor(),
        message_record_writer=FileMessageRecordWriter(data_dir),
    )
    flask_app = create_web_app(config_manager, scheduler)
    try:
        server = make_server("127.0.0.1", port, flask_app, threaded=True)
    except (OSError, SystemExit) as exc:
        raise RuntimeError(f"无法监听 127.0.0.1:{port}，端口可能已被占用：{exc}") from exc
    return Application(
        config_manager=config_manager,
        state_store=state_store,
        scheduler=scheduler,
        server=server,
        url=f"http://127.0.0.1:{server.server_port}/",
    )
