#!/usr/bin/env python3

import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(__file__))

from main import chat

def test_reflection_summary():
    """测试反思和总结功能"""
    print("=== 测试反思和总结功能 ===")
    
    # 测试任务：读取一个文件
    test_task = "读取 workspace2/snake_game.html 文件的内容"
    
    try:
        print(f"执行任务: {test_task}")
        chat(test_task)
        print("任务执行完成")
        
        # 检查是否生成了总结文件
        work_dir = os.path.join(os.path.dirname(__file__), "workspace2")
        files = os.listdir(work_dir)
        summary_files = [f for f in files if f.startswith("summary_") and f.endswith(".md")]
        
        if summary_files:
            print(f"找到总结文件: {summary_files}")
            latest_summary = os.path.join(work_dir, summary_files[-1])
            with open(latest_summary, "r", encoding="utf-8") as f:
                content = f.read()
                print("总结文件内容:")
                print(content)
        else:
            print("未找到总结文件")
            
    except Exception as e:
        print(f"测试失败: {e}")

if __name__ == "__main__":
    test_reflection_summary()
