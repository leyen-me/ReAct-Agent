# -*- coding: utf-8 -*-
"""工作空间文件管理模块"""

import os
import fnmatch
from pathlib import Path
from typing import List, Optional


class FileListManager:
    """文件列表管理器，负责管理文件列表的缓存和更新"""
    
    # 默认忽略模式
    DEFAULT_IGNORE_PATTERNS = ['__pycache__', '.git', 'node_modules', '.venv', 'venv', '.env']
    
    def __init__(self, work_dir: Path, ignore_patterns: Optional[List[str]] = None):
        """
        初始化文件列表管理器
        
        Args:
            work_dir: 工作目录路径
            ignore_patterns: 忽略的文件/目录模式列表，如果为 None 则使用默认模式
        """
        self.work_dir = work_dir
        self.ignore_patterns = ignore_patterns or self.DEFAULT_IGNORE_PATTERNS
        self._file_list: List[str] = []
        self._refresh()
    
    def _should_ignore(self, path: Path) -> bool:
        """
        检查路径是否应该被忽略
        
        Args:
            path: 要检查的路径
            
        Returns:
            如果应该忽略返回 True，否则返回 False
        """
        path_str = str(path)
        name = path.name
        
        # 检查是否匹配忽略模式
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or pattern in path_str:
                return True
        return False
    
    def _scan_directory(self, directory: Path, relative_prefix: str = "") -> None:
        """
        递归扫描目录
        
        Args:
            directory: 要扫描的目录
            relative_prefix: 相对路径前缀
        """
        try:
            if not directory.exists() or not directory.is_dir():
                return
            
            # 按文件类型和名称排序
            items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items:
                if self._should_ignore(item):
                    continue
                
                relative_path = (
                    os.path.join(relative_prefix, item.name) 
                    if relative_prefix 
                    else item.name
                )
                
                if item.is_file():
                    self._file_list.append(relative_path)
                elif item.is_dir():
                    self._scan_directory(item, relative_path)
        except PermissionError:
            # 忽略权限错误，继续扫描其他目录
            pass
    
    def _refresh(self) -> None:
        """刷新文件列表（内部方法）"""
        self._file_list = []
        self._scan_directory(self.work_dir)
        # 按名称排序（不区分大小写）
        self._file_list.sort(key=str.lower)
    
    def refresh(self) -> int:
        """
        刷新文件列表
        
        Returns:
            刷新后的文件数量
        """
        self._refresh()
        return len(self._file_list)
    
    def get_file_list(self) -> List[str]:
        """
        获取文件列表
        
        Returns:
            文件路径列表（相对于工作目录）
        """
        return self._file_list.copy()  # 返回副本，防止外部修改
    
    def get_file_count(self) -> int:
        """
        获取当前文件数量
        
        Returns:
            文件数量
        """
        return len(self._file_list)
    
    def search_files(self, query: str, limit: int = 50) -> List[str]:
        """
        搜索匹配的文件
        
        Args:
            query: 搜索查询字符串（不区分大小写）
            limit: 最大返回结果数
            
        Returns:
            匹配的文件路径列表
        """
        if not query.strip():
            return self._file_list[:limit]
        
        query_lower = query.lower()
        matching_files = [
            f for f in self._file_list
            if query_lower in f.lower()
        ]
        
        return matching_files[:limit]

