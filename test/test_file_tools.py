# -*- coding: utf-8 -*-
"""文件操作工具测试"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.file_tools import (
    PrintTreeTool,
    ListFilesTool,
    FileSearchTool,
    OpenFileTool,
    ReadFileTool,
    WriteFileTool,
    DiffTool,
    ChecksumTool,
)


def setup_test_env():
    """设置测试环境"""
    test_dir = tempfile.mkdtemp(prefix="test_tools_")
    work_dir = Path(test_dir)
    
    # 创建测试文件结构
    (work_dir / "test_file.txt").write_text("Hello, World!\nLine 2\nLine 3")
    (work_dir / "test_file2.txt").write_text("Another file\nWith content")
    (work_dir / "subdir").mkdir()
    (work_dir / "subdir" / "nested.txt").write_text("Nested file content")
    (work_dir / "README.md").write_text("# Test Project\n\nThis is a test.")
    
    return work_dir


def cleanup_test_env(work_dir: Path):
    """清理测试环境"""
    if work_dir.exists():
        shutil.rmtree(work_dir)


def test_print_tree():
    """测试 PrintTreeTool"""
    print("\n=== 测试 PrintTreeTool ===")
    work_dir = setup_test_env()
    try:
        tool = PrintTreeTool(work_dir)
        
        # 测试1: 基本打印
        print("\n测试1: 基本打印")
        result = tool.run({"path": "."})
        print(result)
        
        # 测试2: 限制深度
        print("\n测试2: 限制深度为1")
        result = tool.run({"path": ".", "depth": 1})
        print(result)
        
        # 测试3: 忽略模式
        print("\n测试3: 忽略 .txt 文件")
        result = tool.run({"path": ".", "ignore": ["*.txt"]})
        print(result)
        
        print("\n✓ PrintTreeTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_list_files():
    """测试 ListFilesTool"""
    print("\n=== 测试 ListFilesTool ===")
    work_dir = setup_test_env()
    try:
        tool = ListFilesTool(work_dir)
        
        # 测试1: 列出当前目录文件
        print("\n测试1: 列出当前目录文件")
        result = tool.run({"path": "."})
        print(result)
        
        # 测试2: 递归列出
        print("\n测试2: 递归列出所有文件")
        result = tool.run({"path": ".", "recursive": True})
        print(result)
        
        # 测试3: 使用模式匹配
        print("\n测试3: 只列出 .txt 文件")
        result = tool.run({"path": ".", "pattern": "*.txt", "recursive": True})
        print(result)
        
        print("\n✓ ListFilesTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_search():
    """测试 FileSearchTool"""
    print("\n=== 测试 FileSearchTool ===")
    work_dir = setup_test_env()
    try:
        tool = FileSearchTool(work_dir)
        
        # 测试1: 基本搜索
        print("\n测试1: 搜索 'Hello'")
        result = tool.run({"query": "Hello"})
        print(result)
        
        # 测试2: 正则表达式搜索
        print("\n测试2: 正则表达式搜索 'Line \\d'")
        result = tool.run({"query": "Line \\d", "regex": True})
        print(result)
        
        # 测试3: 限制结果数
        print("\n测试3: 限制结果数为2")
        result = tool.run({"query": "Line", "max_results": 2})
        print(result)
        
        print("\n✓ FileSearchTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_open_file():
    """测试 OpenFileTool"""
    print("\n=== 测试 OpenFileTool ===")
    work_dir = setup_test_env()
    try:
        tool = OpenFileTool(work_dir)
        
        # 测试1: 读取整个文件
        print("\n测试1: 读取整个文件")
        result = tool.run({"path": "test_file.txt"})
        print(result)
        
        # 测试2: 读取指定行范围
        print("\n测试2: 读取第1-2行")
        result = tool.run({"path": "test_file.txt", "line_start": 1, "line_end": 2})
        print(result)
        
        print("\n✓ OpenFileTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_read_file():
    """测试 ReadFileTool"""
    print("\n=== 测试 ReadFileTool ===")
    work_dir = setup_test_env()
    try:
        tool = ReadFileTool(work_dir)
        
        # 测试1: 文本模式读取
        print("\n测试1: 文本模式读取")
        result = tool.run({"path": "test_file.txt"})
        print(result)
        
        # 测试2: 二进制模式读取
        print("\n测试2: 二进制模式读取")
        result = tool.run({"path": "test_file.txt", "binary": True})
        print(f"Base64编码结果（前100字符）: {result[:100]}...")
        
        print("\n✓ ReadFileTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_write_file():
    """测试 WriteFileTool"""
    print("\n=== 测试 WriteFileTool ===")
    work_dir = setup_test_env()
    try:
        tool = WriteFileTool(work_dir)
        
        # 测试1: 创建新文件
        print("\n测试1: 创建新文件")
        result = tool.run({
            "path": "new_file.txt",
            "content": "This is a new file\nWith multiple lines"
        })
        print(f"结果: {result}")
        if Path(work_dir / "new_file.txt").exists():
            print(f"文件内容: {Path(work_dir / 'new_file.txt').read_text()}")
        
        # 测试2: 追加模式
        print("\n测试2: 追加模式")
        result = tool.run({
            "path": "new_file.txt",
            "content": "\nAppended line",
            "append": True
        })
        print(f"结果: {result}")
        print(f"文件内容: {Path(work_dir / 'new_file.txt').read_text()}")
        
        print("\n✓ WriteFileTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_diff():
    """测试 DiffTool"""
    print("\n=== 测试 DiffTool ===")
    work_dir = setup_test_env()
    try:
        tool = DiffTool(work_dir)
        
        # 创建两个不同的文件用于对比
        (work_dir / "file_a.txt").write_text("Line 1\nLine 2\nLine 3")
        (work_dir / "file_b.txt").write_text("Line 1\nLine 2 Modified\nLine 3\nLine 4")
        
        # 测试1: 文件对比
        print("\n测试1: 文件对比")
        result = tool.run({
            "path_a": "file_a.txt",
            "path_b": "file_b.txt"
        })
        print(result)
        
        print("\n✓ DiffTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_checksum():
    """测试 ChecksumTool"""
    print("\n=== 测试 ChecksumTool ===")
    work_dir = setup_test_env()
    try:
        tool = ChecksumTool(work_dir)
        
        # 测试1: SHA256（默认）
        print("\n测试1: SHA256 哈希")
        result = tool.run({"path": "test_file.txt"})
        print(f"SHA256: {result}")
        
        # 测试2: MD5
        print("\n测试2: MD5 哈希")
        result = tool.run({"path": "test_file.txt", "algorithm": "md5"})
        print(f"MD5: {result}")
        
        # 测试3: SHA1
        print("\n测试3: SHA1 哈希")
        result = tool.run({"path": "test_file.txt", "algorithm": "sha1"})
        print(f"SHA1: {result}")
        
        print("\n✓ ChecksumTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


if __name__ == "__main__":
    print("=" * 60)
    print("文件操作工具测试")
    print("=" * 60)
    
    test_print_tree()
    test_list_files()
    test_search()
    test_open_file()
    test_read_file()
    test_write_file()
    test_diff()
    test_checksum()
    
    print("\n" + "=" * 60)
    print("所有文件操作工具测试完成！")
    print("=" * 60)
