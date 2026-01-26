# -*- coding: utf-8 -*-
"""Git 版本控制工具"""

import subprocess
import os
from pathlib import Path
from typing import Dict, Any, Optional

from tools.base import Tool


class GitStatusTool(Tool):
    """查看 Git 仓库状态"""
    
    def _get_description(self) -> str:
        return "查看 Git 仓库的状态，包括已修改、已暂存、未跟踪的文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Git 仓库路径（可选，默认为工作目录）", "default": ""},
            },
            "required": [],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        if path:
            is_valid, error = self.validate_path(path)
            if not is_valid:
                return f"路径错误: {error}"
            git_dir = Path(path)
        else:
            git_dir = self.work_dir
        
        # 检查是否是 Git 仓库
        if not (git_dir / ".git").exists() and not self._is_git_repo(git_dir):
            return f"错误: {git_dir} 不是 Git 仓库"
        
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            
            if result.returncode != 0:
                return f"执行 git status 失败:\n{result.stderr}"
            
            if not result.stdout.strip():
                return "工作目录干净，没有更改"
            
            # 获取详细状态
            detailed_result = subprocess.run(
                ["git", "status"],
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            
            return f"Git 状态:\n{detailed_result.stdout}"
        except subprocess.TimeoutExpired:
            return "执行 git status 超时"
        except Exception as e:
            return f"执行 git status 失败: {e}"
    
    def _is_git_repo(self, path: Path) -> bool:
        """检查路径是否是 Git 仓库"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class GitDiffTool(Tool):
    """查看 Git diff"""
    
    def _get_description(self) -> str:
        return "查看 Git 的差异（diff），可以查看工作区、暂存区或提交之间的差异"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Git 仓库路径（可选，默认为工作目录）", "default": ""},
                "file": {"type": "string", "description": "特定文件路径（可选，查看单个文件的 diff）", "default": ""},
                "staged": {"type": "boolean", "description": "是否查看暂存区的 diff（默认 false，查看工作区）", "default": False},
                "commit1": {"type": "string", "description": "第一个提交哈希或分支名（可选，用于比较两个提交）", "default": ""},
                "commit2": {"type": "string", "description": "第二个提交哈希或分支名（可选，与 commit1 一起使用）", "default": ""},
            },
            "required": [],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        if path:
            is_valid, error = self.validate_path(path)
            if not is_valid:
                return f"路径错误: {error}"
            git_dir = Path(path)
        else:
            git_dir = self.work_dir
        
        # 检查是否是 Git 仓库
        if not (git_dir / ".git").exists() and not self._is_git_repo(git_dir):
            return f"错误: {git_dir} 不是 Git 仓库"
        
        file_path = parameters.get("file", "")
        staged = parameters.get("staged", False)
        commit1 = parameters.get("commit1", "")
        commit2 = parameters.get("commit2", "")
        
        try:
            cmd = ["git", "diff"]
            
            # 如果指定了文件，验证路径
            if file_path:
                if not os.path.isabs(file_path):
                    file_path = str(git_dir / file_path)
                is_valid, error = self.validate_path(file_path)
                if not is_valid:
                    return f"文件路径错误: {error}"
                # 转换为相对于 git_dir 的路径
                rel_path = os.path.relpath(file_path, git_dir)
                cmd.append(rel_path)
            
            # 查看暂存区
            if staged:
                cmd.append("--staged")
            
            # 比较两个提交
            if commit1 and commit2:
                cmd = ["git", "diff", commit1, commit2]
                if file_path:
                    rel_path = os.path.relpath(file_path, git_dir) if os.path.isabs(file_path) else file_path
                    cmd.append("--")
                    cmd.append(rel_path)
            elif commit1:
                cmd = ["git", "diff", commit1]
                if file_path:
                    rel_path = os.path.relpath(file_path, git_dir) if os.path.isabs(file_path) else file_path
                    cmd.append("--")
                    cmd.append(rel_path)
            
            result = subprocess.run(
                cmd,
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace"
            )
            
            if result.returncode != 0:
                return f"执行 git diff 失败:\n{result.stderr}"
            
            if not result.stdout.strip():
                return "没有差异"
            
            return f"Git Diff:\n{result.stdout}"
        except subprocess.TimeoutExpired:
            return "执行 git diff 超时"
        except Exception as e:
            return f"执行 git diff 失败: {e}"
    
    def _is_git_repo(self, path: Path) -> bool:
        """检查路径是否是 Git 仓库"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class GitCommitTool(Tool):
    """提交代码到 Git"""
    
    def _get_description(self) -> str:
        return "提交代码到 Git 仓库。可以提交所有更改或指定文件，并添加提交消息"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Git 仓库路径（可选，默认为工作目录）", "default": ""},
                "message": {"type": "string", "description": "提交消息"},
                "files": {"type": "array", "items": {"type": "string"}, "description": "要提交的文件列表（可选，默认提交所有更改）", "default": []},
                "all": {"type": "boolean", "description": "是否提交所有更改（包括未跟踪的文件，使用 git add -A）", "default": False},
            },
            "required": ["message"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        if path:
            is_valid, error = self.validate_path(path)
            if not is_valid:
                return f"路径错误: {error}"
            git_dir = Path(path)
        else:
            git_dir = self.work_dir
        
        # 检查是否是 Git 仓库
        if not (git_dir / ".git").exists() and not self._is_git_repo(git_dir):
            return f"错误: {git_dir} 不是 Git 仓库"
        
        message = parameters["message"]
        files = parameters.get("files", [])
        all_files = parameters.get("all", False)
        
        try:
            # 添加文件到暂存区
            if all_files:
                add_result = subprocess.run(
                    ["git", "add", "-A"],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )
                if add_result.returncode != 0:
                    return f"执行 git add -A 失败:\n{add_result.stderr}"
            elif files:
                for file in files:
                    if not os.path.isabs(file):
                        file = str(git_dir / file)
                    is_valid, error = self.validate_path(file)
                    if not is_valid:
                        return f"文件路径错误: {file} - {error}"
                    rel_path = os.path.relpath(file, git_dir)
                    add_result = subprocess.run(
                        ["git", "add", rel_path],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                        encoding="utf-8",
                        errors="replace"
                    )
                    if add_result.returncode != 0:
                        return f"执行 git add {rel_path} 失败:\n{add_result.stderr}"
            
            # 检查是否有文件被暂存
            status_result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=10
            )
            if status_result.returncode == 0:
                return "没有文件被暂存，无法提交"
            
            # 执行提交
            commit_result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
                errors="replace"
            )
            
            if commit_result.returncode != 0:
                return f"执行 git commit 失败:\n{commit_result.stderr}"
            
            # 获取提交信息
            log_result = subprocess.run(
                ["git", "log", "-1", "--oneline"],
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=10,
                encoding="utf-8",
                errors="replace"
            )
            
            commit_info = log_result.stdout.strip() if log_result.returncode == 0 else "提交成功"
            return f"提交成功:\n{commit_info}"
        except subprocess.TimeoutExpired:
            return "执行 git commit 超时"
        except Exception as e:
            return f"执行 git commit 失败: {e}"
    
    def _is_git_repo(self, path: Path) -> bool:
        """检查路径是否是 Git 仓库"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class GitBranchTool(Tool):
    """管理 Git 分支"""
    
    def _get_description(self) -> str:
        return "管理 Git 分支：创建新分支、切换分支、列出分支、删除分支"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Git 仓库路径（可选，默认为工作目录）", "default": ""},
                "action": {"type": "string", "description": "操作类型：'list'（列出分支）、'create'（创建分支）、'switch'（切换分支）、'delete'（删除分支）", "enum": ["list", "create", "switch", "delete"]},
                "branch_name": {"type": "string", "description": "分支名称（create/switch/delete 操作需要）", "default": ""},
                "from_branch": {"type": "string", "description": "从哪个分支创建（可选，默认从当前分支）", "default": ""},
            },
            "required": ["action"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        if path:
            is_valid, error = self.validate_path(path)
            if not is_valid:
                return f"路径错误: {error}"
            git_dir = Path(path)
        else:
            git_dir = self.work_dir
        
        # 检查是否是 Git 仓库
        if not (git_dir / ".git").exists() and not self._is_git_repo(git_dir):
            return f"错误: {git_dir} 不是 Git 仓库"
        
        action = parameters["action"]
        branch_name = parameters.get("branch_name", "")
        
        try:
            if action == "list":
                # 列出所有分支
                result = subprocess.run(
                    ["git", "branch", "-a"],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )
                
                if result.returncode != 0:
                    return f"执行 git branch 失败:\n{result.stderr}"
                
                # 获取当前分支
                current_result = subprocess.run(
                    ["git", "branch", "--show-current"],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding="utf-8",
                    errors="replace"
                )
                current_branch = current_result.stdout.strip() if current_result.returncode == 0 else "未知"
                
                return f"当前分支: {current_branch}\n\n所有分支:\n{result.stdout}"
            
            elif action == "create":
                if not branch_name:
                    return "错误: 创建分支需要指定 branch_name"
                
                from_branch = parameters.get("from_branch", "")
                if from_branch:
                    result = subprocess.run(
                        ["git", "checkout", "-b", branch_name, from_branch],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                        encoding="utf-8",
                        errors="replace"
                    )
                else:
                    result = subprocess.run(
                        ["git", "checkout", "-b", branch_name],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                        encoding="utf-8",
                        errors="replace"
                    )
                
                if result.returncode != 0:
                    return f"创建分支失败:\n{result.stderr}"
                
                return f"成功创建并切换到分支: {branch_name}"
            
            elif action == "switch":
                if not branch_name:
                    return "错误: 切换分支需要指定 branch_name"
                
                result = subprocess.run(
                    ["git", "checkout", branch_name],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )
                
                if result.returncode != 0:
                    return f"切换分支失败:\n{result.stderr}"
                
                return f"成功切换到分支: {branch_name}"
            
            elif action == "delete":
                if not branch_name:
                    return "错误: 删除分支需要指定 branch_name"
                
                result = subprocess.run(
                    ["git", "branch", "-d", branch_name],
                    cwd=str(git_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    encoding="utf-8",
                    errors="replace"
                )
                
                if result.returncode != 0:
                    # 尝试强制删除
                    force_result = subprocess.run(
                        ["git", "branch", "-D", branch_name],
                        cwd=str(git_dir),
                        capture_output=True,
                        text=True,
                        timeout=30,
                        encoding="utf-8",
                        errors="replace"
                    )
                    if force_result.returncode != 0:
                        return f"删除分支失败:\n{force_result.stderr}"
                    return f"成功强制删除分支: {branch_name}"
                
                return f"成功删除分支: {branch_name}"
            
            else:
                return f"未知操作: {action}"
        except subprocess.TimeoutExpired:
            return "执行 git branch 操作超时"
        except Exception as e:
            return f"执行 git branch 操作失败: {e}"
    
    def _is_git_repo(self, path: Path) -> bool:
        """检查路径是否是 Git 仓库"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False


class GitLogTool(Tool):
    """查看 Git 提交历史"""
    
    def _get_description(self) -> str:
        return "查看 Git 提交历史，可以查看指定分支、文件或提交范围的提交记录"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Git 仓库路径（可选，默认为工作目录）", "default": ""},
                "limit": {"type": "integer", "description": "显示的提交数量（默认 10）", "default": 10},
                "branch": {"type": "string", "description": "分支名称（可选，默认当前分支）", "default": ""},
                "file": {"type": "string", "description": "文件路径（可选，查看特定文件的提交历史）", "default": ""},
                "since": {"type": "string", "description": "起始日期（可选，格式：YYYY-MM-DD 或 '1 week ago'）", "default": ""},
                "until": {"type": "string", "description": "结束日期（可选，格式：YYYY-MM-DD）", "default": ""},
                "author": {"type": "string", "description": "作者名称（可选，过滤特定作者的提交）", "default": ""},
            },
            "required": [],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters.get("path", "")
        if path:
            is_valid, error = self.validate_path(path)
            if not is_valid:
                return f"路径错误: {error}"
            git_dir = Path(path)
        else:
            git_dir = self.work_dir
        
        # 检查是否是 Git 仓库
        if not (git_dir / ".git").exists() and not self._is_git_repo(git_dir):
            return f"错误: {git_dir} 不是 Git 仓库"
        
        limit = parameters.get("limit", 10)
        branch = parameters.get("branch", "")
        file_path = parameters.get("file", "")
        since = parameters.get("since", "")
        until = parameters.get("until", "")
        author = parameters.get("author", "")
        
        try:
            cmd = ["git", "log", f"-{limit}", "--pretty=format:%h - %an, %ar : %s", "--date=relative"]
            
            if branch:
                cmd.append(branch)
            
            if file_path:
                if not os.path.isabs(file_path):
                    file_path = str(git_dir / file_path)
                is_valid, error = self.validate_path(file_path)
                if not is_valid:
                    return f"文件路径错误: {error}"
                rel_path = os.path.relpath(file_path, git_dir)
                cmd.append("--")
                cmd.append(rel_path)
            
            if since:
                cmd.extend(["--since", since])
            
            if until:
                cmd.extend(["--until", until])
            
            if author:
                cmd.extend(["--author", author])
            
            result = subprocess.run(
                cmd,
                cwd=str(git_dir),
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace"
            )
            
            if result.returncode != 0:
                return f"执行 git log 失败:\n{result.stderr}"
            
            if not result.stdout.strip():
                return "没有找到提交记录"
            
            return f"Git 提交历史:\n{result.stdout}"
        except subprocess.TimeoutExpired:
            return "执行 git log 超时"
        except Exception as e:
            return f"执行 git log 失败: {e}"
    
    def _is_git_repo(self, path: Path) -> bool:
        """检查路径是否是 Git 仓库"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False

