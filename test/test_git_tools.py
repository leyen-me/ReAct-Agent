# -*- coding: utf-8 -*-
"""Git 操作工具测试"""

import sys
import tempfile
import subprocess
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.git_tools import GitTool


def setup_test_env():
    """设置测试环境"""
    test_dir = tempfile.mkdtemp(prefix="test_git_")
    work_dir = Path(test_dir)
    
    # 初始化 git 仓库
    try:
        subprocess.run(
            ["git", "init"],
            cwd=str(work_dir),
            capture_output=True,
            check=True
        )
        
        # 创建初始文件
        (work_dir / "README.md").write_text("# Test Git Repo\n")
        
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=str(work_dir),
            capture_output=True,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=str(work_dir),
            capture_output=True,
            check=True
        )
        
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=str(work_dir),
            capture_output=True,
            check=True
        )
        
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=str(work_dir),
            capture_output=True,
            check=True
        )
    except Exception as e:
        print(f"警告: Git 初始化失败: {e}")
    
    return work_dir


def cleanup_test_env(work_dir: Path):
    """清理测试环境"""
    import shutil
    if work_dir.exists():
        shutil.rmtree(work_dir)


def test_git_status():
    """测试 git status"""
    print("\n=== 测试 Git Status ===")
    work_dir = setup_test_env()
    try:
        tool = GitTool(work_dir)
        
        # 创建新文件
        (work_dir / "new_file.txt").write_text("New file")
        
        result = tool.run({"action": "status"})
        print(result)
        
        print("\n✓ Git Status 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_git_add():
    """测试 git add"""
    print("\n=== 测试 Git Add ===")
    work_dir = setup_test_env()
    try:
        tool = GitTool(work_dir)
        
        # 创建新文件
        (work_dir / "new_file.txt").write_text("New file")
        
        result = tool.run({"action": "add", "args": ["new_file.txt"]})
        print(result)
        
        # 检查状态
        result = tool.run({"action": "status"})
        print("\n添加后的状态:")
        print(result)
        
        print("\n✓ Git Add 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_git_commit():
    """测试 git commit"""
    print("\n=== 测试 Git Commit ===")
    work_dir = setup_test_env()
    try:
        tool = GitTool(work_dir)
        
        # 创建并添加文件
        (work_dir / "commit_test.txt").write_text("Test commit")
        tool.run({"action": "add", "args": ["commit_test.txt"]})
        
        result = tool.run({
            "action": "commit",
            "args": ["-m", "Test commit message"]
        })
        print(result)
        
        # 检查日志
        result = tool.run({"action": "log", "args": ["--oneline", "-1"]})
        print("\n最新提交:")
        print(result)
        
        print("\n✓ Git Commit 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_git_log():
    """测试 git log"""
    print("\n=== 测试 Git Log ===")
    work_dir = setup_test_env()
    try:
        tool = GitTool(work_dir)
        
        result = tool.run({"action": "log", "args": ["--oneline"]})
        print(result)
        
        print("\n✓ Git Log 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_git_branch():
    """测试 git branch"""
    print("\n=== 测试 Git Branch ===")
    work_dir = setup_test_env()
    try:
        tool = GitTool(work_dir)
        
        # 列出分支
        result = tool.run({"action": "branch"})
        print("当前分支:")
        print(result)
        
        # 创建新分支
        result = tool.run({"action": "checkout", "args": ["-b", "test-branch"]})
        print("\n创建分支:")
        print(result)
        
        # 列出所有分支
        result = tool.run({"action": "branch"})
        print("\n所有分支:")
        print(result)
        
        print("\n✓ Git Branch 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_git_diff():
    """测试 git diff"""
    print("\n=== 测试 Git Diff ===")
    work_dir = setup_test_env()
    try:
        tool = GitTool(work_dir)
        
        # 修改文件
        readme = work_dir / "README.md"
        readme.write_text("# Test Git Repo\n\nModified content")
        
        result = tool.run({"action": "diff"})
        print(result)
        
        print("\n✓ Git Diff 测试完成")
    finally:
        cleanup_test_env(work_dir)


if __name__ == "__main__":
    print("=" * 60)
    print("Git 操作工具测试")
    print("=" * 60)
    print("\n注意: 这些测试需要系统安装 Git")
    print("=" * 60)
    
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except:
        print("\n警告: 未检测到 Git，部分测试可能失败")
    
    test_git_status()
    test_git_add()
    test_git_commit()
    test_git_log()
    test_git_branch()
    test_git_diff()
    
    print("\n" + "=" * 60)
    print("所有 Git 操作工具测试完成！")
    print("=" * 60)
