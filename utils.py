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
    action_str = action_str.strip()
    
    # 提取工具名称: ToolName().run(
    tool_match = re.match(r'(\w+)\(\)\.run\(', action_str)
    if not tool_match:
        raise ValueError(f"无法解析 action 格式: {action_str}")
    
    tool_name = tool_match.group(1)
    
    # 找到 .run( 的位置
    run_pos = action_str.find('.run(')
    if run_pos == -1:
        raise ValueError(f"无法找到 .run( 位置: {action_str}")
    
    # 从 .run( 之后开始查找参数字典
    start_pos = run_pos + 5  # len('.run(') = 5
    
    # 跳过空格
    while start_pos < len(action_str) and action_str[start_pos].isspace():
        start_pos += 1
    
    # 检查是否以 { 开头
    if start_pos >= len(action_str) or action_str[start_pos] != '{':
        raise ValueError(f"参数字典必须以 {{ 开头: {action_str[start_pos:start_pos+50]}}}")
    
    # 使用括号匹配来找到参数字典的结束位置
    # 需要处理嵌套的括号、引号内的内容
    params_str = _extract_dict_string(action_str, start_pos)
    
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


def _extract_dict_string(text: str, start_pos: int) -> str:
    """
    从指定位置开始提取字典字符串，正确处理嵌套括号和引号
    
    Args:
        text: 完整文本
        start_pos: 开始位置（在 .run( 之后）
        
    Returns:
        参数字典字符串
    """
    pos = start_pos
    depth = 0  # 括号深度
    in_string = False  # 是否在字符串内
    string_char = None  # 字符串引号类型 (' 或 ")
    escape_next = False  # 下一个字符是否转义
    
    result_start = pos
    
    while pos < len(text):
        char = text[pos]
        
        if escape_next:
            escape_next = False
            pos += 1
            continue
        
        if char == '\\':
            escape_next = True
            pos += 1
            continue
        
        if not in_string:
            if char in ("'", '"'):
                in_string = True
                string_char = char
            elif char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    # 找到匹配的结束括号
                    return text[result_start:pos + 1]
            elif char == ')':
                # 如果没有找到字典，可能是空参数 ()
                if depth == 0:
                    return '{}'
        else:
            if char == string_char:
                in_string = False
                string_char = None
        
        pos += 1
    
    # 如果没有找到匹配的结束括号，返回从开始到结尾的内容
    return text[result_start:].rstrip(')')


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

