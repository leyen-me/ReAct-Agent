# -*- coding: utf-8 -*-
"""命令执行工具"""

import subprocess
import os
import time
import logging
from pathlib import Path
from typing import Dict, Any

from tools.base import Tool

logger = logging.getLogger(__name__)


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
                
                # 等待几秒，收集初始输出，期间检查中断
                wait_time = 3.0
                check_interval = 0.5  # 每0.5秒检查一次
                elapsed = 0.0
                while elapsed < wait_time:
                    if self.should_stop():
                        # 用户中断，终止进程
                        logger.info(f"检测到中断，正在终止命令进程: {command}")
                        try:
                            process.terminate()
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        return "命令执行被用户中断"
                    time.sleep(check_interval)
                    elapsed += check_interval
                
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
            # 普通命令，使用 Popen 以便能够中断
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
                
                # 轮询检查进程状态和中断标志
                check_interval = 0.5  # 每0.5秒检查一次
                start_time = time.time()
                
                while True:
                    # 检查是否超时
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        process.kill()
                        return f"命令执行超时（超过 {timeout} 秒）"
                    
                    # 检查是否应该停止
                    if self.should_stop():
                        # 用户中断，终止进程
                        logger.info(f"检测到中断，正在终止命令进程: {command}")
                        try:
                            process.terminate()
                            stdout, stderr = process.communicate(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            stdout, stderr = process.communicate()
                        return "命令执行被用户中断"
                    
                    # 检查进程是否完成
                    returncode = process.poll()
                    if returncode is not None:
                        # 进程已完成
                        stdout, stderr = process.communicate()
                        if returncode == 0:
                            return f"命令执行成功:\n标准输出:\n{stdout}\n标准错误:\n{stderr}"
                        else:
                            return f"命令执行失败（返回码: {returncode}）:\n标准输出:\n{stdout}\n标准错误:\n{stderr}"
                    
                    # 等待一段时间后再次检查
                    time.sleep(check_interval)
                    
            except Exception as e:
                return f"执行命令失败: {e}"

