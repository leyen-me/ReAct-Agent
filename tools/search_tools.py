# -*- coding: utf-8 -*-
"""搜索工具"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Dict, Any, List

from tools.base import Tool
from utils import format_search_results, format_file_list


class SearchInFilesTool(Tool):
    """在文件中搜索文本内容"""
    
    def __init__(self, work_dir: Path, max_results: int = 50):
        """
        初始化搜索工具
        
        Args:
            work_dir: 工作目录
            max_results: 最大返回结果数
        """
        super().__init__(work_dir)
        self.max_results = max_results
    
    def _get_description(self) -> str:
        return "在文件中搜索文本内容（支持正则表达式）。可以在指定目录下的所有文件中搜索，或仅在特定文件中搜索。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_text": {"type": "string", "description": "要搜索的文本（支持正则表达式）"},
                "directory": {"type": "string", "description": f"要搜索的目录路径（默认工作目录）", "default": str(self.work_dir)},
                "file_pattern": {"type": "string", "description": "文件匹配模式（如 '*.py', '*.js'），默认搜索所有文件"},
                "case_sensitive": {"type": "boolean", "description": "是否区分大小写（默认 false）", "default": False},
                "use_regex": {"type": "boolean", "description": "是否使用正则表达式（默认 false）", "default": False},
            },
            "required": ["search_text"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        search_text = parameters["search_text"]
        directory = parameters.get("directory", str(self.work_dir))
        file_pattern = parameters.get("file_pattern", "*")
        case_sensitive = parameters.get("case_sensitive", False)
        use_regex = parameters.get("use_regex", False)
        
        if not os.path.exists(directory):
            return f"目录 {directory} 不存在"
        
        results: List[Dict[str, Any]] = []
        
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if fnmatch.fnmatch(file, file_pattern):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                for line_num, line in enumerate(f, 1):
                                    matched = False
                                    if use_regex:
                                        flags = 0 if case_sensitive else re.IGNORECASE
                                        if re.search(search_text, line, flags):
                                            matched = True
                                    else:
                                        if case_sensitive:
                                            matched = search_text in line
                                        else:
                                            matched = search_text.lower() in line.lower()
                                    
                                    if matched:
                                        results.append({
                                            "file": file_path,
                                            "line": line_num,
                                            "content": line.strip()
                                        })
                        except Exception:
                            continue
            
            return format_search_results(results, self.max_results)
        except Exception as e:
            return f"搜索失败: {e}"


class FindFilesTool(Tool):
    """按文件名模式搜索文件"""
    
    def __init__(self, work_dir: Path, max_files: int = 100):
        """
        初始化文件查找工具
        
        Args:
            work_dir: 工作目录
            max_files: 最大返回文件数
        """
        super().__init__(work_dir)
        self.max_files = max_files
    
    def _get_description(self) -> str:
        return "按文件名模式搜索文件（支持通配符，如 '*.py', 'test*.js'）。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "文件名匹配模式（如 '*.py', 'test*.js', '**/config.json'）"},
                "directory": {"type": "string", "description": f"要搜索的目录路径（默认工作目录）", "default": str(self.work_dir)},
                "recursive": {"type": "boolean", "description": "是否递归搜索子目录（默认 true）", "default": True},
            },
            "required": ["pattern"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        pattern = parameters["pattern"]
        directory = parameters.get("directory", str(self.work_dir))
        recursive = parameters.get("recursive", True)
        
        if not os.path.exists(directory):
            return f"目录 {directory} 不存在"
        
        try:
            files: List[str] = []
            if recursive:
                for root, dirs, filenames in os.walk(directory):
                    for filename in filenames:
                        if fnmatch.fnmatch(filename, pattern):
                            files.append(os.path.join(root, filename))
            else:
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path) and fnmatch.fnmatch(filename, pattern):
                        files.append(file_path)
            
            return format_file_list(files, self.max_files)
        except Exception as e:
            return f"搜索文件失败: {e}"

