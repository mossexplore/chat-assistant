from __future__ import annotations

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import BadRequest

from ..config import ConfigManager
from ..errors import PersistenceError, ValidationError
from ..scheduler import QueryScheduler
from ..version import __version__


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
            return jsonify(error="请求必须使用 application/json", fields={}), 415
        try:
            raw = request.get_json(silent=False)
            config_manager.save(raw)
        except BadRequest:
            return jsonify(error="请求 JSON 格式无效", fields={}), 400
        except ValidationError as exc:
            return jsonify(error=str(exc), fields=exc.errors), 400
        except PersistenceError as exc:
            return jsonify(error=f"配置保存失败：{exc}", fields={}), 500
        except Exception:
            app.logger.exception("event=config_save_unexpected_error")
            return jsonify(error="配置保存失败，请查看日志", fields={}), 500
        return jsonify(success=True, config=config_manager.as_dict(), message="配置已保存并生效")

    return app
