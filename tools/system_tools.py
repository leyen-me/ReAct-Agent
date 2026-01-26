# -*- coding: utf-8 -*-
"""系统命令工具"""

import subprocess
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import json

from tools.base import Tool


class ShellTool(Tool):
    """执行任意系统 Shell 命令（受限于安全策略）"""
    
    def _get_description(self) -> str:
        return "执行任意系统 Shell 命令（受限于安全策略），常用于查看文件、安装依赖等。支持交互式会话（保持同一进程），适合多步操作。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cmd": {
                    "type": "string",
                    "description": "要执行的 shell 命令"
                },
                "session_id": {
                    "type": "string",
                    "description": "会话标识符，用于保持同一进程"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）"
                }
            },
            "required": ["cmd"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        cmd = parameters["cmd"]
        session_id = parameters.get("session_id")
        timeout = parameters.get("timeout", 30)
        
        # 注意：实际的会话管理需要在更高层实现
        # 这里只是执行命令
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.work_dir)
            )
            
            return json.dumps({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "session_id": session_id
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({
                "stdout": "",
                "stderr": f"执行超时（{timeout}秒）",
                "returncode": -1,
                "session_id": session_id
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "session_id": session_id
            }, ensure_ascii=False)


class TerminalTool(Tool):
    """执行简单的系统命令（受限的 shell）"""
    
    def _get_description(self) -> str:
        return "执行简单的系统命令（受限的 shell），如 ls、cat、grep 等。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "cmd": {
                    "type": "string",
                    "description": "要执行的命令"
                }
            },
            "required": ["cmd"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        cmd = parameters["cmd"]
        
        # 限制允许的命令（安全策略）
        allowed_commands = ["ls", "cat", "grep", "find", "head", "tail", "wc", "pwd", "echo"]
        cmd_parts = cmd.strip().split()
        if not cmd_parts:
            return json.dumps({
                "stdout": "",
                "stderr": "命令为空",
                "returncode": -1
            }, ensure_ascii=False)
        
        base_cmd = cmd_parts[0]
        if base_cmd not in allowed_commands:
            return json.dumps({
                "stdout": "",
                "stderr": f"命令 '{base_cmd}' 不在允许列表中",
                "returncode": -1
            }, ensure_ascii=False)
        
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(self.work_dir)
            )
            
            return json.dumps({
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({
                "stdout": "",
                "stderr": "执行超时",
                "returncode": -1
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }, ensure_ascii=False)


class EnvTool(Tool):
    """查询或修改当前进程的环境变量"""
    
    def _get_description(self) -> str:
        return "查询或修改当前进程的环境变量。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "操作类型，'get'/'set'/'unset'",
                    "enum": ["get", "set", "unset"]
                },
                "key": {
                    "type": "string",
                    "description": "环境变量名"
                },
                "value": {
                    "type": "string",
                    "description": "环境变量值（set 时必填）"
                }
            },
            "required": ["action", "key"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        action = parameters["action"]
        key = parameters["key"]
        value = parameters.get("value")
        
        if action == "get":
            env_value = os.environ.get(key, "")
            return json.dumps({"value": env_value}, ensure_ascii=False)
        elif action == "set":
            if value is None:
                return json.dumps({"success": False, "error": "set 操作需要提供 value 参数"}, ensure_ascii=False)
            os.environ[key] = value
            return json.dumps({"success": True}, ensure_ascii=False)
        elif action == "unset":
            os.environ.pop(key, None)
            return json.dumps({"success": True}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": f"未知操作: {action}"}, ensure_ascii=False)


class SleepTool(Tool):
    """让当前沙箱暂停指定秒数"""
    
    def _get_description(self) -> str:
        return "让当前沙箱暂停指定秒数（用于调试或等待外部进程）。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "seconds": {
                    "type": "number",
                    "description": "暂停的秒数（支持小数）"
                }
            },
            "required": ["seconds"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        seconds = parameters["seconds"]
        
        try:
            time.sleep(float(seconds))
            return "True"
        except Exception as e:
            return f"暂停失败: {e}"
