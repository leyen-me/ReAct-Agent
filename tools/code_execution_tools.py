# -*- coding: utf-8 -*-
"""代码执行工具"""

import subprocess
import sys
import io
import contextlib
from pathlib import Path
from typing import Dict, Any, Optional
import json

from tools.base import Tool


class CodeInterpreterTool(Tool):
    """在受限的 Python 环境中执行代码"""
    
    def _get_description(self) -> str:
        return "在受限的 Python 环境中执行代码，支持读取/写入文件、绘图、数据分析等。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的 Python 代码"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 5"
                },
                "globals": {
                    "type": "object",
                    "description": "全局变量字典"
                },
                "locals": {
                    "type": "object",
                    "description": "局部变量字典"
                }
            },
            "required": ["code"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        code = parameters["code"]
        timeout = parameters.get("timeout", 5)
        globals_dict = parameters.get("globals", {})
        locals_dict = parameters.get("locals", {})
        
        # 准备执行环境
        exec_globals = {
            "__builtins__": __builtins__,
            "__name__": "__main__",
            "__file__": "<string>",
        }
        exec_globals.update(globals_dict)
        
        exec_locals = locals_dict.copy()
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        result = None
        exception = None
        
        try:
            with contextlib.redirect_stdout(stdout_capture), \
                 contextlib.redirect_stderr(stderr_capture):
                # 执行代码
                compiled_code = compile(code, "<string>", "exec")
                exec(compiled_code, exec_globals, exec_locals)
                
                # 尝试获取最后一个表达式的结果
                if code.strip().endswith(")"):
                    # 可能是函数调用，尝试评估
                    try:
                        result = eval(code.strip(), exec_globals, exec_locals)
                    except:
                        pass
        
        except Exception as e:
            exception = str(e)
        
        stdout_text = stdout_capture.getvalue()
        stderr_text = stderr_capture.getvalue()
        
        return json.dumps({
            "result": str(result) if result is not None else None,
            "stdout": stdout_text,
            "stderr": stderr_text,
            "exception": exception
        }, ensure_ascii=False)


class PythonTool(CodeInterpreterTool):
    """Python 代码执行工具（code_interpreter 的别名）"""
    
    def _get_description(self) -> str:
        return "执行 Python 代码（code_interpreter 的别名）。"


class RunTool(Tool):
    """在受控的沙箱环境中执行一段 Python 代码或脚本"""
    
    def _get_description(self) -> str:
        return "在受控的沙箱环境中执行一段 Python 代码或脚本，返回标准输出、错误信息和返回码。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的代码"
                },
                "cmd": {
                    "type": "string",
                    "description": "shell 命令（如果使用 shell 模式）"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）"
                },
                "env": {
                    "type": "object",
                    "description": "环境变量"
                },
                "cwd": {
                    "type": "string",
                    "description": "工作目录"
                }
            },
            "required": []
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        code = parameters.get("code")
        cmd = parameters.get("cmd")
        timeout = parameters.get("timeout", 30)
        env = parameters.get("env")
        cwd = parameters.get("cwd")
        
        if code:
            # 执行 Python 代码
            try:
                result = subprocess.run(
                    [sys.executable, "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    cwd=cwd if cwd else str(self.work_dir)
                )
                return json.dumps({
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }, ensure_ascii=False)
            except subprocess.TimeoutExpired:
                return json.dumps({
                    "stdout": "",
                    "stderr": f"执行超时（{timeout}秒）",
                    "returncode": -1
                }, ensure_ascii=False)
            except Exception as e:
                return json.dumps({
                    "stdout": "",
                    "stderr": str(e),
                    "returncode": -1
                }, ensure_ascii=False)
        elif cmd:
            # 执行 shell 命令
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=env,
                    cwd=cwd if cwd else str(self.work_dir)
                )
                return json.dumps({
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }, ensure_ascii=False)
            except subprocess.TimeoutExpired:
                return json.dumps({
                    "stdout": "",
                    "stderr": f"执行超时（{timeout}秒）",
                    "returncode": -1
                }, ensure_ascii=False)
            except Exception as e:
                return json.dumps({
                    "stdout": "",
                    "stderr": str(e),
                    "returncode": -1
                }, ensure_ascii=False)
        else:
            return json.dumps({
                "stdout": "",
                "stderr": "必须提供 code 或 cmd 参数",
                "returncode": -1
            }, ensure_ascii=False)


class ExecuteTool(RunTool):
    """执行工具（run 的别名）"""
    
    def _get_description(self) -> str:
        return "执行代码或命令（run 的别名）。"


class ExecTool(Tool):
    """执行命令工具（默认在当前工作目录下执行）"""
    
    def _get_description(self) -> str:
        return "与 run 类似，但默认在当前工作目录下执行，常用于一次性脚本。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的命令"
                },
                "input": {
                    "type": "string",
                    "description": "传递给 stdin 的输入"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）"
                }
            },
            "required": ["command"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        command = parameters["command"]
        input_text = parameters.get("input")
        timeout = parameters.get("timeout", 30)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=input_text,
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
                "stderr": f"执行超时（{timeout}秒）",
                "returncode": -1
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "stdout": "",
                "stderr": str(e),
                "returncode": -1
            }, ensure_ascii=False)
