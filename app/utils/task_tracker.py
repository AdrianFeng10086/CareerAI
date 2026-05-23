"""任务追踪相关的状态推进函数,基于 app.extensions 中的全局字典。"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from flask import session

from app.extensions import (
    CHAT_TASKS,
    MCP_LOGIN_LOCK,
    MCP_LOGIN_TASKS,
    TASK_LOCK,
)


def new_task_record(message: str) -> str:
    task_id = uuid.uuid4().hex
    with TASK_LOCK:
        CHAT_TASKS[task_id] = {
            "id": task_id,
            "ok": None,
            "status": "running",
            "progress": 0,
            "stage": "queued",
            "message": "任务已创建，准备开始...",
            "user_message": message,
            "result": None,
            "events": [],
            "next_event_id": 1,
            "owner_user_id": int(session.get("user_id") or 0),
        }
    return task_id


def update_task(
    task_id: str,
    *,
    progress: int | None = None,
    stage: str | None = None,
    message: str | None = None,
    status: str | None = None,
    ok: bool | None = None,
    result: Dict[str, Any] | None = None,
) -> None:
    with TASK_LOCK:
        task = CHAT_TASKS.get(task_id)
        if not task:
            return
        if progress is not None:
            task["progress"] = max(0, min(100, int(progress)))
        if stage is not None:
            task["stage"] = stage
        if message is not None:
            task["message"] = message
        if status is not None:
            task["status"] = status
        if ok is not None:
            task["ok"] = ok
        if result is not None:
            task["result"] = result


def get_task(task_id: str) -> Dict[str, Any] | None:
    with TASK_LOCK:
        task = CHAT_TASKS.get(task_id)
        if not task:
            return None
        snapshot = dict(task)
        snapshot["events"] = list(task.get("events", []))
        return snapshot


def add_task_event(task_id: str, text: str, kind: str = "bot") -> None:
    text = str(text or "").strip()
    if not text:
        return
    with TASK_LOCK:
        task = CHAT_TASKS.get(task_id)
        if not task:
            return
        event_id = int(task.get("next_event_id", 1))
        events = task.setdefault("events", [])
        events.append({"id": event_id, "text": text, "kind": kind})
        task["next_event_id"] = event_id + 1
        if len(events) > 120:
            del events[: len(events) - 120]


def new_mcp_login_task() -> str:
    task_id = uuid.uuid4().hex
    with MCP_LOGIN_LOCK:
        MCP_LOGIN_TASKS[task_id] = {
            "id": task_id,
            "status": "running",
            "ok": None,
            "step": "starting",
            "message": "正在初始化 MCP 登录流程...",
            "qr_id": "",
            "qr_ready": False,
            "qr_bytes": b"",
            "started_at": int(time.time()),
            "updated_at": int(time.time()),
        }
    return task_id


def update_mcp_login_task(task_id: str, **kwargs: Any) -> None:
    with MCP_LOGIN_LOCK:
        task = MCP_LOGIN_TASKS.get(task_id)
        if not task:
            return
        for k, v in kwargs.items():
            task[k] = v
        task["updated_at"] = int(time.time())


def get_mcp_login_task(task_id: str) -> Dict[str, Any] | None:
    with MCP_LOGIN_LOCK:
        task = MCP_LOGIN_TASKS.get(task_id)
        if not task:
            return None
        snapshot = dict(task)
        snapshot.pop("qr_bytes", None)
        return snapshot


def get_mcp_qr_bytes(task_id: str) -> bytes:
    with MCP_LOGIN_LOCK:
        task = MCP_LOGIN_TASKS.get(task_id) or {}
        return task.get("qr_bytes", b"")
