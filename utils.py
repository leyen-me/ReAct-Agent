# -*- coding: utf-8 -*-
"""工具函数模块"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple


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


def parse_action(action_str: str) -> Tuple[str, Dict[str, Any]]:
    """
    安全地解析 action 字符串
    
    期望格式: ToolName().run({'param1': 'value1', 'param2': 'value2'})
    
    Args:
        action_str: action 字符串
        
    Returns:
        (工具名称, 参数字典)
    """
    # 匹配模式: ToolName().run({...})
    pattern = r'(\w+)\(\)\.run\(({.*?})\)'
    match = re.match(pattern, action_str.strip(), re.DOTALL)
    
    if not match:
        raise ValueError(f"无法解析 action 格式: {action_str}")
    
    tool_name = match.group(1)
    params_str = match.group(2)
    
    # 安全地解析参数字典
    try:
        # 使用 ast.literal_eval 而不是 eval，更安全
        import ast
        params = ast.literal_eval(params_str)
        if not isinstance(params, dict):
            raise ValueError("参数必须是字典类型")
        return tool_name, params
    except Exception as e:
        raise ValueError(f"解析参数失败: {e}")


def format_search_results(results: List[Dict[str, Any]], max_results: int = 50) -> str:
    """
    格式化搜索结果
    
    Args:
        results: 搜索结果列表
        max_results: 最大返回结果数
        
    Returns:
        格式化后的字符串
    """
    if not results:
        return "未找到匹配的内容"
    
    result_lines = [f"找到 {len(results)} 处匹配:"]
    
    # 使用列表推导式提高效率
    result_lines.extend(
        f"{r['file']}:{r['line']}: {r['content']}"
        for r in results[:max_results]
    )
    
    if len(results) > max_results:
        result_lines.append(f"... 还有 {len(results) - max_results} 处匹配未显示")
    
    return "\n".join(result_lines)


def format_file_list(files: List[str], max_files: int = 100) -> str:
    """
    格式化文件列表
    
    Args:
        files: 文件路径列表
        max_files: 最大返回文件数
        
    Returns:
        格式化后的字符串
    """
    if not files:
        return "未找到匹配的文件"
    
    result_lines = [f"找到 {len(files)} 个匹配的文件:"]
    result_lines.extend(files[:max_files])
    
    if len(files) > max_files:
        result_lines.append(f"... 还有 {len(files) - max_files} 个文件未显示")
    
    return "\n".join(result_lines)

