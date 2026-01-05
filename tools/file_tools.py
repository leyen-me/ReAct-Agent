# -*- coding: utf-8 -*-
"""文件操作工具"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any

from tools.base import Tool


class ReadFileTool(Tool):
    """读取文件内容"""
    
    def _get_description(self) -> str:
        return "读取文件内容"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                return file.read()
        except Exception as e:
            return f"读取文件失败: {e}"


class WriteFileTool(Tool):
    """写入文件内容"""
    
    def _get_description(self) -> str:
        return "写入文件内容"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                file.write(parameters["content"])
            return f"文件 {path} 写入成功"
        except Exception as e:
            return f"写入文件失败: {e}"


class DeleteFileTool(Tool):
    """删除文件"""
    
    def _get_description(self) -> str:
        return "删除文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            os.remove(path)
            return f"文件 {path} 删除成功"
        except Exception as e:
            return f"删除文件失败: {e}"


class CreateFileTool(Tool):
    """创建文件"""
    
    def _get_description(self) -> str:
        return "创建文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if os.path.exists(path):
            return f"文件 {path} 已存在"
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                file.write("")
            return f"文件 {path} 创建成功"
        except Exception as e:
            return f"创建文件失败: {e}"


class RenameFileTool(Tool):
    """重命名文件"""
    
    def _get_description(self) -> str:
        return "重命名文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "new_name": {"type": "string", "description": "新文件名"},
            },
            "required": ["path", "new_name"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        new_name = parameters["new_name"]
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        # 处理新路径
        if os.path.isabs(new_name):
            new_path = new_name
        else:
            dir_name = os.path.dirname(path)
            new_path = os.path.join(dir_name, new_name)
        
        is_valid, error = self.validate_path(new_path)
        if not is_valid:
            return f"新文件路径错误: {error}"
        
        if os.path.exists(new_path):
            return f"目标文件 {new_path} 已存在"
        
        try:
            os.rename(path, new_path)
            return f"文件 {path} 重命名成功为 {new_path}"
        except Exception as e:
            return f"重命名文件失败: {e}"


class ListFilesTool(Tool):
    """列出文件列表"""
    
    def _get_description(self) -> str:
        return "列出文件列表"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"},
                "ignore_patterns": {"type": "array", "items": {"type": "string"}, "description": "忽略的文件/目录模式（如 ['node_modules', '*.pyc']）", "default": []}
            },
            "required": ["path"],
        }
    
    def _should_ignore(self, path: str, ignore_patterns: list) -> bool:
        """检查路径是否应该被忽略"""
        import fnmatch
        
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        return False
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        ignore_patterns = parameters.get("ignore_patterns", [])
        
        if not os.path.exists(path):
            return f"目录 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是目录"
        
        try:
            files = []
            for f in os.listdir(path):
                full_path = os.path.join(path, f)
                if not self._should_ignore(full_path, ignore_patterns):
                    files.append(full_path)
            
            return "\n".join(files) if files else "目录为空"
        except Exception as e:
            return f"列出文件失败: {e}"


class TreeFilesTool(Tool):
    """显示目录树结构"""
    
    def _get_description(self) -> str:
        return "显示目录树结构"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"},
                "max_depth": {"type": "number", "description": "最大深度（默认：3）", "default": 3},
                "ignore_patterns": {"type": "array", "items": {"type": "string"}, "description": "忽略的文件/目录模式（如 ['node_modules', '*.pyc']）", "default": []}
            },
            "required": ["path"],
        }
    
    def _should_ignore(self, path: str, ignore_patterns: list) -> bool:
        """检查路径是否应该被忽略"""
        import fnmatch
        
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True
        return False
    
    def _build_tree(self, path: str, prefix: str = "", depth: int = 0, max_depth: int = 3, ignore_patterns: list = None) -> str:
        """构建目录树结构"""
        if ignore_patterns is None:
            ignore_patterns = []
        
        if depth >= max_depth:
            return ""
        
        if not os.path.exists(path) or not os.path.isdir(path):
            return ""
        
        try:
            items = []
            for item in sorted(os.listdir(path)):
                full_path = os.path.join(path, item)
                if self._should_ignore(full_path, ignore_patterns):
                    continue
                
                items.append(item)
            
            tree_lines = []
            for i, item in enumerate(items):
                full_path = os.path.join(path, item)
                is_last = i == len(items) - 1
                
                connector = "└── " if is_last else "├── "
                tree_lines.append(f"{prefix}{connector}{item}")
                
                if os.path.isdir(full_path):
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    subtree = self._build_tree(full_path, new_prefix, depth + 1, max_depth, ignore_patterns)
                    if subtree:
                        tree_lines.append(subtree)
            
            return "\n".join(tree_lines)
        except Exception:
            return ""
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        max_depth = parameters.get("max_depth", 3)
        ignore_patterns = parameters.get("ignore_patterns", [])
        
        if not os.path.exists(path):
            return f"目录 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是目录"
        
        try:
            tree = self._build_tree(path, max_depth=max_depth, ignore_patterns=ignore_patterns)
            if not tree:
                return "目录为空或所有内容都被忽略"
            
            return f"{path}\n{tree}"
        except Exception as e:
            return f"显示目录树失败: {e}"


class EditFileTool(Tool):
    """编辑文件内容（部分替换）"""
    
    def _get_description(self) -> str:
        return "编辑文件内容（部分替换），只替换匹配的文本部分，保留文件其他内容不变。这是推荐的文件编辑方式，类似于 Cursor 的部分替换功能。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "old_string": {"type": "string", "description": "要替换的原始文本（必须精确匹配，包括空格、换行等）"},
                "new_string": {"type": "string", "description": "替换后的新文本"},
                "replace_all": {"type": "boolean", "description": "是否替换所有匹配项（默认 false，只替换第一个匹配项）", "default": False},
            },
            "required": ["path", "old_string", "new_string"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            old_string = parameters["old_string"]
            new_string = parameters["new_string"]
            replace_all = parameters.get("replace_all", False)
            
            if old_string not in content:
                return "错误：文件中未找到要替换的文本。请确保 old_string 与文件中的内容完全匹配（包括空格、换行、缩进等）。"
            
            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1
            
            with open(path, "w", encoding="utf-8") as file:
                file.write(new_content)
            
            return f"文件 {path} 编辑成功，已替换 {count} 处匹配的文本"
        except Exception as e:
            return f"编辑文件失败: {e}"


class CreateFolderTool(Tool):
    """创建文件夹"""
    
    def _get_description(self) -> str:
        return "创建文件夹"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件夹路径错误: {error}"
        
        if os.path.exists(path):
            return f"文件夹 {path} 已存在"
        
        try:
            os.makedirs(path, exist_ok=True)
            return f"文件夹 {path} 创建成功"
        except Exception as e:
            return f"创建文件夹失败: {e}"


class DeleteFolderTool(Tool):
    """删除文件夹及其所有内容（递归删除）"""
    
    def _get_description(self) -> str:
        return "删除文件夹及其所有内容（递归删除）"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件夹路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件夹 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是文件夹"
        
        try:
            shutil.rmtree(path)
            return f"文件夹 {path} 删除成功"
        except Exception as e:
            return f"删除文件夹失败: {e}"


class MoveFileTool(Tool):
    """移动文件或文件夹到新位置"""
    
    def _get_description(self) -> str:
        return "移动文件或文件夹到新位置"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        source = parameters["source"]
        destination = parameters["destination"]
        
        is_valid, error = self.validate_path(source)
        if not is_valid:
            return f"源路径错误: {error}"
        
        is_valid, error = self.validate_path(destination)
        if not is_valid:
            return f"目标路径错误: {error}"
        
        if not os.path.exists(source):
            return f"源路径 {source} 不存在"
        
        try:
            shutil.move(source, destination)
            return f"成功将 {source} 移动到 {destination}"
        except Exception as e:
            return f"移动文件失败: {e}"


class CopyFileTool(Tool):
    """复制文件或文件夹到新位置"""
    
    def _get_description(self) -> str:
        return "复制文件或文件夹到新位置"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        source = parameters["source"]
        destination = parameters["destination"]
        
        is_valid, error = self.validate_path(source)
        if not is_valid:
            return f"源路径错误: {error}"
        
        is_valid, error = self.validate_path(destination)
        if not is_valid:
            return f"目标路径错误: {error}"
        
        if not os.path.exists(source):
            return f"源路径 {source} 不存在"
        
        try:
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            return f"成功将 {source} 复制到 {destination}"
        except Exception as e:
            return f"复制文件失败: {e}"

