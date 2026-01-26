# -*- coding: utf-8 -*-
"""其他工具"""

import zipfile
import tempfile
from pathlib import Path
from typing import Dict, Any
import json

from tools.base import Tool
from utils import normalize_path


class FileUploadTool(Tool):
    """上传本地文件供模型读取"""
    
    def _get_description(self) -> str:
        return "上传本地文件供模型读取。典型使用场景：提供数据集、文档、代码等供后续处理。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "本地文件路径"
                }
            },
            "required": ["path"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return json.dumps({
                "success": False,
                "error": f"文件 {path} 不存在"
            }, ensure_ascii=False)
        
        # 返回文件信息
        return json.dumps({
            "success": True,
            "path": str(abs_path),
            "size": abs_path.stat().st_size
        }, ensure_ascii=False)


class FileDownloadTool(Tool):
    """下载模型生成的文件"""
    
    def _get_description(self) -> str:
        return "下载模型生成的文件（如图片、CSV、PDF 等）。典型使用场景：获取生成的报告、图表或其他产出。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径"
                }
            },
            "required": ["path"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        
        try:
            abs_path = normalize_path(path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_path.exists():
            return json.dumps({
                "success": False,
                "error": f"文件 {path} 不存在"
            }, ensure_ascii=False)
        
        return json.dumps({
            "success": True,
            "path": str(abs_path),
            "size": abs_path.stat().st_size
        }, ensure_ascii=False)


class DalleTool(Tool):
    """调用 DALL·E 生成图像"""
    
    def _get_description(self) -> str:
        return "调用 DALL·E 生成图像（根据文字描述）。典型使用场景：生成概念图、插画、示意图等视觉素材。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "图像描述"
                }
            },
            "required": ["prompt"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        prompt = parameters["prompt"]
        
        # 注意：实际的 DALL·E API 调用需要集成 OpenAI SDK
        # 这里返回一个占位符响应
        return json.dumps({
            "success": True,
            "note": "这是一个占位符实现，实际使用时需要集成 OpenAI DALL·E API",
            "prompt": prompt
        }, ensure_ascii=False)


class ZipTool(Tool):
    """将指定文件/目录压缩为 zip 包"""
    
    def _get_description(self) -> str:
        return "将指定文件/目录压缩为 zip 包。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "要压缩的文件或目录路径"
                },
                "dest_zip": {
                    "type": "string",
                    "description": "目标 zip 文件路径"
                },
                "compresslevel": {
                    "type": "integer",
                    "description": "压缩级别（0-9），默认 6"
                }
            },
            "required": ["source", "dest_zip"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        source = parameters["source"]
        dest_zip = parameters["dest_zip"]
        compresslevel = parameters.get("compresslevel", 6)
        
        try:
            abs_source = normalize_path(source, self.work_dir)
            abs_dest = normalize_path(dest_zip, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_source.exists():
            return json.dumps({
                "success": False,
                "error": f"源路径 {source} 不存在"
            }, ensure_ascii=False)
        
        try:
            with zipfile.ZipFile(abs_dest, "w", zipfile.ZIP_DEFLATED, compresslevel=compresslevel) as zipf:
                if abs_source.is_file():
                    zipf.write(abs_source, abs_source.name)
                else:
                    for file_path in abs_source.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(abs_source)
                            zipf.write(file_path, arcname)
            
            return json.dumps({
                "success": True,
                "path": str(abs_dest)
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class UnzipTool(Tool):
    """解压 zip 包到目标目录"""
    
    def _get_description(self) -> str:
        return "解压 zip 包到目标目录。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "zip_path": {
                    "type": "string",
                    "description": "zip 文件路径"
                },
                "dest_dir": {
                    "type": "string",
                    "description": "目标解压目录"
                },
                "overwrite": {
                    "type": "boolean",
                    "description": "是否覆盖已存在的文件"
                }
            },
            "required": ["zip_path", "dest_dir"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        zip_path = parameters["zip_path"]
        dest_dir = parameters["dest_dir"]
        overwrite = parameters.get("overwrite", False)
        
        try:
            abs_zip = normalize_path(zip_path, self.work_dir)
            abs_dest = normalize_path(dest_dir, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_zip.exists():
            return json.dumps({
                "success": False,
                "error": f"zip 文件 {zip_path} 不存在"
            }, ensure_ascii=False)
        
        if not abs_zip.is_file():
            return json.dumps({
                "success": False,
                "error": f"路径 {zip_path} 不是文件"
            }, ensure_ascii=False)
        
        try:
            abs_dest.mkdir(parents=True, exist_ok=True)
            
            extracted_files = []
            with zipfile.ZipFile(abs_zip, "r") as zipf:
                for member in zipf.namelist():
                    # 安全检查：防止路径遍历攻击
                    target_path = abs_dest / member
                    if not str(target_path.resolve()).startswith(str(abs_dest.resolve())):
                        continue
                    
                    if overwrite or not target_path.exists():
                        zipf.extract(member, abs_dest)
                        extracted_files.append(member)
            
            return json.dumps({
                "success": True,
                "files": extracted_files
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
