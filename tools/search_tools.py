# -*- coding: utf-8 -*-
"""搜索工具"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional

from pathspec import GitIgnoreSpec

from tools.base import Tool
from utils import format_search_results, format_file_list


class SearchInFilesTool(Tool):
    """在文件中搜索文本内容"""
    
    # 默认忽略的目录列表（当没有 .gitignore 时使用）
    DEFAULT_IGNORE_DIRS = {
        '__pycache__', '.git', '.svn', '.hg', '.idea', '.vscode',
        'node_modules', 'venv', 'env', '.venv', 'ENV',
        'build', 'dist', '.pytest_cache', '.mypy_cache',
        '.agent_history', '.agent_config', '.agent_logs'
    }
    
    def __init__(self, work_dir: Path, max_results: int = 50):
        """
        初始化搜索工具
        
        Args:
            work_dir: 工作目录
            max_results: 最大返回结果数
        """
        super().__init__(work_dir)
        self.max_results = max_results
        self._gitignore_spec: Optional[GitIgnoreSpec] = None
    
    def _load_gitignore(self, root_dir: str) -> Optional[GitIgnoreSpec]:
        """
        加载并解析 .gitignore 文件
        
        Args:
            root_dir: 根目录路径
            
        Returns:
            GitIgnoreSpec 对象，如果加载失败则返回 None
        """
        try:
            gitignore_path = os.path.join(root_dir, '.gitignore')
            if not os.path.exists(gitignore_path):
                return None
            
            with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
                # GitIgnoreSpec.from_lines 可以直接接受文件对象
                return GitIgnoreSpec.from_lines(f)
        except Exception:
            # 如果加载失败，返回 None，使用默认忽略列表
            return None
    
    def _should_ignore(self, path: str, root_dir: str, is_dir: bool = False) -> bool:
        """
        检查路径是否应该被忽略
        
        Args:
            path: 要检查的路径（绝对路径或相对路径）
            root_dir: 根目录路径
            is_dir: 是否为目录
            
        Returns:
            如果应该忽略则返回 True
        """
        # 如果路径不在根目录下，不忽略
        try:
            rel_path = os.path.relpath(path, root_dir)
            if rel_path.startswith('..'):
                return False
        except ValueError:
            # 如果路径无法转换为相对路径，不忽略
            return False
        
        # 使用 .gitignore 规则（如果可用）
        if self._gitignore_spec:
            try:
                # pathspec 使用正斜杠作为路径分隔符
                normalized_path = rel_path.replace(os.sep, '/')
                if is_dir:
                    normalized_path += '/'
                return self._gitignore_spec.match_file(normalized_path)
            except Exception:
                pass
        
        # 如果没有 .gitignore 或解析失败，使用默认忽略列表
        path_parts = Path(rel_path).parts
        if path_parts:
            first_part = path_parts[0]
            if first_part in self.DEFAULT_IGNORE_DIRS:
                return True
        
        return False
    
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
        
        # 加载 .gitignore 规则
        self._gitignore_spec = self._load_gitignore(directory)
        
        results: List[Dict[str, Any]] = []
        
        try:
            for root, dirs, files in os.walk(directory):
                # 排除应该忽略的目录，避免遍历 node_modules 等大型目录
                dirs[:] = [
                    d for d in dirs 
                    if not self._should_ignore(os.path.join(root, d), directory, is_dir=True)
                ]
                
                for file in files:
                    if fnmatch.fnmatch(file, file_pattern):
                        file_path = os.path.join(root, file)
                        
                        # 检查文件是否应该被忽略
                        if self._should_ignore(file_path, directory, is_dir=False):
                            continue
                        
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
    
    # 默认忽略的目录列表（当没有 .gitignore 时使用）
    DEFAULT_IGNORE_DIRS = {
        '__pycache__', '.git', '.svn', '.hg', '.idea', '.vscode',
        'node_modules', 'venv', 'env', '.venv', 'ENV',
        'build', 'dist', '.pytest_cache', '.mypy_cache',
        '.agent_history', '.agent_config', '.agent_logs'
    }
    
    def __init__(self, work_dir: Path, max_files: int = 100):
        """
        初始化文件查找工具
        
        Args:
            work_dir: 工作目录
            max_files: 最大返回文件数
        """
        super().__init__(work_dir)
        self.max_files = max_files
        self._gitignore_spec: Optional[GitIgnoreSpec] = None
    
    def _load_gitignore(self, root_dir: str) -> Optional[GitIgnoreSpec]:
        """
        加载并解析 .gitignore 文件
        
        Args:
            root_dir: 根目录路径
            
        Returns:
            GitIgnoreSpec 对象，如果加载失败则返回 None
        """
        try:
            gitignore_path = os.path.join(root_dir, '.gitignore')
            if not os.path.exists(gitignore_path):
                return None
            
            with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
                # GitIgnoreSpec.from_lines 可以直接接受文件对象
                return GitIgnoreSpec.from_lines(f)
        except Exception:
            # 如果加载失败，返回 None，使用默认忽略列表
            return None
    
    def _should_ignore(self, path: str, root_dir: str, is_dir: bool = False) -> bool:
        """
        检查路径是否应该被忽略
        
        Args:
            path: 要检查的路径（绝对路径或相对路径）
            root_dir: 根目录路径
            is_dir: 是否为目录
            
        Returns:
            如果应该忽略则返回 True
        """
        # 如果路径不在根目录下，不忽略
        try:
            rel_path = os.path.relpath(path, root_dir)
            if rel_path.startswith('..'):
                return False
        except ValueError:
            # 如果路径无法转换为相对路径，不忽略
            return False
        
        # 使用 .gitignore 规则（如果可用）
        if self._gitignore_spec:
            try:
                # pathspec 使用正斜杠作为路径分隔符
                normalized_path = rel_path.replace(os.sep, '/')
                if is_dir:
                    normalized_path += '/'
                return self._gitignore_spec.match_file(normalized_path)
            except Exception:
                pass
        
        # 如果没有 .gitignore 或解析失败，使用默认忽略列表
        path_parts = Path(rel_path).parts
        if path_parts:
            first_part = path_parts[0]
            if first_part in self.DEFAULT_IGNORE_DIRS:
                return True
        
        return False
    
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
        
        # 加载 .gitignore 规则
        self._gitignore_spec = self._load_gitignore(directory)
        
        try:
            files: List[str] = []
            if recursive:
                for root, dirs, filenames in os.walk(directory):
                    # 排除应该忽略的目录，避免遍历 node_modules 等大型目录
                    dirs[:] = [
                        d for d in dirs 
                        if not self._should_ignore(os.path.join(root, d), directory, is_dir=True)
                    ]
                    
                    for filename in filenames:
                        file_path = os.path.join(root, filename)
                        
                        # 检查文件是否应该被忽略
                        if self._should_ignore(file_path, directory, is_dir=False):
                            continue
                        
                        if fnmatch.fnmatch(filename, pattern):
                            files.append(file_path)
            else:
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        # 检查文件是否应该被忽略
                        if self._should_ignore(file_path, directory, is_dir=False):
                            continue
                        if fnmatch.fnmatch(filename, pattern):
                            files.append(file_path)
            
            return format_file_list(files, self.max_files)
        except Exception as e:
            return f"搜索文件失败: {e}"