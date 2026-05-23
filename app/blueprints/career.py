"""职业规划路由 (分析、报告、流式、对话、简历)。"""

from __future__ import annotations

import json
import time
import traceback
from typing import Any, Dict, List

from flask import Blueprint, Response, jsonify, request, stream_with_context

from app.services.career_service import (
    career_recommend_jobs_for_dialogue,
    get_career_data_dir,
    get_career_output_dir,
)
from app.utils.llm_client import build_career_llm_client
from app.utils.login_required import require_login
from src.career_planning.ai.ai_planner import generate_ai_matching_and_paths
from src.career_planning.data.data_loader import load_jobs_dataframe
from src.career_planning.dialogue.dialogue_manager import (
    build_final_student_text,
    default_state,
    next_dialogue_turn,
)
from src.career_planning.matching.matcher import match_jobs
from src.career_planning.matching.profiles import (
    build_job_profiles,
    build_related_edges,
    build_transition_graph,
    build_vertical_graph,
)
from src.career_planning.reports.report_generator import (
    build_ability_radar_data,
    export_report as export_career_report,
    generate_report_markdown,
    stream_report_markdown,
)
from src.career_planning.resume.resume_parser import parse_resume_file

bp = Blueprint("career", __name__)


@bp.get("/api/career/health")
def api_career_health():
    _, err = require_login()
    if err:
        return err

    llm = build_career_llm_client()
    return jsonify(
        {
            "ok": True,
            "time": int(time.time()),
            "llm_enabled": llm.enabled,
            "data_dir": str(get_career_data_dir().name),
        }
    )


@bp.post("/api/career/analyze")
def api_career_analyze():
    _, err = require_login()
    if err:
        return err

    try:
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        student_text = str(payload.get("student_text", "")).strip()
        include_report = bool(payload.get("include_report", False))

        if not student_text:
            return jsonify({"ok": False, "error": "请先输入简历或自我描述文本。"}), 400

        try:
            jobs_df = load_jobs_dataframe(get_career_data_dir())
        except Exception as exc:
            return jsonify({"ok": False, "error": f"读取岗位数据失败: {exc}"}), 500

        llm = build_career_llm_client()
        from src.career_planning.matching.student_profile import build_student_profile

        job_profiles = build_job_profiles(jobs_df)
        relation_edges = build_related_edges(job_profiles)

        student_profile = build_student_profile(student_text, llm=llm)
        ai_bundle = generate_ai_matching_and_paths(
            student_profile=student_profile,
            job_profiles=job_profiles,
            llm_client=llm,
            top_k=8,
        )

        matches = ai_bundle.get("matches") or match_jobs(student_profile, job_profiles, top_k=8)
        vertical_graph = ai_bundle.get("vertical_graph") or build_vertical_graph(job_profiles)
        transition_graph = ai_bundle.get("transition_graph") or build_transition_graph()
        ability_radar = build_ability_radar_data(
            student_profile=student_profile,
            matches=matches,
            llm_client=llm,
        )

        report_md = ""
        if include_report:
            report_md = generate_report_markdown(
                student_profile=student_profile,
                matches=matches,
                vertical_graph=vertical_graph,
                transition_graph=transition_graph,
                llm_client=llm,
            )

        return jsonify(
            {
                "ok": True,
                "job_profiles": job_profiles,
                "vertical_graph": vertical_graph,
                "transition_graph": transition_graph,
                "relation_edges": relation_edges,
                "student_profile": student_profile,
                "matches": matches,
                "ability_radar": ability_radar,
                "report_markdown": report_md,
                "report_ready": bool(report_md),
                "metrics": {
                    "required_job_profiles": len(job_profiles) >= 10,
                    "required_transition_paths": len(transition_graph) >= 5
                    and all(len(x.get("transitions", [])) >= 2 for x in transition_graph),
                    "matching_dimensions": [
                        "foundation_requirements",
                        "professional_skills",
                        "professional_quality",
                        "development_potential",
                    ],
                },
            }
        )
    except Exception as e:
        print("[ERROR] analyze 崩溃:", str(e))
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.post("/api/career/report")
def api_career_report():
    _, err = require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    student_profile = payload.get("student_profile") or {}
    matches = payload.get("matches") or []
    vertical_graph = payload.get("vertical_graph") or []
    transition_graph = payload.get("transition_graph") or []

    if not student_profile or not matches:
        return jsonify({"ok": False, "error": "报告生成缺少必要的分析结果。"}), 400

    llm = build_career_llm_client()
    ability_radar = build_ability_radar_data(
        student_profile=student_profile,
        matches=matches,
        llm_client=llm,
    )
    report_md = generate_report_markdown(
        student_profile=student_profile,
        matches=matches,
        vertical_graph=vertical_graph,
        transition_graph=transition_graph,
        llm_client=llm,
    )
    return jsonify({"ok": True, "report_markdown": report_md, "ability_radar": ability_radar})


@bp.post("/api/career/report/stream")
def api_career_report_stream():
    _, err = require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    student_profile = payload.get("student_profile") or {}
    matches = payload.get("matches") or []
    vertical_graph = payload.get("vertical_graph") or []
    transition_graph = payload.get("transition_graph") or []
    auto_export = bool(payload.get("auto_export", False))
    report_name = str(payload.get("report_name", "")).strip()

    if not student_profile or not matches:
        def error_stream():
            yield f": {' ' * 2048}\n\n"
            err_event = {
                "type": "error",
                "message": "报告流式输出缺少必要的分析结果。请先完成分析并确保 student_profile 与 matches 非空。",
            }
            yield f"data: {json.dumps(err_event, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'mode': 'error', 'final': True}, ensure_ascii=False)}\n\n"

        return Response(
            stream_with_context(error_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    llm = build_career_llm_client()
    ability_radar = build_ability_radar_data(
        student_profile=student_profile,
        matches=matches,
        llm_client=llm,
    )

    def event_stream():
        assembled_parts: List[str] = []
        try:
            yield f": {' ' * 2048}\n\n"
            yield f"data: {json.dumps({'type': 'stage', 'message': '已建立流式通道，开始连续输出'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'ability_radar', 'data': ability_radar}, ensure_ascii=False)}\n\n"

            for event in stream_report_markdown(
                student_profile=student_profile,
                matches=matches,
                vertical_graph=vertical_graph,
                transition_graph=transition_graph,
                llm_client=llm,
            ):
                if str(event.get("type", "")) == "chunk":
                    assembled_parts.append(str(event.get("content", "")))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            if auto_export:
                markdown_text = "".join(assembled_parts).strip()
                if markdown_text:
                    stem = report_name or f"career_plan_{int(time.time() * 1000)}"
                    try:
                        files = export_career_report(markdown_text, get_career_output_dir(), stem)
                        default_file = files.get("pdf") or ""
                        if default_file:
                            saved_event = {
                                "type": "saved",
                                "files": files,
                                "default_file": default_file,
                            }
                            yield f"data: {json.dumps(saved_event, ensure_ascii=False)}\n\n"
                        else:
                            warn_event = {
                                "type": "warn",
                                "message": f"报告文本已生成，但 PDF 导出失败: {files.get('pdf_error', '未知错误')}",
                            }
                            yield f"data: {json.dumps(warn_event, ensure_ascii=False)}\n\n"
                    except Exception as exc:
                        warn_event = {
                            "type": "warn",
                            "message": f"已生成报告内容，但自动保存失败: {exc}",
                        }
                        yield f"data: {json.dumps(warn_event, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'mode': 'stream', 'final': True}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            err = {"type": "error", "message": f"流式生成失败: {exc}"}
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@bp.post("/api/career/export")
def api_career_export():
    _, err = require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    markdown_text = str(payload.get("report_markdown", "")).strip()
    report_name = str(payload.get("report_name", "career_report")).strip()

    if not markdown_text:
        return jsonify({"ok": False, "error": "没有可导出的报告内容。"}), 400

    files = export_career_report(markdown_text, get_career_output_dir(), report_name)
    default_file = files.get("pdf") or ""
    warning = files.get("pdf_error", "")
    if not default_file:
        return jsonify({"ok": False, "error": warning or "PDF 导出失败"}), 500
    return jsonify({"ok": True, "files": files, "default_file": default_file, "warning": warning})


@bp.post("/api/career/resume/parse")
def api_career_resume_parse():
    _, err = require_login()
    if err:
        return err

    file = request.files.get("file")
    if not file:
        return jsonify({"ok": False, "error": "请先选择要上传的简历文件。"}), 400

    filename = str(file.filename or "").strip()
    if not filename:
        return jsonify({"ok": False, "error": "无效的文件名。"}), 400

    raw = file.read()
    if not raw:
        return jsonify({"ok": False, "error": "上传文件为空。"}), 400
    if len(raw) > 8 * 1024 * 1024:
        return jsonify({"ok": False, "error": "文件过大，请上传 8MB 以内的简历文件。"}), 400

    try:
        text = parse_resume_file(filename, raw)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"简历解析失败: {exc}"}), 400

    if not text:
        return jsonify({"ok": False, "error": "未从文件中提取到文本，请检查文件内容。"}), 400

    return jsonify({"ok": True, "filename": filename, "text": text})


@bp.post("/api/career/dialogue/start")
def api_career_dialogue_start():
    _, err = require_login()
    if err:
        return err

    try:
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        major = str(payload.get("major", "") or "").strip()
        grade = str(payload.get("grade", "") or "").strip()

        state = default_state()
        if major:
            state["major"] = major
        if grade:
            state["grade"] = grade

        llm = build_career_llm_client()
        turn = next_dialogue_turn(
            state=state,
            user_message="",
            llm_client=llm,
            recommend_jobs=career_recommend_jobs_for_dialogue,
        )
        return jsonify({"ok": True, **turn})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"对话初始化失败: {exc}"}), 500


@bp.post("/api/career/dialogue/turn")
def api_career_dialogue_turn():
    _, err = require_login()
    if err:
        return err

    try:
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        raw_state = payload.get("state")
        state = raw_state if isinstance(raw_state, dict) else default_state()
        user_message = str(payload.get("user_message", "")).strip()
        major = str(payload.get("major", "") or "").strip()
        grade = str(payload.get("grade", "") or "").strip()

        if major:
            state["major"] = major
        if grade:
            state["grade"] = grade

        if not user_message:
            return jsonify({"ok": False, "error": "请输入本轮回答内容。"}), 400

        llm = build_career_llm_client()
        turn = next_dialogue_turn(
            state=state,
            user_message=user_message,
            llm_client=llm,
            recommend_jobs=career_recommend_jobs_for_dialogue,
        )
        return jsonify({"ok": True, **turn, "final_student_text": build_final_student_text(turn["state"])})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"对话处理失败: {exc}"}), 500
