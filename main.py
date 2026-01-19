# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

import sys
from typing import Tuple

from config import config
from logger_config import setup_logging
from agent import ReActAgent
from cli import (
    ArgumentHandler,
    CommandProcessor,
)
from cli.textual_app import ReActAgentApp


def initialize_application() -> Tuple[ReActAgent, CommandProcessor]:
    """
    初始化应用程序组件
    
    Returns:
        (agent, command_processor) 元组
    """
    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        sys.exit(1)
    
    # 设置日志
    log_file_path = setup_logging()
    
    # 启动时检查更新（后台，不阻塞）
    try:
        from update import check_update
        check_update()
    except Exception:
        pass  # 更新检查失败不影响主程序运行
    
    # 创建 Agent
    agent = ReActAgent()
    
    # 创建指令处理器
    command_processor = CommandProcessor(agent)
    
    return agent, command_processor


def run_interactive_session(
    agent: ReActAgent,
    command_processor: CommandProcessor,
) -> None:
    """
    运行交互式会话（使用 Textual 界面）
    
    Args:
        agent: ReActAgent 实例
        command_processor: 命令处理器
    """
    # 创建 Textual 应用
    app = ReActAgentApp(agent, command_processor)
    app.run()


def main():
    """主函数"""
    # 处理命令行参数
    arg_handler = ArgumentHandler()
    should_exit = arg_handler.handle()
    
    if should_exit:
        return
    
    # 初始化应用程序
    agent, command_processor = initialize_application()
    
    # 运行交互式会话
    run_interactive_session(agent, command_processor)


if __name__ == "__main__":
    main()
