"""职探AI Flask 应用工厂。

将原 web_app.py(2445 行)拆分为 Blueprints + services + utils 三层架构后,
本模块负责装配 Flask 实例、注册扩展与所有蓝图。
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from flask import Flask

from src.env_file import load_env

mimetypes.init()
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/javascript", ".mjs")
mimetypes.add_type("text/css", ".css")


def create_app() -> Flask:
    base_dir = Path(__file__).resolve().parent.parent

    # 优先把 .env 加载到进程环境变量,确保 SECRET_KEY 等也能从 .env 读取
    load_env(override=False)

    app = Flask(
        __name__,
        static_folder=str(base_dir / "static"),
        template_folder=None,
    )
    app.config["SECRET_KEY"] = os.environ.get(
        "CAREERAI_SECRET_KEY", "careerai-dev-secret-change-me"
    )
    app.config["BASE_DIR"] = base_dir
    app.config["PAGES_DIR"] = base_dir / "frontend" / "pages"

    from app.blueprints import auth, boss, career, chat, interview, pages, reports

    app.register_blueprint(pages.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(chat.bp)
    app.register_blueprint(boss.bp)
    app.register_blueprint(career.bp)
    app.register_blueprint(interview.bp)

    return app
