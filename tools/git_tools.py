# -*- coding: utf-8 -*-
"""Git 操作工具"""

import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
import json

from tools.base import Tool
from utils import normalize_path


class GitTool(Tool):
    """对仓库执行 Git 操作"""
    
    def _get_description(self) -> str:
        return "对仓库执行 Git 操作，如 clone、checkout、pull、commit、status、log 等。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Git 操作类型，如 'clone'、'pull'、'status'、'log' 等"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "操作参数列表"
                },
                "repo_path": {
                    "type": "string",
                    "description": "仓库路径，默认当前工作目录"
                },
                "remote": {
                    "type": "string",
                    "description": "远程仓库名称，如 'origin'"
                },
                "branch": {
                    "type": "string",
                    "description": "分支名称，如 'main'"
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒）"
                }
            },
            "required": ["action"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        action = parameters["action"]
        args = parameters.get("args", [])
        repo_path = parameters.get("repo_path")
        remote = parameters.get("remote")
        branch = parameters.get("branch")
        timeout = parameters.get("timeout", 30)
        
        # 确定工作目录
        if repo_path:
            try:
                work_dir = normalize_path(repo_path, self.work_dir)
            except ValueError as e:
                return f"路径错误: {e}"
        else:
            work_dir = self.work_dir
        
        # 构建 git 命令
        git_cmd = ["git", action]
        
        # 处理特殊操作
        if action == "clone":
            git_cmd.extend(args)
            if repo_path:
                git_cmd.append(str(work_dir))
        elif action == "pull":
            if remote:
                git_cmd.append(remote)
            if branch:
                git_cmd.append(branch)
            git_cmd.extend(args)
        elif action == "push":
            if remote:
                git_cmd.append(remote)
            if branch:
                git_cmd.append(branch)
            git_cmd.extend(args)
        elif action == "checkout":
            if branch:
                git_cmd.append(branch)
            git_cmd.extend(args)
        elif action == "commit":
            if "-m" not in args and "--message" not in args:
                git_cmd.append("-m")
                git_cmd.append("Auto commit")
            git_cmd.extend(args)
        else:
            git_cmd.extend(args)
        
        try:
            result = subprocess.run(
                git_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir) if action != "clone" else None
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
