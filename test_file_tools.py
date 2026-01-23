# -*- coding: utf-8 -*-
"""测试文件编辑工具"""

import os
import tempfile
from pathlib import Path

from tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    EditFileByLineTool,
    EditFileByPositionTool,
)


def print_separator(title: str):
    """打印分隔线"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_read_file_tool(work_dir: Path, test_file: str):
    """测试 ReadFileTool（带行号）"""
    print_separator("测试 ReadFileTool（带行号）")
    
    tool = ReadFileTool(work_dir)
    result = tool.run({"path": test_file})
    print(result)


def test_edit_file_tool(work_dir: Path, test_file: str):
    """测试 EditFileTool（基于文本匹配）"""
    print_separator("测试 EditFileTool（基于文本匹配）")
    
    tool = EditFileTool(work_dir)
    
    # 替换 "Hello" 为 "Hi"
    result = tool.run({
        "path": test_file,
        "old_string": "Hello",
        "new_string": "Hi",
        "replace_all": False
    })
    print(f"替换结果: {result}")
    
    # 读取文件查看结果
    read_tool = ReadFileTool(work_dir)
    content = read_tool.run({"path": test_file})
    print("\n文件内容:")
    print(content)


def test_edit_file_by_line_tool(work_dir: Path, test_file: str):
    """测试 EditFileByLineTool（基于行号）"""
    print_separator("测试 EditFileByLineTool（基于行号）")
    
    tool = EditFileByLineTool(work_dir)
    
    # 替换第 3 行
    result = tool.run({
        "path": test_file,
        "start_line": 3,
        "end_line": 3,
        "new_string": "    print('这是替换后的第3行')"
    })
    print(f"替换结果: {result}")
    
    # 读取文件查看结果
    read_tool = ReadFileTool(work_dir)
    content = read_tool.run({"path": test_file})
    print("\n文件内容:")
    print(content)


def test_edit_file_by_position_tool(work_dir: Path, test_file: str):
    """测试 EditFileByPositionTool（基于字符位置）"""
    print_separator("测试 EditFileByPositionTool（基于字符位置）")
    
    # 先读取文件获取字符位置信息
    read_tool = ReadFileTool(work_dir)
    content = read_tool.run({"path": test_file})
    print("当前文件内容:")
    print(content)
    
    # 读取原始内容计算位置
    with open(test_file, "r", encoding="utf-8") as f:
        original_content = f.read()
    
    tool = EditFileByPositionTool(work_dir)
    
    # 测试1: 插入操作（在位置 50 插入文本）
    print("\n--- 测试1: 插入操作 ---")
    insert_pos = 50
    result = tool.run({
        "path": test_file,
        "start_position": insert_pos,
        "end_position": insert_pos,
        "new_string": "\n    # 这是插入的注释\n"
    })
    print(f"插入结果: {result}")
    
    # 读取文件查看结果
    content = read_tool.run({"path": test_file})
    print("\n插入后的文件内容:")
    print(content)
    
    # 重新读取文件以获取新的字符位置
    with open(test_file, "r", encoding="utf-8") as f:
        new_content = f.read()
    
    # 测试2: 删除操作（删除一段文本）
    print("\n--- 测试2: 删除操作 ---")
    # 找到要删除的文本位置
    delete_start = new_content.find("这是插入的注释")
    if delete_start != -1:
        delete_end = delete_start + len("这是插入的注释")
        result = tool.run({
            "path": test_file,
            "start_position": delete_start,
            "end_position": delete_end,
            "new_string": ""
        })
        print(f"删除结果: {result}")
    
    # 读取文件查看结果
    content = read_tool.run({"path": test_file})
    print("\n删除后的文件内容:")
    print(content)
    
    # 重新读取文件
    with open(test_file, "r", encoding="utf-8") as f:
        final_content = f.read()
    
    # 测试3: 替换操作（替换一段文本）
    print("\n--- 测试3: 替换操作 ---")
    # 找到要替换的文本位置
    replace_start = final_content.find("World")
    if replace_start != -1:
        replace_end = replace_start + len("World")
        result = tool.run({
            "path": test_file,
            "start_position": replace_start,
            "end_position": replace_end,
            "new_string": "Universe"
        })
        print(f"替换结果: {result}")
    
    # 读取文件查看最终结果
    content = read_tool.run({"path": test_file})
    print("\n最终文件内容:")
    print(content)


def main():
    """主测试函数"""
    print("=" * 60)
    print("  文件编辑工具测试")
    print("=" * 60)
    
    # 创建临时目录作为工作目录
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)
        test_file = str(work_dir / "test_file.py")
        
        # 创建测试文件
        print(f"\n创建测试文件: {test_file}")
        initial_content = """# -*- coding: utf-8 -*-
def hello():
    print('Hello')
    print('World')
    return True

if __name__ == '__main__':
    hello()
"""
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(initial_content)
        
        print("初始文件内容:")
        print(initial_content)
        
        # 测试各个工具
        test_read_file_tool(work_dir, test_file)
        test_edit_file_tool(work_dir, test_file)
        test_edit_file_by_line_tool(work_dir, test_file)
        test_edit_file_by_position_tool(work_dir, test_file)
        
        print("\n" + "=" * 60)
        print("  所有测试完成！")
        print("=" * 60)


if __name__ == "__main__":
    main()
