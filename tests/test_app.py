import logging

from chat_message_agent.app import Application
from chat_message_agent.version import __version__


class FakeScheduler:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


class FakeServer:
    def __init__(self):
        self.closed = False

    def serve_forever(self):
        return None

    def server_close(self):
        self.closed = True


def test_startup_and_shutdown_use_operations_logger(caplog):
    scheduler = FakeScheduler()
    server = FakeServer()
    application = Application(
        config_manager=None,  # type: ignore[arg-type]
        state_store=None,  # type: ignore[arg-type]
        scheduler=scheduler,  # type: ignore[arg-type]
        server=server,  # type: ignore[arg-type]
        url="http://127.0.0.1:8765/",
    )

    with caplog.at_level(logging.INFO, logger="operations"):
        application.run(open_browser=False)

    assert scheduler.started is True
    assert scheduler.stopped is True
    assert server.closed is True
    records = [record for record in caplog.records if record.name == "operations"]
    assert records[0].getMessage() == (
        f"application_started version={__version__} url=http://127.0.0.1:8765/"
    )
    assert records[-1].getMessage() == "application_stopped"
