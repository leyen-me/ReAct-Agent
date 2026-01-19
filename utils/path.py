# -*- coding: utf-8 -*-
"""路径处理工具模块"""

import os
import sys
from pathlib import Path
from typing import Tuple


def get_project_root() -> Path:
    """
    获取项目根目录路径
    
    在开发环境中，返回脚本文件所在目录。
    在 PyInstaller 打包后，返回可执行文件所在目录（而不是临时目录）。
    
    Returns:
        Path: 项目根目录路径
    """
    # 如果是 PyInstaller 打包后的可执行文件
    if getattr(sys, 'frozen', False):
        # 使用可执行文件所在目录（而不是临时目录）
        return Path(sys.executable).parent
    else:
        # 开发环境：使用当前模块所在目录的父目录（utils/ 的父目录）
        # 因为 path.py 在 utils/ 目录下，所以需要向上两级到项目根目录
        return Path(__file__).parent.parent


def validate_path(path: str, work_dir: Path) -> Tuple[bool, str]:
    """
    验证路径是否在工作目录内，防止路径遍历攻击
    
    Args:
        path: 要验证的路径
        work_dir: 工作目录
        
    Returns:
        (是否有效, 错误信息)
    """
    try:
        # 转换为绝对路径
        abs_path = Path(path).resolve()
        abs_work_dir = work_dir.resolve()
        
        # 检查是否在工作目录内
        if not str(abs_path).startswith(str(abs_work_dir)):
            return False, f"路径 {path} 不在工作目录内"
        
        return True, ""
    except Exception as e:
        return False, f"路径验证失败: {e}"


def normalize_path(path: str, work_dir: Path) -> Path:
    """
    规范化路径，确保在工作目录内
    
    Args:
        path: 原始路径
        work_dir: 工作目录
        
    Returns:
        规范化后的路径
    """
    if os.path.isabs(path):
        abs_path = Path(path).resolve()
    else:
        abs_path = (work_dir / path).resolve()
    
    # 验证路径
    is_valid, error = validate_path(str(abs_path), work_dir)
    if not is_valid:
        raise ValueError(error)
    
    return abs_path

