from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest

from ..config import ConfigManager
from ..errors import PersistenceError, ValidationError
from ..logging_setup import OPERATIONS_LOGGER_NAME
from ..scheduler import QueryScheduler
from ..version import __version__

OPERATIONS_LOGGER = logging.getLogger(OPERATIONS_LOGGER_NAME)
CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "cli_prefix",
        "scheduled_query_enabled",
        "target_group_ids",
        "log_group_message_content",
        "query_interval_seconds",
        "initial_query_count",
    }
)


def create_web_app(config_manager: ConfigManager, scheduler: QueryScheduler) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.update(DEBUG=False, TESTING=False, JSON_AS_ASCII=False)

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify(status="ok", version=__version__, **scheduler.status())

    @app.get("/api/config")
    def get_config():
        return jsonify(
            config=config_manager.as_dict(),
            version=__version__,
            status=scheduler.status(),
            load_error=config_manager.load_error,
        )

    @app.put("/api/config")
    def put_config():
        if not request.is_json:
            OPERATIONS_LOGGER.warning("config_update_rejected reason=content_type")
            return jsonify(error="请求必须使用 application/json", fields={}), 415
        before = config_manager.as_dict()
        try:
            raw = request.get_json(silent=False)
            config_manager.save(raw)
        except BadRequest:
            OPERATIONS_LOGGER.warning("config_update_rejected reason=malformed_json")
            return jsonify(error="请求 JSON 格式无效", fields={}), 400
        except ValidationError as exc:
            fields = ",".join(sorted(exc.errors)) or "request"
            OPERATIONS_LOGGER.warning(
                "config_update_rejected reason=validation fields=%s",
                fields,
            )
            return jsonify(error=str(exc), fields=exc.errors), 400
        except PersistenceError as exc:
            OPERATIONS_LOGGER.error(
                "config_update_failed error_category=persistence error=%s",
                str(exc)[:300].replace("\r", " ").replace("\n", " "),
            )
            return jsonify(error=f"配置保存失败：{exc}", fields={}), 500
        except Exception:
            OPERATIONS_LOGGER.exception(
                "config_update_failed error_category=unexpected"
            )
            return jsonify(error="配置保存失败，请查看日志", fields={}), 500
        current = config_manager.as_dict()
        changed_fields = ",".join(
            sorted(field for field in CONFIG_FIELDS if before.get(field) != current.get(field))
        )
        OPERATIONS_LOGGER.info(
            "config_updated changed_fields=%s",
            changed_fields or "none",
        )
        return jsonify(success=True, config=current, message="配置已保存并生效")

    return app
