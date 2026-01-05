# -*- coding: utf-8 -*-
"""配置管理模块"""

import os
import platform
import sys
from pathlib import Path
from typing import Optional


class Config:
    """应用配置类"""
    
    @staticmethod
    def detect_operating_system() -> str:
        """自动检测操作系统
        
        Returns:
            str: 操作系统名称 (Windows, macOS, Linux)
        """
        system = platform.system()
        
        if system == "Darwin":
            return "macOS"
        elif system == "Windows":
            return "Windows"
        elif system == "Linux":
            return "Linux"
        else:
            # 对于其他未知系统，返回平台名称
            return system
    
    def __init__(self):
        
        # openai/gpt-oss-120b
        # minimaxai/minimax-m2
        # qwen/qwen3-next-80b-a3b-instruct
        # qwen/qwen3-coder-480b-a35b-instruct
        # deepseek-ai/deepseek-v3.1-terminus
        
        # 模型配置
        self.model: str = os.getenv("MODEL", "openai/gpt-oss-120b")
        self.api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
        self.base_url: str = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
        
        # 系统配置
        self.operating_system: str = os.getenv("OS", self.detect_operating_system())
        
        # 工作目录：优先使用环境变量，否则使用当前工作目录
        work_dir_env = os.getenv("WORK_DIR")
        if work_dir_env:
            self.work_dir: Path = Path(work_dir_env)
        else:
            # 使用当前工作目录（程序运行的目录），而不是项目目录
            self.work_dir: Path = Path.cwd()
        self.work_dir = self.work_dir.resolve()  # 规范化路径
        
        # 调试配置
        self.debug_mode: bool = os.getenv("DEBUG", "False").lower() == "true"
        
        # 命令执行配置
        self.command_timeout: int = int(os.getenv("COMMAND_TIMEOUT", "300"))
        
        # 搜索配置
        self.max_search_results: int = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
        self.max_find_files: int = int(os.getenv("MAX_FIND_FILES", "100"))
        
        # 上下文配置
        # 根据模型设置默认最大上下文 token 数
        default_max_tokens = 180000
        self.max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", str(default_max_tokens)))
        
        # 确保工作目录存在
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # 用户语言偏好
        self.user_language_preference: str = os.getenv("USER_LANGUAGE_PREFERENCE", "中文")
        if self.user_language_preference not in ["中文", "English"]:
            raise ValueError("USER_LANGUAGE_PREFERENCE 环境变量必须为 中文 或 English")
        
        # 日志分隔符长度
        self.log_separator_length: int = int(os.getenv("LOG_SEPARATOR_LENGTH", "20"))
    
    def validate(self) -> None:
        """验证配置"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 环境变量未设置")
        if not self.work_dir.exists():
            raise ValueError(f"工作目录不存在: {self.work_dir}")


# 全局配置实例
config = Config()

