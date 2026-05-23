"""
camera.py — 面试神态分析模块 V5

定位：嵌入面试主程序，实时输出受试者的表情、眼神、头部姿态等指标，
     供上层（对话引擎、评分系统、UI）消费。

主要 API：
    InterviewAnalyzer(config).start() / stop()
    analyzer.get_latest_snapshot()  -> FrameSnapshot   (瞬时)
    analyzer.get_session_stats()    -> SessionStats    (累计)
    analyzer.subscribe(callback)                       (事件推送)

依赖：
    必需: opencv-python, numpy, mediapipe>=0.10
    表情识别: 固定返回 Neutral（不使用 FER+ ONNX）
"""

from __future__ import annotations

import logging
import math
import threading
import time
from copy import copy, deepcopy
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Tuple

import cv2
import numpy as np

# === 可选依赖 ===
try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    _HAS_MEDIAPIPE = True
except ImportError:
    _HAS_MEDIAPIPE = False

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════
#  第一部分：常量与配置
# ════════════════════════════════════════════════════════════════════════

class EmotionLabel(str, Enum):
    NEUTRAL  = "Neutral"
    HAPPY    = "Happy"
    SURPRISE = "Surprise"
    SAD      = "Sad"
    ANGRY    = "Angry"
    DISGUST  = "Disgust"
    FEAR     = "Fear"
    CONTEMPT = "Contempt"


# 面试场景下各表情的"积极性系数"，参与综合评分
EMOTION_POSITIVITY: Dict[str, float] = {
    EmotionLabel.HAPPY.value:    1.00,
    EmotionLabel.NEUTRAL.value:  0.80,
    EmotionLabel.SURPRISE.value: 0.55,
    EmotionLabel.CONTEMPT.value: 0.30,
    EmotionLabel.SAD.value:      0.25,
    EmotionLabel.FEAR.value:     0.20,
    EmotionLabel.ANGRY.value:    0.15,
    EmotionLabel.DISGUST.value:  0.10,
}


@dataclass
class AnalyzerConfig:
    """所有调参项集中放置，便于上层根据场景定制。"""
    # —— 摄像头 ——
    camera_id: int = 0
    capture_width: int = 1280
    capture_height: int = 720
    capture_fps: int = 30
    capture_buffer_size: int = 1            # 1 = 关闭缓冲，最低延迟
    capture_backend: int = cv2.CAP_ANY      # Win 上可用 cv2.CAP_DSHOW

    # —— 模型路径（None 时按 ./models 自动查找）——
    face_landmarker_path: Optional[str] = None
    emotion_model_path: Optional[str] = None

    # —— 推理 ——
    prefer_cuda: bool = True
    emotion_run_every_n: int = 2            # 每 N 帧跑一次表情（节流）

    # —— 平滑与阈值 ——
    smoothing_alpha: float = 0.3
    eye_contact_threshold: float = 0.45     # 大于此值视为视线在屏幕上
    looking_away_min_duration: float = 0.6  # 走神持续秒数才计为一次
    nod_velocity_threshold: float = 50.0    # deg/s
    shake_velocity_threshold: float = 50.0
    action_min_interval: float = 0.7        # 同类动作最小间隔（秒）

    # —— 主循环 ——
    target_fps: float = 30.0
    max_consecutive_read_failures: int = 100
    inference_log_every_n: int = 300

    # —— 调试预览 ——
    show_preview: bool = False
    preview_window_name: str = "Interview Camera (debug)"

    # —— 评分权重（合计 100）——
    score_weights: Dict[str, float] = field(default_factory=lambda: {
        "emotion":        25.0,
        "eye_contact":    35.0,
        "head_stability": 20.0,
        "positive_ratio": 20.0,
    })


# ════════════════════════════════════════════════════════════════════════
#  第二部分：数据模型 —— 严格分离瞬时与累计
# ════════════════════════════════════════════════════════════════════════

@dataclass
class FrameSnapshot:
    """单帧瞬时分析结果。每帧由分析线程产生，立即被覆盖。"""
    timestamp: float = 0.0
    frame_index: int = 0
    face_detected: bool = False

    # 头部姿态（度，已平滑）
    pitch: float = 0.0          # 抬头(+)/低头(-)
    yaw: float   = 0.0          # 左右摇头
    roll: float  = 0.0          # 头部侧倾
    pitch_velocity: float = 0.0 # 度/秒
    yaw_velocity:   float = 0.0

    # 表情
    emotion: str = EmotionLabel.NEUTRAL.value
    emotion_confidence: float = 0.0
    emotion_probs: Dict[str, float] = field(default_factory=dict)

    # 眼神
    eye_contact_score: float = 0.0
    gaze_offset: Tuple[float, float] = (0.0, 0.0)

    # 瞬时事件（仅在「该事件刚被触发」的那一帧为 True）
    nod_triggered: bool = False
    shake_triggered: bool = False
    looking_away: bool = False


@dataclass
class SessionStats:
    """会话累计统计。由 InterviewAnalyzer 持有并滚动更新。"""
    session_start: float = 0.0
    session_duration: float = 0.0

    total_frames: int = 0
    face_detected_frames: int = 0

    # 累计计数
    nod_count: int = 0
    shake_count: int = 0
    looking_away_count: int = 0

    # 累计时长（秒）
    eye_contact_duration: float = 0.0
    looking_away_duration: float = 0.0
    emotion_durations: Dict[str, float] = field(default_factory=dict)

    # 滚动派生指标
    eye_contact_ratio: float = 0.0
    head_stability: float = 1.0
    positive_emotion_ratio: float = 0.0
    dominant_emotion: str = EmotionLabel.NEUTRAL.value

    # 综合评分
    overall_score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        """便于 JSON 输出 / 日志记录。"""
        return {
            "session_duration": round(self.session_duration, 2),
            "total_frames": self.total_frames,
            "face_detection_rate": (
                self.face_detected_frames / self.total_frames
                if self.total_frames else 0.0
            ),
            "nod_count": self.nod_count,
            "shake_count": self.shake_count,
            "looking_away_count": self.looking_away_count,
            "eye_contact_ratio": round(self.eye_contact_ratio, 3),
            "head_stability": round(self.head_stability, 3),
            "positive_emotion_ratio": round(self.positive_emotion_ratio, 3),
            "dominant_emotion": self.dominant_emotion,
            "emotion_durations": {
                k: round(v, 2) for k, v in self.emotion_durations.items()
            },
            "overall_score": round(self.overall_score, 1),
            "score_breakdown": {
                k: round(v, 1) for k, v in self.score_breakdown.items()
            },
        }


# ════════════════════════════════════════════════════════════════════════
#  第三部分：引擎封装
# ════════════════════════════════════════════════════════════════════════

class FaceMeshEngine:
    """MediaPipe FaceLandmarker 同步检测封装。"""

    def __init__(self, model_path: Optional[str] = None):
        if not _HAS_MEDIAPIPE:
            raise RuntimeError("缺少 mediapipe，请 `pip install mediapipe`")

        path = self._resolve_model_path(model_path)
        opts = mp_vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=path),
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_facial_transformation_matrixes=True,
        )
        self._landmarker = mp_vision.FaceLandmarker.create_from_options(opts)
        logger.info(f"FaceMeshEngine 已加载: {path}")

    @staticmethod
    def _resolve_model_path(p: Optional[str]) -> str:
        if p and Path(p).is_file():
            return p
        candidates = [
            Path(__file__).parent.parent / "models" / "face_landmarker.task",
            Path(__file__).parent / "face_landmarker.task",
            Path.home() / ".cache" / "interview_camera" / "face_landmarker.task",
        ]
        for c in candidates:
            if Path(c).is_file():
                return str(c)
        raise FileNotFoundError(
            "找不到 face_landmarker.task。请下载\n"
            "  https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/latest/face_landmarker.task\n"
            "并放到该目录下，或在 AnalyzerConfig.face_landmarker_path 显式指定"
        )

    def detect(self, frame_bgr: np.ndarray, timestamp_ms: int):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        # detect_for_video 是同步阻塞 API（注意：不是 async）
        return self._landmarker.detect_for_video(mp_image, timestamp_ms)

    def close(self):
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception as e:
                logger.warning(f"FaceLandmarker 关闭异常: {e}")
            finally:
                self._landmarker = None


class EmotionEngine:
    """表情识别禁用：固定返回 Neutral。"""
    INPUT_SIZE = 64

    def __init__(self, model_path: Optional[str] = None, prefer_cuda: bool = True):
        self._available = False

    def predict(self, gray_face: np.ndarray) -> Tuple[str, float, Dict[str, float]]:
        return EmotionLabel.NEUTRAL.value, 0.0, {}

    def close(self):
        self._available = False


# ════════════════════════════════════════════════════════════════════════
#  第四部分：指标基础设施
# ════════════════════════════════════════════════════════════════════════

class EMASmoother:
    """指数移动平均。reset 后第一个样本作为初值（避免冷启动陡变）。"""
    __slots__ = ("alpha", "value")

    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.value: Optional[float] = None

    def update(self, x: float) -> float:
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value
        return self.value

    def reset(self):
        self.value = None


class ActionDetector:
    """
    一维信号的"过零穿越"动作检测：
    监测正负阈值之间的状态翻转，每翻转一次（且距上次触发够远）即触发一次事件。
    
    适用：pitch_velocity → 点头；yaw_velocity → 摇头。
    """
    def __init__(self, pos_threshold: float, neg_threshold: float, min_interval: float = 0.7):
        self.pos_threshold = pos_threshold
        self.neg_threshold = neg_threshold
        self.min_interval = min_interval
        self._last_extreme = 0          # -1 / 0 / 1
        self._last_trigger_time = 0.0

    def update(self, value: float, now: float) -> bool:
        if value > self.pos_threshold:
            curr = 1
        elif value < self.neg_threshold:
            curr = -1
        else:
            return False
        triggered = (
            self._last_extreme != 0
            and curr != self._last_extreme
            and (now - self._last_trigger_time) > self.min_interval
        )
        if triggered:
            self._last_trigger_time = now
        self._last_extreme = curr
        return triggered

    def reset(self):
        self._last_extreme = 0
        self._last_trigger_time = 0.0


@dataclass
class FrameContext:
    """每帧传给 MetricExtractor 的上下文。"""
    frame_bgr: np.ndarray
    frame_shape: Tuple[int, int, int]
    timestamp: float                     # monotonic 时间
    dt: float                            # 距上一帧秒数
    landmarks: Optional[List]
    transformation_matrix: Optional[np.ndarray]
    snapshot: FrameSnapshot              # 提取器把结果写入这里


class MetricExtractor(Protocol):
    """指标提取器协议。新增指标只要实现此协议并加入 _extractors 列表。"""
    name: str
    def update(self, ctx: FrameContext) -> None: ...
    def reset(self) -> None: ...


# ════════════════════════════════════════════════════════════════════════
#  第五部分：具体提取器
# ════════════════════════════════════════════════════════════════════════

class HeadPoseExtractor:
    """
    PnP 求解头部欧拉角。
    
    坐标系约定：
      模型点：右手系，X 向右、Y 向上、Z 向相机
      欧拉角：ZYX 分解
        pitch = 绕 X → 抬头(+) / 低头(-)
        yaw   = 绕 Y → 右转(+) / 左转(-)
        roll  = 绕 Z → 侧倾
    """
    name = "head_pose"

    # 标准头部模型 6 关键点（毫米）—— 保留 mm 单位以维持数值条件
    MODEL_POINTS = np.array([
        (0.0,    0.0,    0.0),    # 鼻尖   idx=1
        (0.0,   -63.6,  -12.5),   # 下巴   idx=152
        (-43.3,  32.7,  -26.0),   # 左眼外 idx=33
        (43.3,   32.7,  -26.0),   # 右眼外 idx=263
        (-28.9, -28.9,  -24.1),   # 左嘴角 idx=61
        (28.9,  -28.9,  -24.1),   # 右嘴角 idx=291
    ], dtype=np.float64)
    LANDMARK_IDX = (1, 152, 33, 263, 61, 291)

    def __init__(self, alpha: float = 0.3):
        self.s_pitch = EMASmoother(alpha)
        self.s_yaw   = EMASmoother(alpha)
        self.s_roll  = EMASmoother(alpha)
        self.s_pvel  = EMASmoother(alpha)
        self.s_yvel  = EMASmoother(alpha)
        self._prev_pitch: Optional[float] = None
        self._prev_yaw: Optional[float] = None

    def update(self, ctx: FrameContext) -> None:
        if ctx.landmarks is None:
            return
        h, w, _ = ctx.frame_shape
        focal = float(w)
        cam_mat = np.array([[focal, 0, w / 2.0],
                            [0, focal, h / 2.0],
                            [0, 0, 1]], dtype=np.float64)
        dist = np.zeros((4, 1), dtype=np.float64)

        image_points = np.array([
            (ctx.landmarks[i].x * w, ctx.landmarks[i].y * h)
            for i in self.LANDMARK_IDX
        ], dtype=np.float64)

        try:
            ok, rvec, _ = cv2.solvePnP(
                self.MODEL_POINTS, image_points, cam_mat, dist,
                flags=cv2.SOLVEPNP_ITERATIVE,
            )
        except cv2.error as e:
            logger.debug(f"solvePnP 异常: {e}")
            return
        if not ok:
            return

        R, _ = cv2.Rodrigues(rvec)
        # 关键修正：变量与几何含义对齐
        sy = float(np.clip(-R[2, 0], -1.0, 1.0))
        yaw   = math.degrees(math.asin(sy))
        pitch = math.degrees(math.atan2(R[2, 1], R[2, 2]))
        roll  = math.degrees(math.atan2(R[1, 0], R[0, 0]))

        pitch_s = self.s_pitch.update(pitch)
        yaw_s   = self.s_yaw.update(yaw)
        roll_s  = self.s_roll.update(roll)

        if self._prev_pitch is not None and ctx.dt > 0:
            pvel = (pitch_s - self._prev_pitch) / ctx.dt
            yvel = (yaw_s   - self._prev_yaw)   / ctx.dt
        else:
            pvel = yvel = 0.0
        pvel_s = self.s_pvel.update(pvel)
        yvel_s = self.s_yvel.update(yvel)

        self._prev_pitch, self._prev_yaw = pitch_s, yaw_s

        ctx.snapshot.pitch = pitch_s
        ctx.snapshot.yaw   = yaw_s
        ctx.snapshot.roll  = roll_s
        ctx.snapshot.pitch_velocity = pvel_s
        ctx.snapshot.yaw_velocity   = yvel_s

    def reset(self):
        for s in (self.s_pitch, self.s_yaw, self.s_roll, self.s_pvel, self.s_yvel):
            s.reset()
        self._prev_pitch = self._prev_yaw = None


class EyeContactExtractor:
    """
    虹膜中心相对眼眶中心的归一化偏移，用作"屏幕注视度"评分。

    场景假设：摄像头位于屏幕正上方，候选人作答时需要看屏幕上的题目和输入框，
    而不是盯摄像头。此时虹膜会自然向下偏移一定量（dy > 0 表示虹膜偏下）。
    因此本评分对"向下看"宽容，对"水平偏移"严格——后者更代表真正的走神。

    score=1 表示视线落在屏幕区域，0 表示明显偏离屏幕（看向左右或大幅低头）。

    关键点：
      左眼  33(外) 133(内) 159(上) 145(下) 468(虹膜)
      右眼 263(外) 362(内) 386(上) 374(下) 473(虹膜)
    """
    name = "eye_contact"
    LEFT  = (33, 133, 159, 145, 468)
    RIGHT = (263, 362, 386, 374, 473)

    # 向下注视屏幕的容忍区：dy 在 [0, DOWN_TOLERANCE] 内不扣分。
    DOWN_TOLERANCE = 0.35
    # 水平方向系数远高于垂直方向，水平偏移=真正的走神。
    HORIZONTAL_PENALTY = 6.0
    VERTICAL_PENALTY = 4.0

    def __init__(self, alpha: float = 0.3):
        self.smoother = EMASmoother(alpha)

    @staticmethod
    def _eye_offset(lm, outer, inner, top, bottom, iris):
        cx = (lm[outer].x + lm[inner].x) * 0.5
        cy = (lm[top].y + lm[bottom].y) * 0.5
        w = abs(lm[inner].x - lm[outer].x) + 1e-6
        h = abs(lm[bottom].y - lm[top].y) + 1e-6
        dx = (lm[iris].x - cx) / w
        dy = (lm[iris].y - cy) / h
        return dx, dy

    def update(self, ctx: FrameContext) -> None:
        if ctx.landmarks is None or len(ctx.landmarks) < 478:
            return
        try:
            dxL, dyL = self._eye_offset(ctx.landmarks, *self.LEFT)
            dxR, dyR = self._eye_offset(ctx.landmarks, *self.RIGHT)
        except (IndexError, AttributeError):
            return

        dx = (dxL + dxR) * 0.5
        dy = (dyL + dyR) * 0.5

        # 向下看屏幕的容忍：dy 落在 [0, DOWN_TOLERANCE] 视为对准屏幕，
        # 超过容忍区的部分按系数惩罚；向上看（dy<0）一律按绝对值惩罚。
        if dy >= 0:
            vertical_excess = max(0.0, dy - self.DOWN_TOLERANCE)
        else:
            vertical_excess = -dy

        horizontal_offset = abs(dx)
        # 综合偏离量：水平项更敏感
        deviation = math.hypot(
            horizontal_offset * self.HORIZONTAL_PENALTY,
            vertical_excess * self.VERTICAL_PENALTY,
        )
        raw_score = max(0.0, min(1.0, 1.0 - deviation))
        ctx.snapshot.eye_contact_score = self.smoother.update(raw_score)
        ctx.snapshot.gaze_offset = (dx, dy)

    def reset(self):
        self.smoother.reset()


class EmotionExtractor:
    """裁脸 → 64×64 灰度 → ONNX。可按 N 帧节流以省算力。"""
    name = "emotion"

    def __init__(self, engine: EmotionEngine, run_every_n: int = 2):
        self.engine = engine
        self.run_every_n = max(1, run_every_n)
        self._counter = 0
        self._cached: Tuple[str, float, Dict[str, float]] = (
            EmotionLabel.NEUTRAL.value, 0.0, {}
        )

    def _crop_face(self, frame_bgr: np.ndarray, landmarks) -> Optional[np.ndarray]:
        h, w, _ = frame_bgr.shape
        xs = np.array([p.x for p in landmarks])
        ys = np.array([p.y for p in landmarks])
        x_min, x_max = float(xs.min()), float(xs.max())
        y_min, y_max = float(ys.min()), float(ys.max())
        pad_x = (x_max - x_min) * 0.10
        pad_y = (y_max - y_min) * 0.15  # 多包一点额头
        x1 = max(0, int((x_min - pad_x) * w))
        y1 = max(0, int((y_min - pad_y) * h))
        x2 = min(w, int((x_max + pad_x) * w))
        y2 = min(h, int((y_max + pad_y) * h))
        if x2 - x1 < 8 or y2 - y1 < 8:
            return None
        face = frame_bgr[y1:y2, x1:x2]
        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        return cv2.resize(gray, (EmotionEngine.INPUT_SIZE, EmotionEngine.INPUT_SIZE))

    def update(self, ctx: FrameContext) -> None:
        if ctx.landmarks is None:
            return
        self._counter += 1
        if self._counter % self.run_every_n == 0:
            gray = self._crop_face(ctx.frame_bgr, ctx.landmarks)
            if gray is not None:
                self._cached = self.engine.predict(gray)
        label, conf, probs = self._cached
        ctx.snapshot.emotion = label
        ctx.snapshot.emotion_confidence = conf
        ctx.snapshot.emotion_probs = probs

    def reset(self):
        self._counter = 0
        self._cached = (EmotionLabel.NEUTRAL.value, 0.0, {})


class ActionExtractor:
    """点头 / 摇头瞬时事件检测。读取 HeadPoseExtractor 已经写入的速度。"""
    name = "action"

    def __init__(self, cfg: AnalyzerConfig):
        self.nod = ActionDetector(
            cfg.nod_velocity_threshold, -cfg.nod_velocity_threshold,
            cfg.action_min_interval,
        )
        self.shake = ActionDetector(
            cfg.shake_velocity_threshold, -cfg.shake_velocity_threshold,
            cfg.action_min_interval,
        )

    def update(self, ctx: FrameContext) -> None:
        ctx.snapshot.nod_triggered   = self.nod.update(ctx.snapshot.pitch_velocity, ctx.timestamp)
        ctx.snapshot.shake_triggered = self.shake.update(ctx.snapshot.yaw_velocity, ctx.timestamp)

    def reset(self):
        self.nod.reset()
        self.shake.reset()


# ════════════════════════════════════════════════════════════════════════
#  第六部分：主分析器
# ════════════════════════════════════════════════════════════════════════

SnapshotCallback = Callable[[FrameSnapshot, "SessionStats"], None]


class InterviewAnalyzer:
    """
    面试神态分析主控类。
    
    集成范式：
    
      A) Context manager + 拉取
        with InterviewAnalyzer(cfg) as a:
            a.start()
            while interview_in_progress:
                snap = a.get_latest_snapshot()
                stats = a.get_session_stats()
                ...
    
      B) 推送回调
        a = InterviewAnalyzer(cfg)
        a.subscribe(lambda snap, stats: ...)  # ⚠ 在分析线程中调用
        a.start(); ...; a.stop()
    
      C) 显式生命周期（嵌入到主程序的状态机）
        a = InterviewAnalyzer(cfg); a.start()
        ...
        a.stop()
    """

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or AnalyzerConfig()

        # 资源
        self._face: Optional[FaceMeshEngine] = None
        self._emo:  Optional[EmotionEngine] = None
        self._cap:  Optional[cv2.VideoCapture] = None
        self._extractors: List[MetricExtractor] = []

        # 线程
        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._lock = threading.RLock()

        # 数据
        self._snapshot = FrameSnapshot()
        self._stats = SessionStats()

        # 走神状态机
        self._away_active = False
        self._away_start_ts = 0.0
        self._away_counted = False

        # 头部稳定性 EMA（独立于单帧）
        self._stability_ema: Optional[float] = None

        # 回调
        self._callbacks: List[SnapshotCallback] = []

        # 运行时计数
        self._read_failures = 0
        self._last_loop_ts: Optional[float] = None
        self._initialized = False

    # ───────── 生命周期 ─────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self) -> threading.Thread:
        """启动后台分析线程。重复调用 idempotent。失败时回滚状态。"""
        if self._running.is_set():
            logger.info("InterviewAnalyzer 已在运行，忽略重复 start()")
            return self._thread

        try:
            self._initialize_engines()
            cap = cv2.VideoCapture(self.config.camera_id, self.config.capture_backend)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开摄像头 id={self.config.camera_id}")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.config.capture_width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.capture_height)
            cap.set(cv2.CAP_PROP_FPS,          self.config.capture_fps)
            cap.set(cv2.CAP_PROP_BUFFERSIZE,   self.config.capture_buffer_size)
            self._cap = cap

            self._reset_session()
            self._running.set()
            self._thread = threading.Thread(
                target=self._analysis_loop,
                name="InterviewAnalyzer",
                daemon=True,
            )
            self._thread.start()
            logger.info("InterviewAnalyzer 已启动")
            return self._thread
        except Exception:
            # 失败回滚
            self._running.clear()
            if self._cap is not None:
                self._cap.release()
                self._cap = None
            raise

    def stop(self, timeout: float = 3.0):
        """优雅停止。可重复调用。"""
        if not self._running.is_set() and self._thread is None:
            return
        self._running.clear()

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(f"分析线程未在 {timeout}s 内退出，已放弃等待")

        with self._lock:
            if self._cap is not None:
                try: self._cap.release()
                except Exception as e: logger.warning(f"摄像头释放失败: {e}")
                self._cap = None
            if self._face is not None:
                self._face.close(); self._face = None
            if self._emo is not None:
                self._emo.close(); self._emo = None

        if self.config.show_preview:
            try: cv2.destroyWindow(self.config.preview_window_name)
            except cv2.error: pass

        self._thread = None
        self._initialized = False
        logger.info("InterviewAnalyzer 已关闭")

    def _initialize_engines(self):
        if self._initialized:
            return
        self._face = FaceMeshEngine(self.config.face_landmarker_path)
        self._emo  = EmotionEngine(self.config.emotion_model_path,
                                    prefer_cuda=self.config.prefer_cuda)
        self._extractors = [
            HeadPoseExtractor(self.config.smoothing_alpha),
            EyeContactExtractor(self.config.smoothing_alpha),
            EmotionExtractor(self._emo, self.config.emotion_run_every_n),
            ActionExtractor(self.config),  # 必须在 HeadPose 之后
        ]
        self._initialized = True

    def _reset_session(self):
        with self._lock:
            self._snapshot = FrameSnapshot()
            self._stats = SessionStats(session_start=time.time())
            self._away_active = False
            self._away_start_ts = 0.0
            self._away_counted = False
            self._stability_ema = None
            self._read_failures = 0
            self._last_loop_ts = None
            for ex in self._extractors:
                ex.reset()

    # ───────── 公共 API ─────────

    def get_latest_snapshot(self) -> FrameSnapshot:
        """线程安全地获取最新瞬时快照（浅拷贝，避免外部修改影响内部）。"""
        with self._lock:
            return copy(self._snapshot)

    def get_session_stats(self) -> SessionStats:
        """线程安全地获取会话累计统计（深拷贝）。"""
        with self._lock:
            return deepcopy(self._stats)

    def subscribe(self, callback: SnapshotCallback):
        """⚠ 回调在分析线程中执行；耗时操作请自行投递到其它线程。"""
        with self._lock:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: SnapshotCallback):
        with self._lock:
            try: self._callbacks.remove(callback)
            except ValueError: pass

    def is_running(self) -> bool:
        return self._running.is_set()

    def wait_for_face(self, timeout: float = 30.0) -> bool:
        """阻塞直至检测到人脸或超时。用于"等候用户就位"。"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline and self._running.is_set():
            if self.get_latest_snapshot().face_detected:
                return True
            time.sleep(0.1)
        return False

    def reset_session(self):
        """显式开启新一轮统计（如：进入下一道面试题时清零累计）。"""
        self._reset_session()

    # ───────── 主循环 ─────────

    def _analysis_loop(self):
        loop_period = 1.0 / max(1.0, self.config.target_fps)
        frame_index = 0
        try:
            while self._running.is_set():
                loop_t0 = time.monotonic()

                ret, frame = self._cap.read()
                if not ret or frame is None:
                    self._read_failures += 1
                    if self._read_failures > self.config.max_consecutive_read_failures:
                        logger.error(f"摄像头连续 {self._read_failures} 次读取失败，停止")
                        self._running.clear()
                        break
                    time.sleep(0.05)
                    continue
                self._read_failures = 0

                # 真实时间戳
                now = time.monotonic()
                dt = (now - self._last_loop_ts) if self._last_loop_ts else 1.0 / self.config.target_fps
                self._last_loop_ts = now
                ts_ms = int(now * 1000)

                # 人脸检测
                try:
                    result = self._face.detect(frame, ts_ms)
                except Exception as e:
                    logger.warning(f"FaceLandmarker 检测异常: {e}")
                    continue

                landmarks = None
                tmat = None
                if result and result.face_landmarks:
                    landmarks = result.face_landmarks[0]
                    if (result.facial_transformation_matrixes
                            and len(result.facial_transformation_matrixes) > 0):
                        tmat = np.array(result.facial_transformation_matrixes[0])

                # 构造瞬时快照 & 跑指标管线
                snap = FrameSnapshot(
                    timestamp=time.time(),
                    frame_index=frame_index,
                    face_detected=landmarks is not None,
                )
                ctx = FrameContext(
                    frame_bgr=frame,
                    frame_shape=frame.shape,
                    timestamp=now,
                    dt=dt,
                    landmarks=landmarks,
                    transformation_matrix=tmat,
                    snapshot=snap,
                )
                for ex in self._extractors:
                    try:
                        ex.update(ctx)
                    except Exception as e:
                        logger.warning(f"提取器 {ex.name} 异常: {e}")

                # 更新累计 & 评分
                with self._lock:
                    self._update_session_stats(snap, dt)
                    self._compute_overall_score()
                    self._snapshot = snap
                    callbacks = list(self._callbacks)
                    stats_for_cb = deepcopy(self._stats)

                # 推送回调（不持锁）
                for cb in callbacks:
                    try: cb(snap, stats_for_cb)
                    except Exception as e: logger.warning(f"回调异常: {e}")

                # 调试预览
                if self.config.show_preview:
                    self._draw_preview(frame, snap)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        self._running.clear()

                frame_index += 1
                # 自适应节流
                elapsed = time.monotonic() - loop_t0
                if (st := loop_period - elapsed) > 0:
                    time.sleep(st)

        except Exception as e:
            logger.exception(f"分析线程致命错误: {e}")
        finally:
            self._running.clear()
            logger.info("分析线程退出")

    # ───────── 累计统计 ─────────

    def _update_session_stats(self, snap: FrameSnapshot, dt: float):
        s = self._stats
        s.total_frames += 1
        s.session_duration = time.time() - s.session_start

        if not snap.face_detected:
            return
        s.face_detected_frames += 1

        # 动作累计
        if snap.nod_triggered:   s.nod_count   += 1
        if snap.shake_triggered: s.shake_count += 1

        # 走神状态机：用"持续时长"过滤瞬时抖动
        if snap.eye_contact_score < self.config.eye_contact_threshold:
            snap.looking_away = True
            s.looking_away_duration += dt
            if not self._away_active:
                self._away_active = True
                self._away_start_ts = snap.timestamp
                self._away_counted = False
            elif (not self._away_counted
                  and snap.timestamp - self._away_start_ts
                       >= self.config.looking_away_min_duration):
                s.looking_away_count += 1
                self._away_counted = True
        else:
            snap.looking_away = False
            s.eye_contact_duration += dt
            self._away_active = False
            self._away_counted = False

        # 表情时长
        if snap.emotion:
            s.emotion_durations[snap.emotion] = (
                s.emotion_durations.get(snap.emotion, 0.0) + dt
            )

        # 派生比例
        valid_t = s.eye_contact_duration + s.looking_away_duration
        if valid_t > 0:
            s.eye_contact_ratio = s.eye_contact_duration / valid_t

        # 头部稳定性：基于角速度的 EMA
        speed = abs(snap.pitch_velocity) + abs(snap.yaw_velocity)
        instab = min(1.0, speed / 120.0)  # 120 deg/s 视为完全不稳
        instant_stab = 1.0 - instab
        if self._stability_ema is None:
            self._stability_ema = instant_stab
        else:
            self._stability_ema = 0.05 * instant_stab + 0.95 * self._stability_ema
        s.head_stability = max(0.0, min(1.0, self._stability_ema))

        # 加权积极表情比例（按时长加权，而不是只看主导）
        total_t = sum(s.emotion_durations.values()) or 1.0
        s.positive_emotion_ratio = sum(
            EMOTION_POSITIVITY.get(lbl, 0.5) * dur
            for lbl, dur in s.emotion_durations.items()
        ) / total_t

        # 主导情绪
        if s.emotion_durations:
            s.dominant_emotion = max(s.emotion_durations.items(), key=lambda x: x[1])[0]

    def _compute_overall_score(self):
        s = self._stats
        w = self.config.score_weights

        # 各分项归一化到 0~1
        emotion_factor   = max(0.0, min(1.0, s.positive_emotion_ratio))
        eye_factor       = max(0.0, min(1.0, s.eye_contact_ratio))
        head_factor      = max(0.0, min(1.0, s.head_stability))
        positive_factor  = max(0.0, min(1.0, s.positive_emotion_ratio))

        breakdown = {
            "emotion":        emotion_factor   * w["emotion"],
            "eye_contact":    eye_factor       * w["eye_contact"],
            "head_stability": head_factor      * w["head_stability"],
            "positive_ratio": positive_factor  * w["positive_ratio"],
        }
        s.score_breakdown = breakdown
        s.overall_score = sum(breakdown.values())

    # ───────── 调试预览 ─────────

    def _draw_preview(self, frame: np.ndarray, snap: FrameSnapshot):
        h, w, _ = frame.shape
        s = self._stats
        cv2.rectangle(frame, (0, 0), (w, 105), (0, 0, 0), -1)
        cv2.rectangle(frame, (0, 0), (w, 105), (255, 255, 255), 1)
        lines = [
            f"Emotion: {snap.emotion}({snap.emotion_confidence:.2f})  "
            f"P:{snap.pitch:+.1f}  Y:{snap.yaw:+.1f}  R:{snap.roll:+.1f}",
            f"EyeContact: {snap.eye_contact_score:.2f}   "
            f"Nods:{s.nod_count}  Shakes:{s.shake_count}  Aways:{s.looking_away_count}",
            f"Score: {s.overall_score:5.1f}/100   "
            f"Stab:{s.head_stability:.2f}  Pos:{s.positive_emotion_ratio:.2f}  "
            f"FaceRate:{(s.face_detected_frames/max(1,s.total_frames)):.2f}",
        ]
        for i, ln in enumerate(lines):
            cv2.putText(frame, ln, (10, 28 + i * 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)
        if snap.looking_away:
            cv2.putText(frame, "LOOKING AWAY",
                        (w // 2 - 110, h - 30), cv2.FONT_HERSHEY_SIMPLEX,
                        1.0, (0, 0, 255), 2, cv2.LINE_AA)
        cv2.imshow(self.config.preview_window_name, frame)


# ════════════════════════════════════════════════════════════════════════
#  使用示例（python camera.py 直接运行可看到调试预览）
# ════════════════════════════════════════════════════════════════════════

def _demo_standalone():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    cfg = AnalyzerConfig(show_preview=True)

    def on_frame(snap: FrameSnapshot, stats: SessionStats):
        if snap.nod_triggered:
            print(f"[event] 点头 #{stats.nod_count}")
        if snap.shake_triggered:
            print(f"[event] 摇头 #{stats.shake_count}")

    with InterviewAnalyzer(cfg) as analyzer:
        analyzer.subscribe(on_frame)
        analyzer.start()
        try:
            while analyzer.is_running():
                time.sleep(2.0)
                stats = analyzer.get_session_stats()
                print(f"[stats] score={stats.overall_score:.1f} "
                      f"eye={stats.eye_contact_ratio:.2f} "
                      f"emotion={stats.dominant_emotion}")
        except KeyboardInterrupt:
            print("\n用户中断")


if __name__ == "__main__":
    _demo_standalone()