"""Boss 直聘登录路由。"""

from __future__ import annotations

import threading

from flask import Blueprint, Response, jsonify, request

from app.services.boss_login_service import run_mcp_login_task
from app.utils.task_tracker import (
    get_mcp_login_task,
    get_mcp_qr_bytes,
    new_mcp_login_task,
)
from src.config import Config
from src.scraper import BossZhipinScraper

bp = Blueprint("boss", __name__)


@bp.post("/api/boss/login-save")
def api_boss_login_save():
    payload = request.get_json(silent=True) or {}
    cookie = str(payload.get("cookie", "")).strip()
    bst = str(payload.get("bst", "")).strip()

    if not cookie:
        return jsonify({"ok": False, "message": "Cookie 不能为空"}), 400

    cfg = Config.load()
    cfg.cookie = cookie
    cfg.bst = bst
    cfg.save()

    return jsonify({"ok": True, "message": "Boss Cookie 已保存"})


@bp.post("/api/boss/login-mcp")
def api_boss_login_mcp():
    cfg = Config.load()
    scraper = BossZhipinScraper(cfg)
    success = scraper.load_cookie_from_mcp()

    if success:
        return jsonify({"ok": True, "message": "MCP 登录成功，Cookie 已更新"})
    return jsonify({"ok": False, "message": "MCP 登录失败，请查看终端日志"}), 500


@bp.post("/api/boss/mcp-login/start")
def api_boss_mcp_login_start():
    cfg = Config.load()
    if cfg.cookie:
        return jsonify(
            {
                "ok": True,
                "already_logged_in": True,
                "message": "您已登录，进入首页。",
            }
        )

    task_id = new_mcp_login_task()
    worker = threading.Thread(target=run_mcp_login_task, args=(task_id,), daemon=True)
    worker.start()

    return jsonify(
        {
            "ok": True,
            "already_logged_in": False,
            "task_id": task_id,
            "qr_url": f"/api/boss/mcp-login/qr/{task_id}",
            "message": "MCP 登录已启动",
        }
    )


@bp.get("/api/boss/mcp-login/task/<task_id>")
def api_boss_mcp_login_task(task_id: str):
    task = get_mcp_login_task(task_id)
    if not task:
        return jsonify({"ok": False, "message": "登录任务不存在"}), 404
    return jsonify({"ok": True, "task": task})


@bp.get("/api/boss/mcp-login/qr/<task_id>")
def api_boss_mcp_login_qr(task_id: str):
    task = get_mcp_login_task(task_id)
    if not task:
        return Response("登录任务不存在", status=404, mimetype="text/plain; charset=utf-8")

    qr_bytes = get_mcp_qr_bytes(task_id)
    if qr_bytes:
        return Response(qr_bytes, mimetype="image/png")

    html = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="1" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MCP 登录二维码</title>
  <style>
    body { margin: 0; background: #091a2b; color: #d7f2ff; font-family: sans-serif; display: grid; place-items: center; height: 100vh; }
    .box { text-align: center; padding: 16px 20px; border: 1px solid #24506f; border-radius: 12px; }
  </style>
</head>
<body>
  <div class="box">二维码生成中，请稍候...</div>
</body>
</html>
"""
    return Response(html, mimetype="text/html; charset=utf-8")
