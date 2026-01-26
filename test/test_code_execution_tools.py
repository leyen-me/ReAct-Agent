# -*- coding: utf-8 -*-
"""代码执行工具测试"""

import sys
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.code_execution_tools import (
    CodeInterpreterTool,
    PythonTool,
    RunTool,
    ExecuteTool,
    ExecTool,
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


def test_code_interpreter():
    """测试 CodeInterpreterTool"""
    print("\n=== 测试 CodeInterpreterTool ===")
    work_dir = setup_test_env()
    try:
        tool = CodeInterpreterTool(work_dir)
        
        # 测试1: 简单计算
        print("\n测试1: 简单计算")
        result = tool.run({"code": "result = 2 + 3\nprint(result)"})
        print(result)
        
        # 测试2: 列表操作
        print("\n测试2: 列表操作")
        result = tool.run({"code": "numbers = [1, 2, 3, 4, 5]\nprint(sum(numbers))"})
        print(result)
        
        # 测试3: 文件操作
        print("\n测试3: 文件操作")
        result = tool.run({
            "code": """
import os
test_file = 'test_output.txt'
with open(test_file, 'w') as f:
    f.write('Hello from code interpreter')
print(f'File written: {os.path.exists(test_file)}')
"""
        })
        print(result)
        
        print("\n✓ CodeInterpreterTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_python():
    """测试 PythonTool"""
    print("\n=== 测试 PythonTool ===")
    work_dir = setup_test_env()
    try:
        tool = PythonTool(work_dir)
        
        # 测试1: 基本执行
        print("\n测试1: 基本执行")
        result = tool.run({"code": "print('Hello from Python tool')"})
        print(result)
        
        print("\n✓ PythonTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_run():
    """测试 RunTool"""
    print("\n=== 测试 RunTool ===")
    work_dir = setup_test_env()
    try:
        tool = RunTool(work_dir)
        
        # 测试1: Python 代码执行
        print("\n测试1: Python 代码执行")
        result = tool.run({
            "code": "import sys\nprint('Python version:', sys.version.split()[0])"
        })
        print(result)
        
        # 测试2: Shell 命令执行
        print("\n测试2: Shell 命令执行")
        import platform
        if platform.system() != "Windows":
            result = tool.run({"cmd": "echo 'Hello from shell'"})
            print(result)
        else:
            result = tool.run({"cmd": "echo Hello from shell"})
            print(result)
        
        # 测试3: 带超时
        print("\n测试3: 带超时设置")
        result = tool.run({
            "code": "import time\ntime.sleep(0.1)\nprint('Done')",
            "timeout": 5
        })
        print(result)
        
        print("\n✓ RunTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_execute():
    """测试 ExecuteTool"""
    print("\n=== 测试 ExecuteTool ===")
    work_dir = setup_test_env()
    try:
        tool = ExecuteTool(work_dir)
        
        # 测试1: 基本执行
        print("\n测试1: 基本执行")
        result = tool.run({"code": "print('Hello from Execute tool')"})
        print(result)
        
        print("\n✓ ExecuteTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_exec():
    """测试 ExecTool"""
    print("\n=== 测试 ExecTool ===")
    work_dir = setup_test_env()
    try:
        tool = ExecTool(work_dir)
        
        # 测试1: 基本命令
        print("\n测试1: 基本命令")
        import platform
        if platform.system() != "Windows":
            result = tool.run({"command": "pwd"})
        else:
            result = tool.run({"command": "cd"})
        print(result)
        
        # 测试2: 带输入
        print("\n测试2: 带输入的命令")
        if platform.system() != "Windows":
            result = tool.run({
                "command": "cat",
                "input": "Test input\nLine 2"
            })
            print(result)
        
        # 测试3: 超时设置
        print("\n测试3: 超时设置")
        result = tool.run({
            "command": "echo 'Quick command'",
            "timeout": 5
        })
        print(result)
        
        print("\n✓ ExecTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


if __name__ == "__main__":
    print("=" * 60)
    print("代码执行工具测试")
    print("=" * 60)
    
    test_code_interpreter()
    test_python()
    test_run()
    test_execute()
    test_exec()
    
    print("\n" + "=" * 60)
    print("所有代码执行工具测试完成！")
    print("=" * 60)
