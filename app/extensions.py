"""全局共享的锁与任务字典。

替代原 web_app.py 中散落的模块级单例,集中管理便于在测试时替换。
"""

from __future__ import annotations

import threading
from typing import Any, Dict

# 求职流水线任务追踪
TASK_LOCK = threading.Lock()
CHAT_TASKS: Dict[str, Dict[str, Any]] = {}

# Boss 直聘 MCP 二维码登录任务追踪
MCP_LOGIN_LOCK = threading.Lock()
MCP_LOGIN_TASKS: Dict[str, Dict[str, Any]] = {}

# 模拟面试会话状态
INTERVIEW_LOCK = threading.Lock()
INTERVIEW_SESSIONS: Dict[str, Dict[str, Any]] = {}

# 摄像头分析器实例
CAMERA_LOCK = threading.Lock()
CAMERA_ANALYZERS: Dict[str, Any] = {}

# 用户库读写锁
AUTH_LOCK = threading.Lock()
