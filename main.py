# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

from .config import config
from .logger_config import setup_logging
from .agent import ReActAgent


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
            task_message = input("请输入任务，输入 exit 退出: ")
            if task_message == "exit":
                break
            if task_message.strip():
                agent.chat(task_message)
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
