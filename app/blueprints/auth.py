"""认证与基础状态路由。"""

from __future__ import annotations

from flask import Blueprint, jsonify, request, session

from app.services.auth_service import create_user, verify_user
from app.utils.login_required import current_user
from src.config import Config

bp = Blueprint("auth", __name__)


@bp.post("/api/auth/register")
def api_auth_register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    ok, message = create_user(username, password)
    if not ok:
        return jsonify({"ok": False, "message": message}), 400
    return jsonify({"ok": True, "message": message})


@bp.post("/api/auth/login")
def api_auth_login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = verify_user(username, password)
    if not user:
        return jsonify({"ok": False, "message": "用户名或密码错误。"}), 400

    session["user_id"] = int(user["id"])
    session["username"] = str(user["username"])
    return jsonify({"ok": True, "message": "登录成功", "user": user})


@bp.post("/api/auth/logout")
def api_auth_logout():
    session.pop("user_id", None)
    session.pop("username", None)
    return jsonify({"ok": True, "message": "已退出登录"})


@bp.get("/api/auth/me")
def api_auth_me():
    user = current_user()
    if not user:
        return jsonify({"ok": True, "logged_in": False})
    return jsonify({"ok": True, "logged_in": True, "user": user})


@bp.get("/api/status")
def api_status():
    cfg = Config.load()
    user = current_user()
    return jsonify(
        {
            "ok": True,
            "logged_in": bool(user),
            "username": (user or {}).get("username", ""),
            "has_cookie": bool(cfg.cookie),
            "ai_configured": bool(cfg.ai_api_key),
            "ai_model": cfg.ai_model,
        }
    )
