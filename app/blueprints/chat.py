"""求职对话/任务路由。"""

from __future__ import annotations

import threading

from flask import Blueprint, current_app, jsonify, request

from app.services.pipeline_service import run_pipeline_task
from app.utils.login_required import require_login
from app.utils.task_tracker import get_task, new_task_record

bp = Blueprint("chat", __name__)


@bp.post("/api/chat")
def api_chat():
    user, err = require_login()
    if err:
        return err

    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message:
        return jsonify({"ok": False, "message": "消息不能为空"}), 400

    task_id = new_task_record(message)
    worker = threading.Thread(
        target=run_pipeline_task,
        args=(current_app._get_current_object(), task_id, message),
        daemon=True,
    )
    worker.start()

    return jsonify({"ok": True, "task_id": task_id, "message": "任务已启动"})


@bp.get("/api/chat/task/<task_id>")
def api_chat_task(task_id: str):
    user, err = require_login()
    if err:
        return err

    task = get_task(task_id)
    if not task:
        return jsonify({"ok": False, "message": "任务不存在"}), 404
    if int(task.get("owner_user_id") or 0) != int(user.get("id") or 0):
        return jsonify({"ok": False, "message": "无权访问该任务"}), 403
    return jsonify({"ok": True, "task": task})
