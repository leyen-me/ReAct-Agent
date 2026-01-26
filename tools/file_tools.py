# -*- coding: utf-8 -*-
"""文件操作工具"""

import os
import hashlib
import difflib
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

from tools.base import Tool
from utils import load_gitignore, should_ignore, normalize_path


class PrintTreeTool(Tool):
    """递归打印指定目录的文件树结构"""
    
    def _get_description(self) -> str:
        return "递归打印指定目录（或仓库根目录）的文件树结构，帮助快速了解项目结构。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要打印的根目录路径，默认是工作区根目录 '.'"
                },
                "depth": {
                    "type": ["integer", "null"],
                    "description": "递归深度，0 表示只显示根目录本身，null 或省略表示无限深度"
                },
                "ignore": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要忽略的文件/目录模式列表，如 ['*.pyc', '__pycache__']"
                }
            },
            "required": []
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", ".")
        depth = parameters.get("depth")
        ignore_patterns = parameters.get("ignore", [])
        
        # 规范化路径
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return f"路径 {path} 不存在"
        
        if not abs_path.is_dir():
            return f"路径 {path} 不是目录"
        
        # 加载 gitignore
        gitignore_spec = load_gitignore(str(self.work_dir))
        
        lines = []
        self._print_tree_recursive(abs_path, self.work_dir, lines, depth, 0, ignore_patterns, gitignore_spec)
        
        return "\n".join(lines)
    
    def _print_tree_recursive(
        self,
        current_path: Path,
        root_dir: Path,
        lines: List[str],
        max_depth: Optional[int],
        current_depth: int,
        ignore_patterns: List[str],
        gitignore_spec
    ) -> None:
        """递归打印目录树"""
        if max_depth is not None and current_depth > max_depth:
            return
        
        # 获取相对路径用于显示
        rel_path = os.path.relpath(current_path, root_dir)
        if rel_path == ".":
            prefix = ""
            name = str(root_dir.name) if root_dir.name else "."
        else:
            prefix = "  " * current_depth
            name = current_path.name
        
        # 检查是否应该忽略
        if should_ignore(str(current_path), str(root_dir), gitignore_spec, current_path.is_dir()):
            return
        
        # 检查自定义忽略模式
        for pattern in ignore_patterns:
            if self._match_pattern(name, pattern):
                return
        
        lines.append(f"{prefix}{name}/" if current_path.is_dir() else f"{prefix}{name}")
        
        if current_path.is_dir():
            try:
                children = sorted(current_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                for child in children:
                    self._print_tree_recursive(
                        child, root_dir, lines, max_depth, current_depth + 1,
                        ignore_patterns, gitignore_spec
                    )
            except PermissionError:
                lines.append(f"{prefix}  [权限不足]")
    
    def _match_pattern(self, name: str, pattern: str) -> bool:
        """简单的模式匹配"""
        import fnmatch
        return fnmatch.fnmatch(name, pattern)


class ListFilesTool(Tool):
    """列出指定目录下的文件（支持递归）"""
    
    def _get_description(self) -> str:
        return "列出指定目录下的文件（支持递归）。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要列出的目录路径"
                },
                "pattern": {
                    "type": "string",
                    "description": "glob 模式，如 '*.js'"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出子目录，默认 false"
                }
            },
            "required": ["path"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        pattern = parameters.get("pattern")
        recursive = parameters.get("recursive", False)
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return f"路径 {path} 不存在"
        
        if not abs_path.is_dir():
            return f"路径 {path} 不是目录"
        
        files = []
        # 规范化工作目录路径，避免符号链接问题
        work_dir_resolved = self.work_dir.resolve()
        
        if recursive:
            for file_path in abs_path.rglob("*"):
                if file_path.is_file():
                    if pattern is None or file_path.match(pattern):
                        # 使用 resolve() 规范化路径，然后计算相对路径
                        file_path_resolved = file_path.resolve()
                        try:
                            rel_path = file_path_resolved.relative_to(work_dir_resolved)
                            files.append(str(rel_path))
                        except ValueError:
                            # 如果路径不在工作目录内，跳过
                            continue
        else:
            for file_path in abs_path.iterdir():
                if file_path.is_file():
                    if pattern is None or file_path.match(pattern):
                        # 使用 resolve() 规范化路径，然后计算相对路径
                        file_path_resolved = file_path.resolve()
                        try:
                            rel_path = file_path_resolved.relative_to(work_dir_resolved)
                            files.append(str(rel_path))
                        except ValueError:
                            # 如果路径不在工作目录内，跳过
                            continue
        
        return json.dumps(files, ensure_ascii=False)


class FileSearchTool(Tool):
    """在代码库或文档中全文搜索关键字或正则表达式"""
    
    def _get_description(self) -> str:
        return "在代码库或文档中全文搜索关键字或正则表达式，返回匹配的文件路径和摘要。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "要搜索的字符串或正则表达式（支持 re 语法）"
                },
                "path": {
                    "type": "string",
                    "description": "搜索起始目录，默认是根目录 '.'"
                },
                "regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式，默认 false"
                },
                "max_results": {
                    "type": ["integer", "null"],
                    "description": "返回的最大匹配数，默认 100，设为 null 表示不限制"
                }
            },
            "required": ["query"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        query = parameters["query"]
        path = parameters.get("path", ".")
        use_regex = parameters.get("regex", False)
        max_results = parameters.get("max_results", 100)
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return f"路径 {path} 不存在"
        
        matches = []
        gitignore_spec = load_gitignore(str(self.work_dir))
        # 规范化工作目录路径，避免符号链接问题
        work_dir_resolved = self.work_dir.resolve()
        
        # 遍历文件
        for file_path in abs_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            if should_ignore(str(file_path), str(self.work_dir), gitignore_spec):
                continue
            
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        matched = False
                        if use_regex:
                            import re
                            try:
                                if re.search(query, line):
                                    matched = True
                            except re.error:
                                return f"正则表达式错误: {query}"
                        else:
                            if query in line:
                                matched = True
                        
                        if matched:
                            # 使用 resolve() 规范化路径，然后计算相对路径
                            file_path_resolved = file_path.resolve()
                            try:
                                rel_path = str(file_path_resolved.relative_to(work_dir_resolved))
                            except ValueError:
                                # 如果路径不在工作目录内，跳过
                                continue
                            matches.append({
                                "file": rel_path,
                                "line": line_num,
                                "content": line.rstrip()
                            })
                            
                            if max_results is not None and len(matches) >= max_results:
                                return json.dumps(matches, ensure_ascii=False, indent=2)
            except Exception:
                continue
        
        return json.dumps(matches, ensure_ascii=False, indent=2)


class OpenFileTool(Tool):
    """打开并读取指定文件的内容（最多 20 KB）"""
    
    def _get_description(self) -> str:
        return "打开并读取指定文件的内容（最多 20 KB），返回纯文本。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "相对于工作区根目录的文件路径"
                },
                "line_start": {
                    "type": "integer",
                    "description": "只返回从该行开始的内容，默认 1（文件开头）"
                },
                "line_end": {
                    "type": ["integer", "null"],
                    "description": "只返回到该行结束，默认返回到文件末尾或 20 KB 限制"
                }
            },
            "required": ["path"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        line_start = parameters.get("line_start", 1)
        line_end = parameters.get("line_end")
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return f"文件 {path} 不存在"
        
        if not abs_path.is_file():
            return f"路径 {path} 不是文件"
        
        try:
            with open(abs_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            
            # 调整行号（从1开始）
            start_idx = max(0, line_start - 1)
            end_idx = len(lines) if line_end is None else min(len(lines), line_end)
            
            selected_lines = lines[start_idx:end_idx]
            content = "".join(selected_lines)
            
            # 限制 20 KB
            max_size = 20 * 1024
            if len(content.encode("utf-8")) > max_size:
                content = content[:max_size]
                # 尝试在最后一个换行符处截断
                last_newline = content.rfind("\n")
                if last_newline > 0:
                    content = content[:last_newline + 1]
                content += "\n... (内容被截断，超过 20 KB)"
            
            return content
        except Exception as e:
            return f"读取文件失败: {e}"


class ReadFileTool(Tool):
    """读取文件的完整内容，支持二进制读取"""
    
    def _get_description(self) -> str:
        return "读取文件的完整内容，常用于后续处理。与 open_file 类似，但专注于读取操作，支持二进制读取。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "binary": {
                    "type": "boolean",
                    "description": "是否以二进制模式读取，默认 false"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认 'utf-8'"
                }
            },
            "required": ["path"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        binary = parameters.get("binary", False)
        encoding = parameters.get("encoding", "utf-8")
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return f"文件 {path} 不存在"
        
        if not abs_path.is_file():
            return f"路径 {path} 不是文件"
        
        try:
            if binary:
                with open(abs_path, "rb") as f:
                    content = f.read()
                import base64
                return base64.b64encode(content).decode("utf-8")
            else:
                with open(abs_path, "r", encoding=encoding, errors="ignore") as f:
                    return f.read()
        except Exception as e:
            return f"读取文件失败: {e}"


class WriteFileTool(Tool):
    """向指定文件写入内容（覆盖或追加）"""
    
    def _get_description(self) -> str:
        return "向指定文件写入内容（覆盖或追加），可用于创建新文件或修改已有文件。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                },
                "append": {
                    "type": "boolean",
                    "description": "是否追加模式，默认 false（覆盖模式）"
                },
                "mode": {
                    "type": "string",
                    "description": "写入模式，'w' 覆盖、'a' 追加，默认 'w'"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码，默认 'utf-8'"
                }
            },
            "required": ["path", "content"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        content = parameters["content"]
        append = parameters.get("append", False)
        mode = parameters.get("mode", "w")
        encoding = parameters.get("encoding", "utf-8")
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        # 确保父目录存在
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            write_mode = "a" if append or mode == "a" else "w"
            with open(abs_path, write_mode, encoding=encoding) as f:
                f.write(content)
            return "True"
        except Exception as e:
            return f"写入文件失败: {e}"


class DiffTool(Tool):
    """对比两个文件或目录，返回统一 diff 格式"""
    
    def _get_description(self) -> str:
        return "对比两个文件或目录，返回统一 diff 格式。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path_a": {
                    "type": "string",
                    "description": "第一个文件或目录路径"
                },
                "path_b": {
                    "type": "string",
                    "description": "第二个文件或目录路径"
                },
                "ignore_whitespace": {
                    "type": "boolean",
                    "description": "是否忽略空白字符差异"
                }
            },
            "required": ["path_a", "path_b"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path_a = parameters["path_a"]
        path_b = parameters["path_b"]
        ignore_whitespace = parameters.get("ignore_whitespace", False)
        
        try:
            abs_path_a = normalize_path(path_a, self.work_dir)
            abs_path_b = normalize_path(path_b, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path_a.exists():
            return f"路径 {path_a} 不存在"
        if not abs_path_b.exists():
            return f"路径 {path_b} 不存在"
        
        try:
            if abs_path_a.is_file() and abs_path_b.is_file():
                # 文件对比
                with open(abs_path_a, "r", encoding="utf-8", errors="ignore") as f:
                    lines_a = f.readlines()
                with open(abs_path_b, "r", encoding="utf-8", errors="ignore") as f:
                    lines_b = f.readlines()
                
                if ignore_whitespace:
                    lines_a = [line.rstrip() + "\n" for line in lines_a]
                    lines_b = [line.rstrip() + "\n" for line in lines_b]
                
                diff = difflib.unified_diff(
                    lines_a, lines_b,
                    fromfile=str(abs_path_a),
                    tofile=str(abs_path_b),
                    lineterm=""
                )
                return "".join(diff)
            else:
                return "目录对比功能暂未实现"
        except Exception as e:
            return f"对比失败: {e}"


class ChecksumTool(Tool):
    """计算文件的哈希值（MD5、SHA1、SHA256 等）"""
    
    def _get_description(self) -> str:
        return "计算文件的哈希值（MD5、SHA1、SHA256 等）。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                },
                "algorithm": {
                    "type": "string",
                    "description": "哈希算法，可选 'md5'、'sha1'、'sha256'，默认 'sha256'",
                    "enum": ["md5", "sha1", "sha256"]
                }
            },
            "required": ["path"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        algorithm = parameters.get("algorithm", "sha256")
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return f"文件 {path} 不存在"
        
        if not abs_path.is_file():
            return f"路径 {path} 不是文件"
        
        try:
            hash_obj = hashlib.new(algorithm)
            with open(abs_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
            return hash_obj.hexdigest()
        except Exception as e:
            return f"计算哈希失败: {e}"
