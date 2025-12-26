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
                "path": {"type": "string", "description": "文件路径"}
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
                "path": {"type": "string", "description": "文件路径"},
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
                "path": {"type": "string", "description": "文件路径"}
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
                "path": {"type": "string", "description": "文件路径"}
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
                "path": {"type": "string", "description": "文件路径"},
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
                "path": {"type": "string", "description": "文件夹路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        
        if not os.path.exists(path):
            return f"目录 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是目录"
        
        try:
            files = [os.path.join(path, f) for f in os.listdir(path)]
            return "\n".join(files) if files else "目录为空"
        except Exception as e:
            return f"列出文件失败: {e}"


class EditFileTool(Tool):
    """编辑文件内容（部分替换）"""
    
    def _get_description(self) -> str:
        return "编辑文件内容（部分替换），只替换匹配的文本部分，保留文件其他内容不变。这是推荐的文件编辑方式，类似于 Cursor 的部分替换功能。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
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

