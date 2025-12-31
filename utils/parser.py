# -*- coding: utf-8 -*-
"""解析工具模块"""

import re
import json
from typing import Dict, Any, Tuple


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
    # 先尝试 JSON 格式（LLM 经常生成 JSON 格式的 true/false/null）
    # 如果失败，再尝试 Python 格式（True/False/None）
    try:
        # 尝试 JSON 解析
        params = json.loads(params_str)
        if not isinstance(params, dict):
            raise ValueError("参数必须是字典类型")
        return tool_name, params
    except (json.JSONDecodeError, ValueError):
        # JSON 解析失败，尝试 Python 格式
        try:
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

