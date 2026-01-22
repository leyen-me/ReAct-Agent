# -*- coding: utf-8 -*-
"""配置管理模块"""

import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional, Dict, Any


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
    
    @staticmethod
    def get_config_dir() -> Path:
        """获取配置目录路径"""
        # 如果是 PyInstaller 打包后的可执行文件
        if getattr(sys, 'frozen', False):
            # 使用可执行文件所在目录（而不是临时目录）
            project_root = Path(sys.executable).parent
        else:
            # 开发环境：使用 config.py 所在目录
            project_root = Path(__file__).parent
        
        config_dir = project_root / ".agent_config"
        return config_dir
    
    @staticmethod
    def get_config_file() -> Path:
        """获取配置文件路径"""
        config_dir = Config.get_config_dir()
        return config_dir / "config.json"
    
    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """获取默认配置字典
        
        Returns:
            Dict[str, Any]: 包含所有默认配置的字典
        """
        return {
            "execution_model": "openai/gpt-oss-120b",  # 用于执行计划的小模型
            "api_key": None,
            "base_url": "https://integrate.api.nvidia.com/v1",
            "operating_system": Config.detect_operating_system(),  # 自动检测操作系统
            "work_dir": None,  # None 表示使用当前工作目录
            "command_timeout": "300",
            "max_search_results": "50",
            "max_find_files": "100",
            "max_context_tokens": "128000",
            "user_language_preference": "中文",
            "log_separator_length": "20",
        }
    
    def _load_config_file(self) -> Dict[str, Any]:
        """从配置文件加载配置，如果文件不存在则创建带默认值的配置文件
        
        Returns:
            Dict[str, Any]: 配置字典，如果文件不存在或读取失败则返回空字典
        """
        config_file = self.get_config_file()
        default_config = self.get_default_config()
        
        if not config_file.exists():
            # 创建带默认值的配置文件
            try:
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=2, ensure_ascii=False)
            except Exception as e:
                # 如果创建失败，记录错误但继续使用环境变量
                print(f"警告: 创建配置文件失败: {e}", file=sys.stderr)
            return {}
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                
                # 迁移旧的 model 配置到 execution_model
                if "model" in file_config and "execution_model" not in file_config:
                    old_model = file_config.get("model")
                    if old_model:
                        file_config["execution_model"] = old_model
                    # 删除旧的 model 配置
                    del file_config["model"]
                
                # 合并默认值，确保配置文件中有所有配置项
                # 如果配置文件中缺少某些项，使用默认值补充
                merged_config = default_config.copy()
                merged_config.update(file_config)
                
                # 如果 operating_system 是 null 或不存在，自动检测并更新
                if merged_config.get("operating_system") is None:
                    merged_config["operating_system"] = Config.detect_operating_system()
                
                # 如果配置文件缺少某些项或 operating_system 被更新，更新配置文件
                if file_config != merged_config or "model" in file_config:
                    # 确保删除旧的 model 配置
                    merged_config.pop("model", None)
                    try:
                        with open(config_file, 'w', encoding='utf-8') as f:
                            json.dump(merged_config, f, indent=2, ensure_ascii=False)
                    except Exception as e:
                        print(f"警告: 更新配置文件失败: {e}", file=sys.stderr)
                
                return merged_config
        except Exception as e:
            # 如果读取失败，记录错误但继续使用环境变量
            print(f"警告: 读取配置文件失败: {e}", file=sys.stderr)
            return {}
    
    def _get_config_value(self, config_dict: Dict[str, Any], key: str, env_key: Optional[str] = None, default: Any = None) -> Any:
        """获取配置值，优先从配置文件读取，如果不存在则从环境变量读取
        
        Args:
            config_dict: 配置文件字典
            key: 配置键名（在配置文件中的键名）
            env_key: 环境变量键名（如果为 None，则使用 key）
            default: 默认值
            
        Returns:
            配置值
        """
        # 优先从配置文件读取
        if key in config_dict and config_dict[key] is not None:
            return config_dict[key]
        
        # 如果配置文件不存在该键，则从环境变量读取
        env_key = env_key or key
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value
        
        # 如果都不存在，返回默认值
        return default
    
    def __init__(self):
        # 创建配置目录
        config_dir = self.get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载配置文件
        config_dict = self._load_config_file()
        
        # 模型配置
        # 执行模型：用于执行任务
        self.execution_model: str = self._get_config_value(
            config_dict, "execution_model", "EXECUTION_MODEL", "openai/gpt-oss-120b"
        )
        self.api_key: Optional[str] = self._get_config_value(
            config_dict, "api_key", "OPENAI_API_KEY", None
        )
        self.base_url: str = self._get_config_value(
            config_dict, "base_url", "OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1"
        )
        
        # 系统配置
        os_value = self._get_config_value(
            config_dict, "operating_system", "OS", None
        )
        self.operating_system: str = os_value if os_value else self.detect_operating_system()
        
        # 工作目录：优先使用配置文件，然后环境变量，最后使用当前工作目录
        work_dir_value = self._get_config_value(config_dict, "work_dir", "WORK_DIR", None)
        if work_dir_value:
            self.work_dir: Path = Path(work_dir_value)
        else:
            # 使用当前工作目录（程序运行的目录），而不是项目目录
            self.work_dir: Path = Path.cwd()
        self.work_dir = self.work_dir.resolve()  # 规范化路径
        
        # 命令执行配置
        command_timeout_value = self._get_config_value(
            config_dict, "command_timeout", "COMMAND_TIMEOUT", "300"
        )
        self.command_timeout: int = int(command_timeout_value)
        
        # 搜索配置
        max_search_results_value = self._get_config_value(
            config_dict, "max_search_results", "MAX_SEARCH_RESULTS", "50"
        )
        self.max_search_results: int = int(max_search_results_value)
        
        max_find_files_value = self._get_config_value(
            config_dict, "max_find_files", "MAX_FIND_FILES", "100"
        )
        self.max_find_files: int = int(max_find_files_value)
        
        # 上下文配置
        # 根据模型设置默认最大上下文 token 数
        default_max_tokens = 128000
        max_context_tokens_value = self._get_config_value(
            config_dict, "max_context_tokens", "MAX_CONTEXT_TOKENS", str(default_max_tokens)
        )
        self.max_context_tokens: int = int(max_context_tokens_value)
        
        # 确保工作目录存在
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # 用户语言偏好
        user_language_value = self._get_config_value(
            config_dict, "user_language_preference", "USER_LANGUAGE_PREFERENCE", "中文"
        )
        self.user_language_preference: str = user_language_value
        if self.user_language_preference not in ["中文", "English"]:
            raise ValueError("USER_LANGUAGE_PREFERENCE 配置必须为 中文 或 English")
        
        # 日志分隔符长度
        log_separator_length_value = self._get_config_value(
            config_dict, "log_separator_length", "LOG_SEPARATOR_LENGTH", "20"
        )
        self.log_separator_length: int = int(log_separator_length_value)
    
    def save_config_file(self, config_dict: Dict[str, Any]) -> bool:
        """保存配置到文件
        
        Args:
            config_dict: 要保存的配置字典
            
        Returns:
            bool: 是否保存成功
        """
        config_file = self.get_config_file()
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"警告: 保存配置文件失败: {e}", file=sys.stderr)
            return False
    
    def validate(self) -> None:
        """验证配置"""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 配置未设置（请通过配置文件或环境变量设置）")
        if not self.work_dir.exists():
            raise ValueError(f"工作目录不存在: {self.work_dir}")


# 全局配置实例
config = Config()

