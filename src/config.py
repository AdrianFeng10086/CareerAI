"""
配置管理模块
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """全局配置"""
    # Boss直聘 MCP 服务器地址
    mcp_server_url: str = "http://127.0.0.1:8000"

    # AI 分析配置 (支持 OpenAI 兼容 API)
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_temperature: float = 0.7
    ai_max_tokens: int = 4096

    # 备用 AI 配置（主 AI 连接异常时自动切换）
    backup_ai_api_key: str = ""
    backup_ai_base_url: str = "https://api.hunyuan.cloud.tencent.com/v1/chat/completions"
    backup_ai_model: str = "hunyuan-turbos-latest"
    backup_ai_enable_enhancement: bool = True

    # 爬取配置
    request_delay: float = 1.5          # 请求间隔(秒)，避免被封
    max_retry: int = 3                  # 最大重试次数
    max_pages_per_search: int = 5       # 每次搜索最大页数

    # 数据存储
    data_dir: str = "data"              # 数据存储目录
    output_dir: str = "output"          # 输出目录

    # Cookie (从 mcp-bosszp 登录后获取)
    cookie: str = ""
    bst: str = ""

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> "Config":
        """加载配置文件"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config.json"
            )

        config = cls()

        # 从文件加载
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

        # 环境变量覆盖
        env_mappings = {
            "AI_API_KEY": "ai_api_key",
            "OPENAI_API_KEY": "ai_api_key",
            "AI_BASE_URL": "ai_base_url",
            "OPENAI_BASE_URL": "ai_base_url",
            "AI_MODEL": "ai_model",
            "BACKUP_AI_API_KEY": "backup_ai_api_key",
            "BACKUP_AI_BASE_URL": "backup_ai_base_url",
            "BACKUP_AI_MODEL": "backup_ai_model",
            "HUNYUAN_API_KEY": "backup_ai_api_key",
            "HUNYUAN_BASE_URL": "backup_ai_base_url",
            "HUNYUAN_MODEL": "backup_ai_model",
            "BOSS_COOKIE": "cookie",
            "BOSS_BST": "bst",
        }

        for env_key, attr_name in env_mappings.items():
            env_value = os.environ.get(env_key)
            if env_value:
                setattr(config, attr_name, env_value)

        # 确保目录存在
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(os.path.join(base_dir, config.data_dir), exist_ok=True)
        os.makedirs(os.path.join(base_dir, config.output_dir), exist_ok=True)

        return config

    def save(self, config_path: Optional[str] = None):
        """保存配置到文件"""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config.json"
            )

        data = {
            "mcp_server_url": self.mcp_server_url,
            "ai_api_key": self.ai_api_key,
            "ai_base_url": self.ai_base_url,
            "ai_model": self.ai_model,
            "ai_temperature": self.ai_temperature,
            "ai_max_tokens": self.ai_max_tokens,
            "backup_ai_api_key": self.backup_ai_api_key,
            "backup_ai_base_url": self.backup_ai_base_url,
            "backup_ai_model": self.backup_ai_model,
            "backup_ai_enable_enhancement": self.backup_ai_enable_enhancement,
            "request_delay": self.request_delay,
            "max_retry": self.max_retry,
            "max_pages_per_search": self.max_pages_per_search,
            "data_dir": self.data_dir,
            "output_dir": self.output_dir,
            "cookie": self.cookie,
            "bst": self.bst,
        }

        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"配置已保存到: {config_path}")
