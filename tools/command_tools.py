# -*- coding: utf-8 -*-
"""命令执行工具"""

import subprocess
import os
import time
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
        return "执行终端命令（如 npm install, python -m pytest, git status 等）。命令会在工作目录下执行。对于长期运行的服务器命令（如 npm start），会自动在后台运行。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令（如 'npm install' 或 'python -m pytest'）"},
                "timeout": {"type": "integer", "description": f"命令超时时间（秒），默认 {self.default_timeout} 秒", "default": self.default_timeout},
                "background": {"type": "boolean", "description": "是否在后台运行（适用于长期运行的服务器命令，如 npm start）", "default": False},
            },
            "required": ["command"],
        }
    
    def _is_long_running_command(self, command: str) -> bool:
        """
        检测是否是长期运行的命令
        
        Args:
            command: 命令字符串
            
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
        
        command_lower = command.lower()
        return any(pattern in command_lower for pattern in long_running_patterns)
    
    def run(self, parameters: Dict[str, Any]) -> str:
        command = parameters["command"]
        timeout = parameters.get("timeout", self.default_timeout)
        background = parameters.get("background", False)
        
        # 设置环境变量，避免交互式提示
        # CI=true: npm/npx/yarn 等工具会检测此变量，自动回答 yes
        # DEBIAN_FRONTEND=noninteractive: apt-get 等包管理器
        env = os.environ.copy()
        env['CI'] = 'true'
        env['DEBIAN_FRONTEND'] = 'noninteractive'
        
        # 检测是否是长期运行的命令
        is_long_running = background or self._is_long_running_command(command)
        
        if is_long_running:
            # 长期运行的命令，在后台启动
            try:
                process = subprocess.Popen(
                    command,
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
                
                # 等待几秒，收集初始输出
                time.sleep(3)
                
                # 检查进程是否还在运行
                if process.poll() is None:
                    # 进程仍在运行，说明是长期进程
                    pid = process.pid
                    
                    output_parts = []
                    output_parts.append(f"进程已在后台启动（PID: {pid}）")
                    output_parts.append("服务正在运行中...")
                    output_parts.append(f"\n提示：要停止服务，可以使用命令 'kill {pid}' 或 'pkill -f \"{command}\"'")
                    
                    return "\n".join(output_parts)
                else:
                    # 进程已退出，返回结果
                    stdout, stderr = process.communicate()
                    if process.returncode == 0:
                        return f"命令执行成功:\n标准输出:\n{stdout}\n标准错误:\n{stderr}"
                    else:
                        return f"命令执行失败（返回码: {process.returncode}）:\n标准输出:\n{stdout}\n标准错误:\n{stderr}"
                        
            except Exception as e:
                return f"执行命令失败: {e}"
        else:
            # 普通命令，正常执行
            try:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(self.work_dir),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    encoding="utf-8",
                    errors="replace",
                    env=env,
                    # 通过 input 提供自动输入，回答所有可能的 yes/no 提示
                    # 提供多个 y 和回车，处理多个交互式提示
                    input="y\n" * 20,
                )
                
                if result.returncode == 0:
                    return f"命令执行成功:\n标准输出:\n{result.stdout}\n标准错误:\n{result.stderr}"
                else:
                    return f"命令执行失败（返回码: {result.returncode}）:\n标准输出:\n{result.stdout}\n标准错误:\n{result.stderr}"
            except subprocess.TimeoutExpired:
                return f"命令执行超时（超过 {timeout} 秒）"
            except Exception as e:
                return f"执行命令失败: {e}"

