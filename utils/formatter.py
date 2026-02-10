# -*- coding: utf-8 -*-
"""格式化工具模块"""

from typing import List, Dict, Any


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

