"""页面路由,通过 send_from_directory 直接服务 frontend/pages/*.html。"""

from __future__ import annotations

from flask import Blueprint, current_app, send_from_directory

from app.utils.login_required import current_user

bp = Blueprint("pages", __name__)


def _send(name: str):
    return send_from_directory(str(current_app.config["PAGES_DIR"]), name)


@bp.get("/")
def index():
    return _send("home.html" if current_user() else "login.html")


@bp.get("/career")
def career_page():
    return _send("career.html" if current_user() else "login.html")


@bp.get("/job")
def job_page():
    return _send("job.html" if current_user() else "login.html")


@bp.get("/interview")
def interview_page():
    return _send("interview.html" if current_user() else "login.html")


@bp.get("/login")
def login_page():
    return _send("home.html" if current_user() else "login.html")
