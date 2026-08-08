from chat_message_agent.config import ConfigManager
from chat_message_agent.processor import NoOpMessageProcessor
from chat_message_agent.scheduler import QueryScheduler
from chat_message_agent.state import StateStore
from chat_message_agent.web.routes import create_web_app


def make_client(tmp_path):
    manager = ConfigManager(tmp_path)
    manager.load()
    state = StateStore(tmp_path)
    state.load()
    scheduler = QueryScheduler(manager, state, NoOpMessageProcessor())
    app = create_web_app(manager, scheduler)
    app.config["TESTING"] = True
    return app.test_client(), manager


def valid_payload(**changes):
    payload = {
        "schema_version": 1,
        "cli_prefix": "chat-cli",
        "scheduled_query_enabled": False,
        "target_group_id": "",
        "query_interval_seconds": 30,
        "initial_query_count": 20,
    }
    payload.update(changes)
    return payload


def test_page_and_health_are_local_assets(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "聊天消息查询程序" in response.get_data(as_text=True)
    assert "Content-Security-Policy" in response.headers
    assert client.get("/api/health").json["status"] == "ok"


def test_get_and_put_config(tmp_path):
    client, manager = make_client(tmp_path)
    assert client.get("/api/config").json["config"]["cli_prefix"] == "chat-cli"
    response = client.put("/api/config", json=valid_payload(query_interval_seconds=55))
    assert response.status_code == 200
    assert manager.snapshot().query_interval_seconds == 55


def test_put_config_returns_field_errors(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.put(
        "/api/config",
        json=valid_payload(scheduled_query_enabled=True, target_group_id="not-number"),
    )
    assert response.status_code == 400
    assert "target_group_id" in response.json["fields"]


def test_put_requires_json(tmp_path):
    client, _ = make_client(tmp_path)
    assert client.put("/api/config", data="x").status_code == 415


def test_put_rejects_malformed_json(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.put(
        "/api/config", data="{broken", content_type="application/json"
    )
    assert response.status_code == 400
