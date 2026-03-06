"""
Cookie 持久化工具 — 轻量模块，不依赖 FastMCP 等重型库。
供 scraper.py 和 boss_zhipin_fastmcp_v2.py 共同使用。
"""

import json
import os


def _get_config_path() -> str:
    """获取 config.json 的路径（项目根目录）"""
    # cookie_utils.py -> src/boss_zp/ -> src/ -> 项目根目录
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config.json"
    )


def save_cookie_to_config(cookie: str, bst: str = "") -> bool:
    """将 Cookie 保存到项目根目录的 config.json 中

    Args:
        cookie: Cookie 字符串
        bst: BST Token

    Returns:
        是否保存成功
    """
    try:
        config_path = _get_config_path()

        # 读取现有配置
        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

        # 更新 cookie 和 bst
        config_data["cookie"] = cookie
        config_data["bst"] = bst

        # 写回文件
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=2)

        print(f"[Cookie同步] ✅ Cookie 已保存到 {config_path}")
        return True

    except Exception as e:
        print(f"[Cookie同步] ❌ 保存 Cookie 到 config.json 失败: {e}")
        return False
