# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

import sys
from config import config
from logger_config import setup_logging
from agent import ReActAgent


def main():
    """主函数"""
    # 处理命令行参数
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg in ["--update", "update", "-u"]:
            from update import Updater
            updater = Updater()
            success, message = updater.update()
            print(message)
            sys.exit(0 if success else 1)
        
        elif arg in ["--version", "-v", "version"]:
            from __init__ import __version__
            print(f"ask version {__version__}")
            sys.exit(0)
        
        elif arg in ["--check-update", "check-update"]:
            from update import Updater
            updater = Updater()
            latest = updater.get_latest_version()
            if latest:
                comparison = updater.compare_versions(updater.current_version, latest)
                if comparison < 0:
                    print(f"发现新版本: {latest} (当前: {updater.current_version})")
                    print(f"运行 'ask --update' 进行更新")
                else:
                    print(f"当前已是最新版本: {updater.current_version}")
            else:
                print("无法检查更新，请检查网络连接")
            sys.exit(0)
        
        elif arg in ["--help", "-h", "help"]:
            print("ReAct Agent - 智能代理工具")
            print("\n用法:")
            print("  ask                   启动交互式会话")
            print("  ask --version         显示版本号")
            print("  ask --update          更新到最新版本")
            print("  ask --check-update    检查是否有新版本")
            print("  ask --help            显示帮助信息")
            sys.exit(0)
    
    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        return
    
    # 设置日志
    setup_logging(debug_mode=config.debug_mode)
    
    # 启动时检查更新（后台，不阻塞）
    try:
        from update import check_update
        check_update()
    except:
        pass  # 更新检查失败不影响主程序运行
    
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
