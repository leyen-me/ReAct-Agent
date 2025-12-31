# -*- coding: utf-8 -*-
"""文件管理工具模块"""

import os
import fnmatch
from pathlib import Path
from typing import List, Optional, Dict, Tuple

# 默认忽略模式
DEFAULT_IGNORE_PATTERNS = ['__pycache__', '.git', 'node_modules', '.venv', 'venv', '.env']

# 模块级缓存：存储不同工作目录的文件列表
_file_cache: Dict[Path, Tuple[List[str], List[str]]] = {}  # {work_dir: (file_list, ignore_patterns)}


def _should_ignore(path: Path, ignore_patterns: List[str]) -> bool:
    """
    检查路径是否应该被忽略
    
    Args:
        path: 要检查的路径
        ignore_patterns: 忽略模式列表
        
    Returns:
        如果应该忽略返回 True，否则返回 False
    """
    path_str = str(path)
    name = path.name
    
    # 检查是否匹配忽略模式
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(name, pattern) or pattern in path_str:
            return True
    return False


def _scan_directory(
    directory: Path, 
    relative_prefix: str,
    file_list: List[str],
    ignore_patterns: List[str]
) -> None:
    """
    递归扫描目录
    
    Args:
        directory: 要扫描的目录
        relative_prefix: 相对路径前缀
        file_list: 文件列表（会被修改）
        ignore_patterns: 忽略模式列表
    """
    try:
        if not directory.exists() or not directory.is_dir():
            return
        
        # 按文件类型和名称排序
        items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        
        for item in items:
            if _should_ignore(item, ignore_patterns):
                continue
            
            relative_path = (
                os.path.join(relative_prefix, item.name) 
                if relative_prefix 
                else item.name
            )
            
            if item.is_file():
                file_list.append(relative_path)
            elif item.is_dir():
                _scan_directory(item, relative_path, file_list, ignore_patterns)
    except PermissionError:
        # 忽略权限错误，继续扫描其他目录
        pass


def scan_workspace_files(
    work_dir: Path, 
    ignore_patterns: Optional[List[str]] = None
) -> List[str]:
    """
    扫描工作目录，返回文件列表
    
    Args:
        work_dir: 工作目录路径
        ignore_patterns: 忽略的文件/目录模式列表，如果为 None 则使用默认模式
        
    Returns:
        文件路径列表（相对于工作目录），已排序
    """
    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS
    
    file_list: List[str] = []
    _scan_directory(work_dir, "", file_list, ignore_patterns)
    # 按名称排序（不区分大小写）
    file_list.sort(key=str.lower)
    
    return file_list


def refresh_file_list(
    work_dir: Path,
    ignore_patterns: Optional[List[str]] = None
) -> int:
    """
    刷新文件列表缓存
    
    Args:
        work_dir: 工作目录路径
        ignore_patterns: 忽略的文件/目录模式列表，如果为 None 则使用默认模式
        
    Returns:
        刷新后的文件数量
    """
    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS
    
    file_list = scan_workspace_files(work_dir, ignore_patterns)
    _file_cache[work_dir] = (file_list.copy(), ignore_patterns.copy())
    
    return len(file_list)


def get_file_list(work_dir: Path) -> List[str]:
    """
    获取文件列表（如果缓存存在则返回缓存，否则扫描并缓存）
    
    Args:
        work_dir: 工作目录路径
        
    Returns:
        文件路径列表（相对于工作目录）
    """
    # 检查缓存
    if work_dir in _file_cache:
        cached_list, _ = _file_cache[work_dir]
        return cached_list.copy()
    
    # 缓存不存在，扫描并缓存
    refresh_file_list(work_dir)
    cached_list, _ = _file_cache[work_dir]
    return cached_list.copy()


def get_file_count(work_dir: Path) -> int:
    """
    获取文件数量
    
    Args:
        work_dir: 工作目录路径
        
    Returns:
        文件数量
    """
    return len(get_file_list(work_dir))


def search_files(
    work_dir: Path,
    query: str,
    limit: int = 50
) -> List[str]:
    """
    搜索匹配的文件
    
    Args:
        work_dir: 工作目录路径
        query: 搜索查询字符串（不区分大小写）
        limit: 最大返回结果数
        
    Returns:
        匹配的文件路径列表
    """
    file_list = get_file_list(work_dir)
    
    if not query.strip():
        return file_list[:limit]
    
    query_lower = query.lower()
    matching_files = [
        f for f in file_list
        if query_lower in f.lower()
    ]
    
    return matching_files[:limit]
