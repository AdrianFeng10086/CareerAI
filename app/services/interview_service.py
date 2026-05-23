"""模拟面试摄像头分析服务。"""

from __future__ import annotations

from app.extensions import CAMERA_ANALYZERS, CAMERA_LOCK

try:
    from src.camera import AnalyzerConfig, InterviewAnalyzer
    HAS_CAMERA = True
except ImportError:
    AnalyzerConfig = None  # type: ignore[assignment]
    InterviewAnalyzer = None  # type: ignore[assignment]
    HAS_CAMERA = False


def stop_camera_for_session(session_id: str) -> None:
    with CAMERA_LOCK:
        analyzer = CAMERA_ANALYZERS.pop(session_id, None)
    if analyzer is not None:
        try:
            analyzer.stop(timeout=2.0)
        except Exception:
            pass


def start_camera_for_session(session_id: str) -> bool:
    if not HAS_CAMERA:
        return False
    try:
        cfg = AnalyzerConfig(show_preview=False)
        analyzer = InterviewAnalyzer(cfg)
        analyzer.start()
        with CAMERA_LOCK:
            CAMERA_ANALYZERS[session_id] = analyzer
        return True
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(f"摄像头分析启动失败（不影响面试）: {exc}")
        return False
