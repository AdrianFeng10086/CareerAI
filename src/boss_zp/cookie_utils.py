"""Cookie 持久化工具 — 轻量模块,不依赖 FastMCP 等重型库。

目前把 Cookie / BST 写入项目根目录下的 `.env` 文件(键名 BOSS_COOKIE / BOSS_BST),
保留 .env 中其他键值与注释。
供 scraper.py 和 boss_zhipin_fastmcp_v2.py 共同使用。
"""

from __future__ import annotations

import os

from src.env_file import get_env_path, update_env


def _get_config_path() -> str:
    """兼容旧调用方:返回当前用于持久化 Cookie 的文件路径(.env)。"""
    return str(get_env_path())


def save_cookie_to_config(cookie: str, bst: str = "") -> bool:
    """把 Cookie / BST 持久化到项目根目录下的 .env。

    Args:
        cookie: Cookie 字符串
        bst:    BST Token

    Returns:
        是否保存成功
    """
    try:
        update_env({"BOSS_COOKIE": cookie or "", "BOSS_BST": bst or ""})
        os.environ["BOSS_COOKIE"] = cookie or ""
        os.environ["BOSS_BST"] = bst or ""
        print(f"[Cookie同步] ✅ Cookie 已保存到 {get_env_path()}")
        return True
    except Exception as e:
        print(f"[Cookie同步] ❌ 保存 Cookie 到 .env 失败: {e}")
        return False
