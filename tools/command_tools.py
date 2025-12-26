# -*- coding: utf-8 -*-
"""命令执行工具"""

import subprocess
from pathlib import Path
from typing import Dict, Any

from tools.base import Tool


class RunCommandTool(Tool):
    """执行终端命令"""
    
    def __init__(self, work_dir: Path, timeout: int = 300):
        """
        初始化命令执行工具
        
        Args:
            work_dir: 工作目录
            timeout: 默认超时时间（秒）
        """
        self.default_timeout = timeout
        super().__init__(work_dir)
    
    def _get_description(self) -> str:
        return "执行终端命令（如 npm install, python -m pytest, git status 等）。命令会在工作目录下执行。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令（如 'npm install' 或 'python -m pytest'）"},
                "timeout": {"type": "integer", "description": f"命令超时时间（秒），默认 {self.default_timeout} 秒", "default": self.default_timeout},
            },
            "required": ["command"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        command = parameters["command"]
        timeout = parameters.get("timeout", self.default_timeout)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            
            if result.returncode == 0:
                return f"命令执行成功:\n标准输出:\n{result.stdout}\n标准错误:\n{result.stderr}"
            else:
                return f"命令执行失败（返回码: {result.returncode}）:\n标准输出:\n{result.stdout}\n标准错误:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return f"命令执行超时（超过 {timeout} 秒）"
        except Exception as e:
            return f"执行命令失败: {e}"

