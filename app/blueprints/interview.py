"""模拟面试路由。"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from app.extensions import (
    CAMERA_ANALYZERS,
    CAMERA_LOCK,
    INTERVIEW_LOCK,
    INTERVIEW_SESSIONS,
)
from app.services.interview_service import (
    start_camera_for_session,
    stop_camera_for_session,
)
from app.utils.common import safe_int
from app.utils.llm_client import build_career_llm_client
from app.utils.login_required import require_login
from src.career_planning.resume.resume_parser import parse_resume_file
from src.interview_module import (
    build_interview_feedback,
    build_interview_questions,
    evaluate_answer_completeness,
)

bp = Blueprint("interview", __name__)


@bp.post("/api/interview/resume/parse")
def api_interview_resume_parse():
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


@bp.post("/api/interview/start")
def api_interview_start():
    _, err = require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    resume_text = str(payload.get("resume_text", "")).strip()
    question_count = max(8, min(15, safe_int(payload.get("question_count"), 10)))

    if not resume_text:
        return jsonify({"ok": False, "error": "请先上传并解析简历，或直接粘贴简历文本。"}), 400

    llm = build_career_llm_client()
    target_role, questions = build_interview_questions(
        resume_text=resume_text,
        llm_client=llm,
        target_count=question_count,
    )
    if not questions:
        return jsonify({"ok": False, "error": "未能生成面试问题，请稍后重试。"}), 500

    session_id = uuid.uuid4().hex
    session_state = {
        "session_id": session_id,
        "created_at": int(time.time()),
        "target_role": target_role,
        "resume_text": resume_text[:12000],
        "questions": questions,
        "current_index": 0,
        "attempts": {},
        "records": [],
        "status": "running",
    }
    with INTERVIEW_LOCK:
        INTERVIEW_SESSIONS[session_id] = session_state

    camera_started = start_camera_for_session(session_id)

    current_question = questions[0]
    return jsonify(
        {
            "ok": True,
            "session_id": session_id,
            "target_role": target_role,
            "total_questions": len(questions),
            "deep_questions": sum(1 for q in questions if q.get("is_deep")),
            "camera_active": camera_started,
            "current": {
                "index": 1,
                "question_id": current_question.get("id", 1),
                "question": current_question.get("question", ""),
                "sub_questions": current_question.get("sub_questions", []),
                "is_deep": bool(current_question.get("is_deep")),
                "category": current_question.get("category", ""),
            },
        }
    )


@bp.post("/api/interview/answer")
def api_interview_answer():
    _, err = require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    session_id = str(payload.get("session_id", "")).strip()
    answer = str(payload.get("answer", "")).strip()
    timed_out = bool(payload.get("timed_out"))

    if not session_id:
        return jsonify({"ok": False, "error": "缺少 session_id。"}), 400
    if not answer and not timed_out:
        return jsonify({"ok": False, "error": "请输入你的回答后再提交。"}), 400

    with INTERVIEW_LOCK:
        session_state = INTERVIEW_SESSIONS.get(session_id)
    if not session_state or session_state.get("status") != "running":
        return jsonify({"ok": False, "error": "面试会话已结束或不存在。"}), 404

    questions = session_state.get("questions") or []
    current_index = int(session_state.get("current_index", 0))
    if current_index >= len(questions):
        return jsonify({"ok": False, "error": "已完成所有问题。"}), 400

    current_question = questions[current_index]
    sub_questions = current_question.get("sub_questions", []) or []

    llm = build_career_llm_client()
    if timed_out:
        evaluation = {
            "status": "incomplete",
            "covered_sub_questions": [],
            "missing_sub_questions": list(range(len(sub_questions))),
            "comment": "倒计时结束，未在限定时间内提交完整回答。",
            "quality_score": 0,
        }
    else:
        evaluation = evaluate_answer_completeness(llm_client=llm, question=current_question, answer=answer)

    status = str(evaluation.get("status", "incomplete"))
    missing_indices = evaluation.get("missing_sub_questions") if isinstance(evaluation.get("missing_sub_questions"), list) else []
    missing_indices = [int(x) for x in missing_indices if isinstance(x, (int, float))]
    missing_sub_questions = [sub_questions[i] for i in missing_indices if 0 <= i < len(sub_questions)]

    attempts = session_state.get("attempts") if isinstance(session_state.get("attempts"), dict) else {}
    qid = str(current_question.get("id", current_index + 1))
    attempts[qid] = int(attempts.get(qid, 0)) + 1
    session_state["attempts"] = attempts

    record = {
        "question_id": current_question.get("id", current_index + 1),
        "question": current_question.get("question", ""),
        "sub_questions": sub_questions,
        "is_deep": bool(current_question.get("is_deep")),
        "answer": answer,
        "status": "complete" if status == "complete" else "incomplete",
        "missing_sub_questions": missing_sub_questions,
        "quality_score": int(evaluation.get("quality_score", 0) or 0),
        "comment": str(evaluation.get("comment", "")).strip(),
        "attempt": attempts[qid],
        "timed_out": timed_out,
    }

    if not timed_out and status != "complete" and attempts[qid] < 3:
        session_state["records"].append(record)
        with INTERVIEW_LOCK:
            INTERVIEW_SESSIONS[session_id] = session_state
        return jsonify(
            {
                "ok": True,
                "status": "needs_completion",
                "message": "当前回答未覆盖全部小问题，请先补充后再进入下一题。",
                "evaluation": {**record},
                "current": {
                    "index": current_index + 1,
                    "question_id": current_question.get("id", current_index + 1),
                    "question": current_question.get("question", ""),
                    "sub_questions": sub_questions,
                    "is_deep": bool(current_question.get("is_deep")),
                    "category": current_question.get("category", ""),
                },
            }
        )

    session_state["records"].append(record)
    session_state["current_index"] = current_index + 1

    if session_state["current_index"] < len(questions):
        next_q = questions[session_state["current_index"]]
        with INTERVIEW_LOCK:
            INTERVIEW_SESSIONS[session_id] = session_state
        return jsonify(
            {
                "ok": True,
                "status": "next_question",
                "message": "继续下一题。",
                "evaluation": record,
                "current": {
                    "index": session_state["current_index"] + 1,
                    "question_id": next_q.get("id", session_state["current_index"] + 1),
                    "question": next_q.get("question", ""),
                    "sub_questions": next_q.get("sub_questions", []),
                    "is_deep": bool(next_q.get("is_deep")),
                    "category": next_q.get("category", ""),
                },
                "progress": {
                    "answered": session_state["current_index"],
                    "total": len(questions),
                },
            }
        )

    session_state["status"] = "done"
    feedback = build_interview_feedback(
        llm_client=llm,
        target_role=str(session_state.get("target_role", "目标岗位")),
        questions=questions,
        records=session_state.get("records") or [],
    )
    session_state["feedback"] = feedback
    with INTERVIEW_LOCK:
        INTERVIEW_SESSIONS[session_id] = session_state

    stop_camera_for_session(session_id)

    return jsonify(
        {
            "ok": True,
            "status": "finished",
            "message": "模拟面试已完成，已生成反馈。",
            "evaluation": record,
            "feedback": feedback,
            "progress": {
                "answered": len(questions),
                "total": len(questions),
            },
        }
    )


@bp.get("/api/interview/camera/stats/<session_id>")
def api_interview_camera_stats(session_id: str):
    _, err = require_login()
    if err:
        return err

    with CAMERA_LOCK:
        analyzer = CAMERA_ANALYZERS.get(session_id)
    if analyzer is None:
        return jsonify({"ok": True, "camera_active": False})

    try:
        snap = analyzer.get_latest_snapshot()
        stats = analyzer.get_session_stats()
        return jsonify(
            {
                "ok": True,
                "camera_active": analyzer.is_running(),
                "snapshot": {
                    "face_detected": snap.face_detected,
                    "emotion": snap.emotion,
                    "emotion_confidence": round(snap.emotion_confidence, 3),
                    "eye_contact_score": round(snap.eye_contact_score, 3),
                    "pitch": round(snap.pitch, 1),
                    "yaw": round(snap.yaw, 1),
                    "roll": round(snap.roll, 1),
                    "looking_away": snap.looking_away,
                    "nod_triggered": snap.nod_triggered,
                    "shake_triggered": snap.shake_triggered,
                },
                "stats": stats.as_dict(),
            }
        )
    except Exception:
        return jsonify({"ok": True, "camera_active": False})


@bp.post("/api/interview/stop")
def api_interview_stop():
    _, err = require_login()
    if err:
        return err

    payload: Dict[str, Any] = request.get_json(silent=True) or {}
    session_id = str(payload.get("session_id", "")).strip()
    if not session_id:
        return jsonify({"ok": False, "error": "缺少 session_id。"}), 400

    with INTERVIEW_LOCK:
        session_state = INTERVIEW_SESSIONS.get(session_id)
    if session_state and session_state.get("status") == "running":
        session_state["status"] = "aborted"
        with INTERVIEW_LOCK:
            INTERVIEW_SESSIONS[session_id] = session_state

    stop_camera_for_session(session_id)
    return jsonify({"ok": True, "message": "面试会话已结束。"})
