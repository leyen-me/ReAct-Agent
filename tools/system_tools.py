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
        return "执行任意系统 Shell 命令（受限于安全策略），常用于查看文件、安装依赖等。支持交互式会话（保持同一进程），适合多步操作。对于长期运行的服务器命令（如 npm start），会自动在后台运行。"
    
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
                    "description": f"超时时间（秒），默认 {self.default_timeout} 秒",
                    "default": self.default_timeout
                },
                "background": {
                    "type": "boolean",
                    "description": "是否在后台运行（适用于长期运行的服务器命令，如 npm start）",
                    "default": False
                }
            },
            "required": ["cmd"]
        }
    
    def _is_long_running_command(self, cmd: str) -> bool:
        """
        检测是否是长期运行的命令
        
        Args:
            cmd: 命令字符串
            
        Returns:
            是否是长期运行的命令
        """
        long_running_patterns = [
            'npm start',
            'npm run dev',
            'npm run serve',
            'yarn start',
            'yarn dev',
            'python -m http.server',
            'python -m SimpleHTTPServer',
            'node server.js',
            'node app.js',
            'python app.py',
            'python manage.py runserver',
            'rails server',
            'rails s',
            'php -S',
            'java -jar',
            'docker-compose up',
            'docker run',
        ]
        
        cmd_lower = cmd.lower()
        return any(pattern in cmd_lower for pattern in long_running_patterns)
    
    def run(self, parameters: Dict[str, Any]) -> str:
        cmd = parameters["cmd"]
        session_id = parameters.get("session_id")
        timeout = parameters.get("timeout", self.default_timeout)
        background = parameters.get("background", False)
        
        # 设置环境变量，避免交互式提示
        env = os.environ.copy()
        env['CI'] = 'true'
        env['DEBIAN_FRONTEND'] = 'noninteractive'
        
        # 检测是否是长期运行的命令
        is_long_running = background or self._is_long_running_command(cmd)
        
        if is_long_running:
            # 长期运行的命令，在后台启动
            try:
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=str(self.work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    stdin=subprocess.PIPE,
                )
                
                # 等待几秒，收集初始输出，期间检查中断
                wait_time = 3.0
                check_interval = 0.5
                elapsed = 0.0
                while elapsed < wait_time:
                    if self.should_stop():
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"检测到中断，正在终止命令进程: {cmd}")
                        try:
                            process.terminate()
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        return json.dumps({
                            "stdout": "",
                            "stderr": "命令执行被用户中断",
                            "returncode": -1,
                            "session_id": session_id
                        }, ensure_ascii=False)
                    time.sleep(check_interval)
                    elapsed += check_interval
                
                # 检查进程是否还在运行
                if process.poll() is None:
                    # 进程仍在运行，说明是长期进程
                    pid = process.pid
                    return json.dumps({
                        "stdout": f"进程已在后台启动（PID: {pid}）\n服务正在运行中...\n提示：要停止服务，可以使用命令 'kill {pid}' 或 'pkill -f \"{cmd}\"'",
                        "stderr": "",
                        "returncode": 0,
                        "session_id": session_id
                    }, ensure_ascii=False)
                else:
                    # 进程已退出，返回结果
                    stdout, stderr = process.communicate()
                    return json.dumps({
                        "stdout": stdout,
                        "stderr": stderr,
                        "returncode": process.returncode,
                        "session_id": session_id
                    }, ensure_ascii=False)
                        
            except Exception as e:
                return json.dumps({
                    "stdout": "",
                    "stderr": f"执行命令失败: {e}",
                    "returncode": -1,
                    "session_id": session_id
                }, ensure_ascii=False)
        else:
            # 普通命令，使用 Popen 以便能够中断
            try:
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=str(self.work_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    stdin=subprocess.PIPE,
                )
                
                # 轮询检查进程状态和中断标志
                check_interval = 0.5
                start_time = time.time()
                
                while True:
                    # 检查是否超时
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        process.kill()
                        return json.dumps({
                            "stdout": "",
                            "stderr": f"命令执行超时（超过 {timeout} 秒）",
                            "returncode": -1,
                            "session_id": session_id
                        }, ensure_ascii=False)
                    
                    # 检查是否应该停止
                    if self.should_stop():
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"检测到中断，正在终止命令进程: {cmd}")
                        try:
                            process.terminate()
                            stdout, stderr = process.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            stdout, stderr = process.communicate()
                        return json.dumps({
                            "stdout": stdout,
                            "stderr": stderr + "\n命令执行被用户中断",
                            "returncode": -1,
                            "session_id": session_id
                        }, ensure_ascii=False)
                    
                    # 检查进程是否完成
                    returncode = process.poll()
                    if returncode is not None:
                        # 进程已完成
                        stdout, stderr = process.communicate()
                        return json.dumps({
                            "stdout": stdout,
                            "stderr": stderr,
                            "returncode": returncode,
                            "session_id": session_id
                        }, ensure_ascii=False)
                    
                    # 等待一段时间后再次检查
                    time.sleep(check_interval)
                    
            except Exception as e:
                return json.dumps({
                    "stdout": "",
                    "stderr": f"执行命令失败: {e}",
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
