# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

from config import config
from logger_config import setup_logging
from agent import ReActAgent


def main():
    """主函数"""
    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        return
    
    # 设置日志
    setup_logging(debug_mode=config.debug_mode)
    
    # 创建 Agent
    agent = ReActAgent()
    
    # 主循环
    try:
        while True:
            task_message = input("\n请输入任务，输入 exit 退出: ")
            if task_message == "exit":
                break
            if task_message.strip():
                agent.chat(task_message)
                
                # 每轮对话结束后显示上下文使用情况
                usage_percent = agent.message_manager.get_token_usage_percent()
                remaining_tokens = agent.message_manager.get_remaining_tokens()
                used_tokens = agent.message_manager.max_context_tokens - remaining_tokens
                max_tokens = agent.message_manager.max_context_tokens
                print(f"\n{'='*60}")
                print(f"[上下文使用: {usage_percent:.1f}% ({used_tokens:,}/{max_tokens:,} tokens) | 剩余: {remaining_tokens:,} tokens]")
                print(f"{'='*60}")
    except EOFError:
        print("\n程序结束")
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序异常: {e}")
        if config.debug_mode:
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
