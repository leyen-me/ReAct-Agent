# -*- coding: utf-8 -*-
"""其他工具测试"""

import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.other_tools import (
    FileUploadTool,
    FileDownloadTool,
    DalleTool,
    ZipTool,
    UnzipTool,
)


def setup_test_env():
    """设置测试环境"""
    test_dir = tempfile.mkdtemp(prefix="test_tools_")
    work_dir = Path(test_dir)
    
    # 创建测试文件
    (work_dir / "test_file.txt").write_text("Test file content\nLine 2")
    (work_dir / "subdir").mkdir()
    (work_dir / "subdir" / "nested.txt").write_text("Nested content")
    
    return work_dir


def cleanup_test_env(work_dir: Path):
    """清理测试环境"""
    if work_dir.exists():
        shutil.rmtree(work_dir)


def test_file_upload():
    """测试 FileUploadTool"""
    print("\n=== 测试 FileUploadTool ===")
    work_dir = setup_test_env()
    try:
        tool = FileUploadTool(work_dir)
        
        # 测试1: 上传文件
        print("\n测试1: 上传文件")
        result = tool.run({"path": "test_file.txt"})
        print(result)
        
        # 测试2: 上传不存在的文件
        print("\n测试2: 上传不存在的文件")
        result = tool.run({"path": "nonexistent.txt"})
        print(result)
        
        print("\n✓ FileUploadTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_file_download():
    """测试 FileDownloadTool"""
    print("\n=== 测试 FileDownloadTool ===")
    work_dir = setup_test_env()
    try:
        tool = FileDownloadTool(work_dir)
        
        # 测试1: 下载文件
        print("\n测试1: 下载文件")
        result = tool.run({"path": "test_file.txt"})
        print(result)
        
        # 测试2: 下载不存在的文件
        print("\n测试2: 下载不存在的文件")
        result = tool.run({"path": "nonexistent.txt"})
        print(result)
        
        print("\n✓ FileDownloadTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_dalle():
    """测试 DalleTool"""
    print("\n=== 测试 DalleTool ===")
    work_dir = setup_test_env()
    try:
        tool = DalleTool(work_dir)
        
        # 测试1: 生成图像
        print("\n测试1: 生成图像")
        result = tool.run({"prompt": "A beautiful sunset over mountains"})
        print(result)
        
        print("\n✓ DalleTool 测试完成")
        print("注意: 这是占位符实现，实际使用时需要集成 OpenAI DALL·E API")
    finally:
        cleanup_test_env(work_dir)


def test_zip():
    """测试 ZipTool"""
    print("\n=== 测试 ZipTool ===")
    work_dir = setup_test_env()
    try:
        tool = ZipTool(work_dir)
        
        # 测试1: 压缩单个文件
        print("\n测试1: 压缩单个文件")
        result = tool.run({
            "source": "test_file.txt",
            "dest_zip": "test_file.zip"
        })
        print(result)
        
        if Path(work_dir / "test_file.zip").exists():
            print("✓ ZIP 文件已创建")
        
        # 测试2: 压缩目录
        print("\n测试2: 压缩目录")
        result = tool.run({
            "source": "subdir",
            "dest_zip": "subdir.zip",
            "compresslevel": 6
        })
        print(result)
        
        if Path(work_dir / "subdir.zip").exists():
            print("✓ 目录 ZIP 文件已创建")
        
        # 测试3: 自定义压缩级别
        print("\n测试3: 自定义压缩级别")
        result = tool.run({
            "source": "test_file.txt",
            "dest_zip": "test_file_max.zip",
            "compresslevel": 9
        })
        print(result)
        
        print("\n✓ ZipTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_unzip():
    """测试 UnzipTool"""
    print("\n=== 测试 UnzipTool ===")
    work_dir = setup_test_env()
    try:
        tool = UnzipTool(work_dir)
        
        # 先创建一个 ZIP 文件
        zip_tool = ZipTool(work_dir)
        zip_tool.run({
            "source": "test_file.txt",
            "dest_zip": "test_file.zip"
        })
        
        # 测试1: 解压文件
        print("\n测试1: 解压文件")
        extract_dir = work_dir / "extracted"
        extract_dir.mkdir()
        
        result = tool.run({
            "zip_path": "test_file.zip",
            "dest_dir": "extracted",
            "overwrite": True
        })
        print(result)
        
        if Path(extract_dir / "test_file.txt").exists():
            print("✓ 文件已成功解压")
            print(f"解压内容: {Path(extract_dir / 'test_file.txt').read_text()}")
        
        # 测试2: 解压目录
        print("\n测试2: 解压目录")
        zip_tool.run({
            "source": "subdir",
            "dest_zip": "subdir.zip"
        })
        
        extract_dir2 = work_dir / "extracted2"
        extract_dir2.mkdir()
        
        result = tool.run({
            "zip_path": "subdir.zip",
            "dest_dir": "extracted2",
            "overwrite": True
        })
        print(result)
        
        print("\n✓ UnzipTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


if __name__ == "__main__":
    print("=" * 60)
    print("其他工具测试")
    print("=" * 60)
    
    test_file_upload()
    test_file_download()
    test_dalle()
    test_zip()
    test_unzip()
    
    print("\n" + "=" * 60)
    print("所有其他工具测试完成！")
    print("=" * 60)
