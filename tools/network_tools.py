# -*- coding: utf-8 -*-
"""网络工具"""

import urllib.request
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional
import json

from tools.base import Tool
from utils import normalize_path


class BrowseTool(Tool):
    """通过网络搜索获取最新的网页信息、文档或图片链接"""
    
    def _get_description(self) -> str:
        return "通过网络搜索获取最新的网页信息、文档或图片链接。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数"
                }
            },
            "required": ["query"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        query = parameters["query"]
        max_results = parameters.get("max_results", 10)
        
        # 注意：实际的网络搜索功能需要集成搜索引擎 API
        # 这里返回一个占位符响应
        return json.dumps({
            "results": [
                {
                    "title": f"搜索结果: {query}",
                    "url": f"https://example.com/search?q={urllib.parse.quote(query)}",
                    "snippet": f"关于 '{query}' 的搜索结果"
                }
            ],
            "note": "这是一个占位符实现，实际使用时需要集成搜索引擎 API"
        }, ensure_ascii=False)


class SearchTool(BrowseTool):
    """搜索工具（browse 的简化版）"""
    
    def _get_description(self) -> str:
        return "搜索工具（browse 的简化版），只返回搜索结果的摘要或链接。"


class DownloadTool(Tool):
    """从网络 URL 下载文件到本地临时目录"""
    
    def _get_description(self) -> str:
        return "从网络 URL 下载文件到本地临时目录。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要下载的文件 URL"
                },
                "dest_path": {
                    "type": "string",
                    "description": "目标保存路径"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）"
                }
            },
            "required": ["url"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        url = parameters["url"]
        dest_path = parameters.get("dest_path")
        timeout = parameters.get("timeout", 30)
        
        try:
            if dest_path:
                try:
                    abs_dest = normalize_path(dest_path, self.work_dir)
                except ValueError as e:
                    return f"路径错误: {e}"
            else:
                # 使用临时目录
                import tempfile
                filename = url.split("/")[-1] or "download"
                abs_dest = Path(tempfile.gettempdir()) / filename
            
            # 确保父目录存在
            abs_dest.parent.mkdir(parents=True, exist_ok=True)
            
            # 下载文件
            with urllib.request.urlopen(url, timeout=timeout) as response:
                with open(abs_dest, "wb") as f:
                    f.write(response.read())
            
            return json.dumps({
                "success": True,
                "path": str(abs_dest)
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class UploadTool(Tool):
    """将本地文件上传到指定的远程存储"""
    
    def _get_description(self) -> str:
        return "将本地文件上传到指定的远程存储（如 S3、FTP），需要预先配置凭证。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "本地文件路径"
                },
                "remote_path": {
                    "type": "string",
                    "description": "远程存储路径"
                },
                "service": {
                    "type": "string",
                    "description": "存储服务类型，如 's3'"
                },
                "metadata": {
                    "type": "object",
                    "description": "元数据字典"
                }
            },
            "required": ["local_path", "remote_path", "service"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        local_path = parameters["local_path"]
        remote_path = parameters["remote_path"]
        service = parameters["service"]
        metadata = parameters.get("metadata", {})
        
        try:
            abs_local = normalize_path(local_path, self.work_dir)
        except ValueError as e:
            return f"路径错误: {e}"
        
        if not abs_local.exists():
            return json.dumps({
                "success": False,
                "error": f"文件 {local_path} 不存在"
            }, ensure_ascii=False)
        
        # 注意：实际上传功能需要集成相应的服务 SDK
        # 这里返回一个占位符响应
        return json.dumps({
            "success": True,
            "note": f"这是一个占位符实现，实际使用时需要集成 {service} SDK",
            "local_path": str(abs_local),
            "remote_path": remote_path,
            "service": service
        }, ensure_ascii=False)
