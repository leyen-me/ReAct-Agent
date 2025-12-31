# -*- coding: utf-8 -*-
"""路径处理工具模块"""

import os
from pathlib import Path
from typing import Tuple


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

