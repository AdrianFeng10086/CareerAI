"""报告列表/查看/下载路由。"""

from __future__ import annotations

import re

from flask import Blueprint, jsonify, send_file

from app.services.auth_service import get_user_output_dir
from app.services.report_service import collect_report_files, resolve_report_pdf_file
from app.utils.login_required import require_login
from app.utils.markdown import render_markdown_to_html

bp = Blueprint("reports", __name__)


@bp.get("/api/reports")
def api_reports():
    user, err = require_login()
    if err:
        return err
    return jsonify({"ok": True, "reports": collect_report_files(user)})


@bp.get("/api/reports/<path:report_name>")
def api_report_content(report_name: str):
    user, err = require_login()
    if err:
        return err

    output_dir = get_user_output_dir(user).resolve()
    target = (output_dir / report_name).resolve()

    if output_dir not in target.parents or not target.exists():
        return jsonify({"ok": False, "message": "报告不存在"}), 404

    suffix = target.suffix.lower()

    if suffix == ".pdf":
        return jsonify(
            {
                "ok": True,
                "name": report_name,
                "suffix": suffix,
                "is_binary": True,
                "view_url": f"/api/reports/{report_name}/raw",
            }
        )

    content = target.read_text(encoding="utf-8")

    if report_name.startswith("career_plan"):
        content = re.sub(r"```mermaid\s*radar-beta.*?```", "", content, flags=re.DOTALL | re.IGNORECASE)

    rendered_html = render_markdown_to_html(content) if suffix == ".md" else ""

    return jsonify(
        {
            "ok": True,
            "name": report_name,
            "suffix": suffix,
            "content": content,
            "rendered_html": rendered_html,
            "is_binary": False,
        }
    )


@bp.get("/api/reports/<path:report_name>/raw")
def api_report_raw(report_name: str):
    user, err = require_login()
    if err:
        return err

    output_dir = get_user_output_dir(user).resolve()
    target = (output_dir / report_name).resolve()

    if output_dir not in target.parents or not target.exists():
        return jsonify({"ok": False, "message": "报告不存在"}), 404

    return send_file(target)


@bp.get("/api/reports/<path:report_name>/pdf")
def api_report_pdf(report_name: str):
    user, err = require_login()
    if err:
        return err

    output_dir = get_user_output_dir(user).resolve()
    target = resolve_report_pdf_file(output_dir, report_name)
    if not target:
        return jsonify({"ok": False, "message": "报告对应的 PDF 不存在"}), 404

    return send_file(target)
