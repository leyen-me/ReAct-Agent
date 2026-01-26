# -*- coding: utf-8 -*-
"""系统命令工具测试"""

import sys
import tempfile
import platform
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.system_tools import (
    ShellTool,
    TerminalTool,
    EnvTool,
    SleepTool,
)


def setup_test_env():
    """设置测试环境"""
    test_dir = tempfile.mkdtemp(prefix="test_tools_")
    work_dir = Path(test_dir)
    return work_dir


def cleanup_test_env(work_dir: Path):
    """清理测试环境"""
    import shutil
    if work_dir.exists():
        shutil.rmtree(work_dir)


def test_shell():
    """测试 ShellTool"""
    print("\n=== 测试 ShellTool ===")
    work_dir = setup_test_env()
    try:
        tool = ShellTool(work_dir)
        
        # 测试1: 基本命令
        print("\n测试1: 基本命令")
        if platform.system() != "Windows":
            result = tool.run({"cmd": "echo 'Hello from shell'"})
        else:
            result = tool.run({"cmd": "echo Hello from shell"})
        print(result)
        
        # 测试2: 列出文件
        print("\n测试2: 列出文件")
        (work_dir / "test.txt").write_text("test")
        if platform.system() != "Windows":
            result = tool.run({"cmd": "ls -la"})
        else:
            result = tool.run({"cmd": "dir"})
        print(result)
        
        # 测试3: 带会话ID
        print("\n测试3: 带会话ID")
        result = tool.run({
            "cmd": "pwd" if platform.system() != "Windows" else "cd",
            "session_id": "test-session-123"
        })
        print(result)
        
        print("\n✓ ShellTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_terminal():
    """测试 TerminalTool"""
    print("\n=== 测试 TerminalTool ===")
    work_dir = setup_test_env()
    try:
        tool = TerminalTool(work_dir)
        
        # 测试1: 允许的命令 - ls
        print("\n测试1: ls 命令")
        if platform.system() != "Windows":
            result = tool.run({"cmd": "ls"})
            print(result)
        else:
            print("跳过（Windows 不支持 ls）")
        
        # 测试2: 允许的命令 - cat
        print("\n测试2: cat 命令")
        (work_dir / "test.txt").write_text("Test content\nLine 2")
        if platform.system() != "Windows":
            result = tool.run({"cmd": "cat test.txt"})
            print(result)
        else:
            print("跳过（Windows 不支持 cat）")
        
        # 测试3: 不允许的命令
        print("\n测试3: 不允许的命令")
        result = tool.run({"cmd": "rm test.txt"})
        print(result)
        
        print("\n✓ TerminalTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_env():
    """测试 EnvTool"""
    print("\n=== 测试 EnvTool ===")
    work_dir = setup_test_env()
    try:
        tool = EnvTool(work_dir)
        
        # 测试1: 获取环境变量
        print("\n测试1: 获取环境变量 PATH")
        result = tool.run({"action": "get", "key": "PATH"})
        print(f"PATH 值（前100字符）: {result[:100]}...")
        
        # 测试2: 设置环境变量
        print("\n测试2: 设置环境变量")
        result = tool.run({
            "action": "set",
            "key": "TEST_VAR",
            "value": "test_value"
        })
        print(result)
        
        # 验证设置
        result = tool.run({"action": "get", "key": "TEST_VAR"})
        print(f"验证设置: {result}")
        
        # 测试3: 取消设置环境变量
        print("\n测试3: 取消设置环境变量")
        result = tool.run({"action": "unset", "key": "TEST_VAR"})
        print(result)
        
        # 验证取消设置
        result = tool.run({"action": "get", "key": "TEST_VAR"})
        print(f"验证取消设置: {result}")
        
        print("\n✓ EnvTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_sleep():
    """测试 SleepTool"""
    print("\n=== 测试 SleepTool ===")
    work_dir = setup_test_env()
    try:
        tool = SleepTool(work_dir)
        
        # 测试1: 暂停1秒
        print("\n测试1: 暂停1秒")
        import time
        start = time.time()
        result = tool.run({"seconds": 1})
        elapsed = time.time() - start
        print(f"结果: {result}")
        print(f"实际耗时: {elapsed:.2f} 秒")
        
        # 测试2: 暂停小数秒
        print("\n测试2: 暂停0.5秒")
        start = time.time()
        result = tool.run({"seconds": 0.5})
        elapsed = time.time() - start
        print(f"结果: {result}")
        print(f"实际耗时: {elapsed:.2f} 秒")
        
        print("\n✓ SleepTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


if __name__ == "__main__":
    print("=" * 60)
    print("系统命令工具测试")
    print("=" * 60)
    
    test_shell()
    test_terminal()
    test_env()
    test_sleep()
    
    print("\n" + "=" * 60)
    print("所有系统命令工具测试完成！")
    print("=" * 60)
