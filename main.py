# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

import sys
from config import config
from logger_config import setup_logging
from agent import ReActAgent
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.shortcuts import CompleteStyle


class CommandProcessor:
    """指令处理器"""
    
    def __init__(self, agent):
        self.agent = agent
        self.commands = {
            "help": self._help_command,
            "exit": self._exit_command,
        }
        
    def get_command_names(self):
        """获取所有指令名称（带/前缀）"""
        return [f"/{cmd}" for cmd in self.commands.keys()]
    
    def process_command(self, command_str):
        """处理指令"""
        if not command_str.startswith("/"):
            return False
        
        # 如果只有 /，显示指令帮助
        if command_str.strip() == "/":
            print("\n💡 可用指令:")
            for cmd_name in self.commands.keys():
                print(f"  /{cmd_name}")
            print("\n💡 提示: 输入 / 后按 Tab 键自动补全")
            return True
        
        # 提取指令名和参数
        parts = command_str[1:].strip().split()
        if not parts:
            return False
        
        command_name = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        # 执行指令
        if command_name in self.commands:
            self.commands[command_name](args)
            return True
        else:
            print(f"未知指令: /{command_name}")
            print("使用 /help 查看可用指令")
            return True
    
    def _help_command(self, args):
        """帮助指令"""
        print("\n可用指令:")
        print("  /help     - 显示此帮助信息")
        print("  /exit     - 退出程序")
        print("\n聊天模式:")
        print("  直接输入文本进行对话，无需使用 / 前缀")
    
    def _exit_command(self, args):
        """退出指令"""
        print("\n感谢使用，再见！")
        sys.exit(0)


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
    
    # 创建指令处理器
    command_processor = CommandProcessor(agent)
    
    # 创建 Prompt Toolkit 会话
    command_names = command_processor.get_command_names()
    completer = WordCompleter(command_names, ignore_case=True)
    
    session = PromptSession(
        completer=completer,
        complete_style=CompleteStyle.MULTI_COLUMN,
        message="请输入任务或指令: ",
    )
    
    # 显示欢迎信息
    print("\n" + "="*60)
    print("ReAct Agent - 智能代理工具")
    print("="*60)
    
    # 主循环
    try:
        while True:
            task_message = session.prompt()
            
            # 处理指令
            if command_processor.process_command(task_message):
                continue
            
            # 处理聊天
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
