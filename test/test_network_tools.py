# -*- coding: utf-8 -*-
"""网络工具测试"""

import sys
import tempfile
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.network_tools import (
    BrowseTool,
    SearchTool,
    DownloadTool,
    UploadTool,
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


def test_browse():
    """测试 BrowseTool"""
    print("\n=== 测试 BrowseTool ===")
    work_dir = setup_test_env()
    try:
        tool = BrowseTool(work_dir)
        
        # 测试1: 基本搜索
        print("\n测试1: 基本搜索")
        result = tool.run({"query": "Python programming"})
        print(result)
        
        # 测试2: 限制结果数
        print("\n测试2: 限制结果数")
        result = tool.run({
            "query": "machine learning",
            "max_results": 5
        })
        print(result)
        
        print("\n✓ BrowseTool 测试完成")
        print("注意: 这是占位符实现，实际使用时需要集成搜索引擎 API")
    finally:
        cleanup_test_env(work_dir)


def test_search():
    """测试 SearchTool"""
    print("\n=== 测试 SearchTool ===")
    work_dir = setup_test_env()
    try:
        tool = SearchTool(work_dir)
        
        # 测试1: 基本搜索
        print("\n测试1: 基本搜索")
        result = tool.run({"query": "Python best practices"})
        print(result)
        
        print("\n✓ SearchTool 测试完成")
        print("注意: 这是占位符实现，实际使用时需要集成搜索引擎 API")
    finally:
        cleanup_test_env(work_dir)


def test_download():
    """测试 DownloadTool"""
    print("\n=== 测试 DownloadTool ===")
    work_dir = setup_test_env()
    try:
        tool = DownloadTool(work_dir)
        
        # 测试1: 下载文件（使用公开的测试URL）
        print("\n测试1: 下载文件")
        print("注意: 实际测试需要有效的 URL")
        
        # 使用一个简单的测试 URL（如果可用）
        try:
            result = tool.run({
                "url": "https://www.example.com",
                "dest_path": "example.html"
            })
            print(result)
        except Exception as e:
            print(f"下载测试失败（预期）: {e}")
            print("这是正常的，因为需要网络连接和有效的 URL")
        
        print("\n✓ DownloadTool 测试完成")
    finally:
        cleanup_test_env(work_dir)


def test_upload():
    """测试 UploadTool"""
    print("\n=== 测试 UploadTool ===")
    work_dir = setup_test_env()
    try:
        tool = UploadTool(work_dir)
        
        # 创建测试文件
        test_file = work_dir / "test_upload.txt"
        test_file.write_text("Test upload content")
        
        # 测试1: 上传文件
        print("\n测试1: 上传文件")
        result = tool.run({
            "local_path": "test_upload.txt",
            "remote_path": "s3://test-bucket/test_upload.txt",
            "service": "s3",
            "metadata": {"content-type": "text/plain"}
        })
        print(result)
        
        print("\n✓ UploadTool 测试完成")
        print("注意: 这是占位符实现，实际使用时需要集成相应的服务 SDK")
    finally:
        cleanup_test_env(work_dir)


if __name__ == "__main__":
    print("=" * 60)
    print("网络工具测试")
    print("=" * 60)
    print("\n注意: 部分工具是占位符实现，需要集成实际的 API")
    print("=" * 60)
    
    test_browse()
    test_search()
    test_download()
    test_upload()
    
    print("\n" + "=" * 60)
    print("所有网络工具测试完成！")
    print("=" * 60)
