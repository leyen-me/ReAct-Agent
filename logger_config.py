# -*- coding: utf-8 -*-
"""日志配置模块"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.path import get_project_root


def get_log_dir() -> Path:
    """获取日志目录路径"""
    project_root = get_project_root()
    log_dir = project_root / ".agent_logs"
    return log_dir


def get_current_log_file() -> Path:
    """获取当前日志文件路径"""
    log_dir = get_log_dir()
    # 使用日期作为日志文件名
    log_filename = f"agent_{datetime.now().strftime('%Y%m%d')}.log"
    return log_dir / log_filename


def get_all_log_files() -> list:
    """获取所有日志文件列表（按时间倒序）"""
    log_dir = get_log_dir()
    if not log_dir.exists():
        return []
    
    log_files = list(log_dir.glob("agent_*.log"))
    # 按修改时间倒序排序
    log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return log_files


def setup_logging(log_file: Optional[str] = None, enable_console: bool = False) -> str:
    """
    配置日志系统
    
    Args:
        log_file: 日志文件路径（可选，如果不指定则使用默认路径）
        enable_console: 是否启用控制台输出（默认 False，避免污染 TUI 界面）
    
    Returns:
        实际使用的日志文件路径
    
    Note:
        始终记录 DEBUG 级别的日志到文件
        控制台输出默认关闭，避免干扰 Textual TUI 界面
    """
    # 创建根 logger（始终设置为 DEBUG）
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 清除已有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器（仅在需要时启用）
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        
        # 格式化器（始终使用详细格式）
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 创建 logs 目录
    log_dir = get_log_dir()
    log_dir.mkdir(exist_ok=True)
    
    # 确定日志文件路径
    if log_file:
        actual_log_file = Path(log_file)
    else:
        actual_log_file = get_current_log_file()
    
    # 文件处理器（始终 DEBUG 级别）
    file_handler = logging.FileHandler(actual_log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    return str(actual_log_file)

