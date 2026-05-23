"""登录相关 Flask 上下文辅助函数。"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from flask import jsonify, session


def current_user() -> Dict[str, Any] | None:
    uid = session.get("user_id")
    uname = session.get("username")
    if not uid or not uname:
        return None
    return {"id": int(uid), "username": str(uname)}


def require_login() -> Tuple[Dict[str, Any] | None, Any | None]:
    user = current_user()
    if not user:
        return None, (jsonify({"ok": False, "message": "请先登录账号。"}), 401)
    return user, None
