"""求职主流水线: 意图解析 -> 抓取 -> 分析 -> 报告。"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict

from flask import current_app

from app.services.auth_service import get_user_output_dir
from app.services.career_service import persist_career_jobs_dataset
from app.services.intent_service import (
    extract_user_profile,
    parse_intent,
    profile_summary_text,
)
from app.services.report_service import collect_report_files
from app.utils.task_tracker import add_task_event, get_task, update_task
from src.analyzer import JobAnalyzer
from src.career_job_store import schedule_upsert_jobs_to_vector_store
from src.config import Config
from src.job_search_store import (
    fetch_jobs_by_city_keyword_since,
    purge_jobs_before_ts,
    schedule_upsert_jobs_to_search_store,
)
from src.models import CITY_CODES, JobDetail, SearchQuery
from src.report import ReportGenerator
from src.scraper import BossZhipinScraper


def run_pipeline(
    message: str,
    user: Dict[str, Any] | None = None,
    progress_cb: Callable[[int, str, str], None] | None = None,
    event_cb: Callable[[str, str], None] | None = None,
) -> Dict[str, Any]:
    def step(pct: int, stage: str, msg: str) -> None:
        if progress_cb:
            progress_cb(pct, stage, msg)

    def emit(text: str, kind: str = "bot") -> None:
        if event_cb:
            event_cb(text, kind)

    base_dir: Path = current_app.config["BASE_DIR"]
    config = Config.load()
    user_output_dir = get_user_output_dir(user)
    config.output_dir = str(user_output_dir)
    if not config.cookie:
        return {
            "ok": False,
            "message": "还没有 Boss Cookie，请先在【Boss登录】板块保存 Cookie 后再开始对话。",
        }

    step(1, "intent.parse", "正在理解你的搜索意图（解析城市、岗位、页数）...")
    intent = parse_intent(config, message)
    if not intent.keyword and intent.action != "recommend":
        return {"ok": False, "message": "未能识别关键词，请尝试输入具体岗位如 'Python前端'"}

    if intent.intent_provider == "备用AI":
        emit("提示: 意图解析阶段主AI不可用，已自动切换到备用模型（混元）。")

    emit(
        f"执行参数: action={intent.action}, keyword={intent.keyword or '(空)'}, city={intent.city}, pages={intent.pages}"
    )

    if config.ai_api_key:
        step(4, "intent.done", "意图解析完成，已识别到具体搜索目标。")
        step(6, "profile.extract", "正在从对话中提取个人经历（经验、技能、优势）...")
    else:
        step(6, "profile.rule", "正在基于规则提取个人简历信息...")

    user_profile = extract_user_profile(message)
    if intent.personal_strengths_summary:
        user_profile["personal_strengths_summary"] = intent.personal_strengths_summary
        strengths = user_profile.setdefault("strengths", [])
        if intent.personal_strengths_summary not in strengths and len(strengths) < 10:
            strengths.insert(0, intent.personal_strengths_summary)

    step(10, "profile.done", "个人画像提取完成，正准备启动抓取引擎...")
    emit(f"画像预览: {profile_summary_text(user_profile)}")

    scraper = BossZhipinScraper(config)
    analyzer = JobAnalyzer(config)
    reporter = ReportGenerator(config)

    step(14, "scraper.init", "正在初始化 Boss直聘 数据抓取器...")
    report_snapshot = {x["name"] for x in collect_report_files(user)}

    def on_scrape_progress(done_pages: int, total_pages: int, job_count: int) -> None:
        total_pages = max(total_pages, 1)
        pct = 18 + int((done_pages / total_pages) * 36)
        step(
            pct,
            "scraping.page",
            f"正在抓取 Boss 数据: {done_pages}/{total_pages} 页, 已获取 {job_count} 条数据...",
        )
        emit("抓取中: 每页约需 1.5s 避开风控检测...")

    cache_hit = False
    scrape_meta: Dict[str, Any] = {}
    risk_detected = False

    step(16, "cache.check", "正在检查本地缓存库，比对数据时效性...")
    now_dt = datetime.now()
    cfg = Config.load()
    base_time_str = cfg.last_search_time
    one_month_seconds = 30 * 24 * 3600
    cache_start_dt = now_dt
    data_dir = base_dir / cfg.data_dir

    if base_time_str:
        try:
            cache_start_dt = datetime.fromisoformat(base_time_str)
        except Exception:
            cache_start_dt = now_dt
            cfg.last_search_time = cache_start_dt.isoformat()
            cfg.save()
            emit("缓存起始时间异常，已重建起始时间。")
    else:
        cache_start_dt = now_dt
        cfg.last_search_time = cache_start_dt.isoformat()
        cfg.save()
        emit("已创建求职缓存起始时间窗口。")

    if (now_dt - cache_start_dt).total_seconds() > one_month_seconds:
        cache_start_dt = now_dt
        cfg.last_search_time = cache_start_dt.isoformat()
        cfg.save()
        purged = purge_jobs_before_ts(data_dir=data_dir, threshold_ts=int(cache_start_dt.timestamp()))
        emit(f"缓存窗口已超过1个月，已重置起始时间并清理 {purged} 条过期求职缓存。")

    if intent.action == "recommend":
        step(18, "scraping.start", "开始抓取推荐系统职位...")
        jobs = scraper.get_recommend_jobs(max_pages=intent.pages, progress_callback=on_scrape_progress)
        query_name = "推荐职位"
        scrape_meta = scraper.get_last_run_meta()
        risk_detected = bool(scrape_meta.get("risk_blocked") or scrape_meta.get("entered_browser_mode"))
    elif intent.action == "search":
        query_name = intent.keyword
        step(17, "cache.match", f"正在检索 '{intent.city}' 下相关岗位记录...")

        cached = fetch_jobs_by_city_keyword_since(
            data_dir=data_dir,
            city_name=intent.city,
            keyword=intent.keyword,
            start_time_iso=cfg.last_search_time,
            limit=500,
        )
        if cached:
            allowed_fields = set(JobDetail.__dataclass_fields__.keys())
            jobs = [
                JobDetail(**{k: v for k, v in item.items() if k in allowed_fields})
                for item in cached
            ]
            cache_hit = True
            scrape_meta = {
                "cache_hit": True,
                "cache_size": len(jobs),
                "cache_start_time": cfg.last_search_time,
                "cache_backend": "sqlite",
            }
            step(56, "cache.hit", f"检索完成，成功匹配到 {len(jobs)} 个相关岗位记录。")
            emit(f"检索到 {len(jobs)} 个记录，直接进入分析阶段。")
        else:
            step(18, "scraping.start", "未找到近期缓存，正在启动远程抓取引擎...")
            query = SearchQuery(
                keyword=intent.keyword,
                city=CITY_CODES.get(intent.city, CITY_CODES["北京"]),
                city_name=intent.city,
                max_pages=intent.pages,
            )
            jobs = scraper.search_jobs(query, progress_callback=on_scrape_progress)
            scrape_meta = scraper.get_last_run_meta()
            risk_detected = bool(scrape_meta.get("risk_blocked") or scrape_meta.get("entered_browser_mode"))
    else:
        jobs = []
        scrape_meta = {"message": "Invalid intent action or missing keyword"}

    if not jobs:
        fail_message = "没有抓取到有效职位数据。请检查关键词、城市或登录状态后重试。"
        if risk_detected:
            fail_message = "没有抓取到有效职位数据，且检测到疑似被风控。系统将进入第二轮重试。"
        return {
            "ok": False,
            "message": fail_message,
            "risk_control_detected": risk_detected,
            "should_retry": risk_detected,
            "scrape_meta": scrape_meta,
        }

    if risk_detected:
        emit(
            "提示: 已检测到被风控，浏览器模式可能跳转空白页。系统将使用第一轮已抓取 Data 继续分析。"
        )

    try:
        Config.load()
    except Exception as rag_err:
        emit(f"RAG 上下文读取失败: {rag_err}", kind="error")

    data_path = ""
    career_data_path = ""
    if not cache_hit:
        step(58, "save-data", "抓取完成，正在保存原始数据...")
        data_path = scraper.save_jobs(jobs)
        emit(f"原始数据已保存: {os.path.basename(data_path)}")

        try:
            step(59, "save.career", "建立职业规划历史数据集...")
            career_data_path = persist_career_jobs_dataset(data_path)
            if career_data_path:
                emit(f"数据集已更新: {os.path.basename(career_data_path)}")
        except Exception as copy_err:
            emit(f"同步失败(不影响主流程): {copy_err}", kind="error")

    data_destroyed = False
    result_payload: Dict[str, Any] | None = None
    try:
        def on_analyze_progress(local_pct: int, stage: str, msg: str) -> None:
            mapped = 60 + int(max(0, min(100, local_pct)) * 0.22)
            step(mapped, f"ai.{stage}", f"AI 正在思考: {msg}")

        step(62, "analyzing.init", "正在初始化 LLM 分析插件（分配 API 配额与令牌）...")
        analysis = analyzer.analyze(
            jobs,
            query=query_name,
            user_profile=user_profile,
            progress_callback=on_analyze_progress,
        )
        if getattr(analyzer, "ai_provider_used", "") == "备用AI":
            emit("提示: 深度分析阶段主AI不可用，已自动切换到备用模型（混元）。")

        def on_report_progress(local_pct: int, stage: str, msg: str) -> None:
            mapped = 86 + int(max(0, min(100, local_pct)) * 0.12)
            step(mapped, f"pdf.{stage}", f"正在排版: {msg}")

        report_stem = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]}"

        step(84, "report.html", "正在将分析结论转化为交互式 HTML 报告...")
        reporter.generate_html(analysis, jobs, save=True, report_stem=report_stem)

        step(86, "report.pdf", "分析结果入库成功，正在排版并生成 PDF 离线报告...")
        reporter.generate_pdf(
            analysis,
            jobs,
            save=True,
            progress_callback=on_report_progress,
            report_stem=report_stem,
        )

        if not cache_hit:
            try:
                step(99, "storage.upsert", "正在更新本地向量数据库索引...")
                cfg = Config.load()
                data_dir = base_dir / cfg.data_dir
                schedule_upsert_jobs_to_search_store([job.to_dict() for job in jobs], data_dir)
                schedule_upsert_jobs_to_vector_store([job.to_dict() for job in jobs], data_dir)
                emit("服务结束: 已将抓取职位写入求职缓存 SQLite 与职业规划向量数据库。")
            except Exception as post_task_err:
                emit(f"后续持久化任务失败: {post_task_err}", kind="error")

        step(100, "finalizing", "报告生成完毕，正在整理结果...")

        report_after = collect_report_files(user)
        new_reports = [x for x in report_after if x["name"] not in report_snapshot]
        latest_report = (new_reports[0]["name"] if new_reports else report_after[0]["name"])

        summary = (
            f"任务完成: 已执行{intent.action}流程, 共抓取 {len(jobs)} 条职位, "
            f"并生成 HTML+PDF 报告（最新: `{latest_report}`）。"
        )
        emit(f"新报告已生成（HTML+PDF）: {latest_report}，可在报告中心查看。")

        result_payload = {
            "ok": True,
            "message": summary,
            "intent": {
                "action": intent.action,
                "keyword": intent.keyword,
                "city": intent.city,
                "pages": intent.pages,
                "personal_strengths_summary": intent.personal_strengths_summary,
                "intent_provider": intent.intent_provider,
            },
            "jobs_count": len(jobs),
            "risk_control_detected": risk_detected,
            "scrape_meta": scrape_meta,
            "user_profile": user_profile,
            "user_profile_summary": profile_summary_text(user_profile),
            "data_file": (os.path.basename(data_path) if data_path else "vector_cache"),
            "career_data_file": os.path.basename(career_data_path) if career_data_path else "",
            "data_destroyed": data_destroyed,
            "report_file": latest_report,
        }
    finally:
        try:
            if data_path and os.path.exists(data_path):
                os.remove(data_path)
                data_destroyed = True
                step(100, "cleanup.data", "任务结束，已销毁本次抓取的原始数据文件。")
                emit(f"原始数据已销毁: {os.path.basename(data_path)}")
        except Exception as cleanup_err:
            emit(f"原始数据销毁失败(不影响报告): {cleanup_err}", kind="error")

    if result_payload is not None:
        result_payload["data_destroyed"] = data_destroyed
        return result_payload

    return {
        "ok": False,
        "message": "任务未生成结果",
        "risk_control_detected": risk_detected,
        "scrape_meta": scrape_meta,
    }


def run_pipeline_task(app, task_id: str, message: str) -> None:
    """后台线程入口,需要把 Flask app 传进来以推入应用上下文。"""

    def progress_cb(pct: int, stage: str, text: str) -> None:
        update_task(task_id, progress=pct, stage=stage, message=text)

    def event_cb(text: str, kind: str = "bot") -> None:
        add_task_event(task_id, text, kind=kind)

    with app.app_context():
        owner: Dict[str, Any] | None = None
        task = get_task(task_id)
        owner_uid = int((task or {}).get("owner_user_id") or 0)
        if owner_uid:
            owner = {"id": owner_uid, "username": ""}

        try:
            result = run_pipeline(message, user=owner, progress_cb=progress_cb, event_cb=event_cb)

            should_retry = not result.get("ok") and bool(result.get("should_retry"))
            if should_retry:
                warning = "提示: 检测到首次抓取疑似触发风控，系统将自动按原始输入完整重跑一次流程，因此整体耗时会更长。"
                add_task_event(task_id, warning, kind="bot")
                update_task(
                    task_id,
                    progress=5,
                    stage="retry.wind-control",
                    message="检测到首次抓取疑似触发风控，系统将按你的原始输入完整重跑一次流程。由于风控原因，本次总耗时会更长，请耐心等待。",
                )
                retry_result = run_pipeline(message, user=owner, progress_cb=progress_cb, event_cb=event_cb)
                if retry_result.get("ok"):
                    retry_result["retried_due_to_wind_control"] = True
                    result = retry_result
                else:
                    retry_result["retried_due_to_wind_control"] = True
                    retry_result["message"] = (
                        f"{retry_result.get('message', '任务失败')}（已因风控自动重试一次完整流程）"
                    )
                    result = retry_result

            if result.get("ok"):
                update_task(
                    task_id,
                    progress=100,
                    stage="done",
                    message="任务完成",
                    status="done",
                    ok=True,
                    result=result,
                )
            else:
                update_task(
                    task_id,
                    stage="failed",
                    message=result.get("message", "任务失败"),
                    status="failed",
                    ok=False,
                    result=result,
                )
        except Exception as e:
            add_task_event(task_id, f"执行异常: {e}", kind="error")
            update_task(
                task_id,
                stage="failed",
                message=f"执行异常: {e}",
                status="failed",
                ok=False,
                result={"ok": False, "message": f"执行异常: {e}"},
            )
