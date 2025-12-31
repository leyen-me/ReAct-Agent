# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

import sys
from typing import Tuple
from prompt_toolkit.completion import WordCompleter

from config import config
from logger_config import setup_logging
from agent import ReActAgent
from utils import refresh_file_list, get_file_count
from cli import (
    ArgumentHandler,
    CommandProcessor,
    FileCompleter,
    MergedCompleter,
    create_session,
    get_prompt_message,
)


def initialize_application() -> Tuple[ReActAgent, CommandProcessor, MergedCompleter]:
    """
    初始化应用程序组件
    
    Returns:
        (agent, file_list_manager, command_processor, completer) 元组
    """
    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        sys.exit(1)
    
    # 设置日志
    setup_logging(debug_mode=config.debug_mode)
    
    # 启动时检查更新（后台，不阻塞）
    try:
        from update import check_update
        check_update()
    except Exception:
        pass  # 更新检查失败不影响主程序运行
    
    # 创建 Agent
    agent = ReActAgent()
    
    # 初始化文件列表缓存（启动时自动扫描）
    print("正在扫描工作目录...")
    file_count = refresh_file_list(config.work_dir)
    print(f"已扫描 {file_count} 个文件")
    print("提示: 文件列表会在每轮对话前自动刷新")
    
    # 创建指令处理器
    command_processor = CommandProcessor(agent)
    
    # 创建命令补全器
    command_names = command_processor.get_command_names()
    command_completer = WordCompleter(
        command_names,
        ignore_case=True,
        match_middle=True,
        sentence=True,
    )
    
    # 创建文件补全器（传入工作目录）
    file_completer = FileCompleter(config.work_dir)
    
    # 创建合并补全器
    completer = MergedCompleter(command_completer, file_completer)
    
    return agent, command_processor, completer


def run_interactive_session(
    agent: ReActAgent,
    command_processor: CommandProcessor,
    completer: MergedCompleter,
) -> None:
    """
    运行交互式会话
    
    Args:
        agent: ReActAgent 实例
        command_processor: 命令处理器
        completer: 补全器
    """
    # 创建提示会话
    session = create_session(completer)
    
    chat_count = 0
    
    try:
        while True:
            chat_count += 1
            
            # 获取提示消息
            message = get_prompt_message(chat_count)
            task_message = session.prompt(message=message)
            
            # 处理指令
            if command_processor.process_command(task_message):
                continue
            
            # 处理聊天
            if task_message.strip():
                # 在每轮对话前自动刷新文件列表
                refresh_file_list(config.work_dir)
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


def main():
    """主函数"""
    # 处理命令行参数
    arg_handler = ArgumentHandler()
    should_exit = arg_handler.handle()
    
    if should_exit:
        return
    
    # 初始化应用程序
    agent, command_processor, completer = initialize_application()
    
    # 运行交互式会话
    run_interactive_session(agent, command_processor, completer)


if __name__ == "__main__":
    main()
