# -*- coding: utf-8 -*-
"""ReAct Agent 主程序入口"""

import sys
import os
from pathlib import Path
from typing import List, Iterable, Optional
from config import config
from logger_config import setup_logging
from agent import ReActAgent
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter, Completion, Completer
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.styles import Style
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.document import Document


class FileListManager:
    """文件列表管理器，负责管理文件列表的缓存和更新"""
    
    def __init__(self, work_dir: Path):
        """
        初始化文件列表管理器
        
        Args:
            work_dir: 工作目录路径
        """
        self.work_dir = work_dir
        self.file_list: List[str] = []
        self._refresh()
    
    def _refresh(self) -> None:
        """刷新文件列表"""
        self.file_list = scan_workspace_files(self.work_dir)
    
    def refresh(self) -> int:
        """
        刷新文件列表
        
        Returns:
            文件数量
        """
        self._refresh()
        return len(self.file_list)
    
    def get_file_list(self) -> List[str]:
        """
        获取文件列表
        
        Returns:
            文件列表
        """
        return self.file_list
    
    def get_file_count(self) -> int:
        """获取当前文件数量"""
        return len(self.file_list)


def scan_workspace_files(work_dir: Path, ignore_patterns: List[str] = None) -> List[str]:
    """
    扫描工作目录，生成文件列表并排序
    
    Args:
        work_dir: 工作目录路径
        ignore_patterns: 忽略的文件/目录模式列表
        
    Returns:
        排序后的文件路径列表（相对于工作目录）
    """
    if ignore_patterns is None:
        ignore_patterns = ['__pycache__', '.git', 'node_modules', '.venv', 'venv', '.env']
    
    file_list = []
    
    def should_ignore(path: Path) -> bool:
        """检查路径是否应该被忽略"""
        import fnmatch
        path_str = str(path)
        name = path.name
        
        # 检查是否匹配忽略模式
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(name, pattern) or pattern in path_str:
                return True
        return False
    
    def scan_directory(directory: Path, relative_prefix: str = ""):
        """递归扫描目录"""
        try:
            if not directory.exists() or not directory.is_dir():
                return
            
            items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            
            for item in items:
                if should_ignore(item):
                    continue
                
                relative_path = os.path.join(relative_prefix, item.name) if relative_prefix else item.name
                
                if item.is_file():
                    file_list.append(relative_path)
                elif item.is_dir():
                    scan_directory(item, relative_path)
        except PermissionError:
            pass  # 忽略权限错误
    
    scan_directory(work_dir)
    return sorted(file_list, key=str.lower)


class FileCompleter(Completer):
    """文件补全器，处理@符号后的文件补全"""
    
    def __init__(self, file_list_manager: FileListManager):
        """
        初始化文件补全器
        
        Args:
            file_list_manager: 文件列表管理器
        """
        self.file_list_manager = file_list_manager
    
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """获取补全项"""
        text = document.text_before_cursor
        
        # 检查是否在@符号后
        if '@' not in text:
            return
        
        # 找到最后一个@符号的位置
        last_at_index = text.rfind('@')
        if last_at_index == -1:
            return
        
        # 获取文件列表（如果需要会自动刷新）
        file_list = self.file_list_manager.get_file_list()
        
        # 获取@符号后的文本（查询字符串）
        query = text[last_at_index + 1:]
        
        # 如果查询字符串为空，显示前20个文件；否则过滤匹配的文件
        if query.strip() == '':
            matching_files = file_list[:20]  # 默认只显示前20个
        else:
            matching_files = [
                f for f in file_list
                if query.lower() in f.lower()
            ]
        
        # 限制结果数量
        matching_files = matching_files[:50]
        
        # 生成补全项
        for file_path in matching_files:
            # 计算需要替换的文本长度（从@后到光标位置）
            replace_length = len(text) - last_at_index - 1
            
            yield Completion(
                file_path,
                start_position=-replace_length,
                display=file_path,
                style="fg:#00ffcc",
            )


class MergedCompleter(Completer):
    """合并补全器，同时处理命令和文件补全"""
    
    def __init__(self, command_completer: WordCompleter, file_completer: FileCompleter):
        """
        初始化合并补全器
        
        Args:
            command_completer: 命令补全器
            file_completer: 文件补全器
        """
        self.command_completer = command_completer
        self.file_completer = file_completer
    
    def get_completions(self, document: Document, complete_event) -> Iterable[Completion]:
        """获取补全项"""
        text = document.text_before_cursor
        
        # 如果以/开头，使用命令补全器
        if text.startswith('/'):
            yield from self.command_completer.get_completions(document, complete_event)
        # 如果包含@符号，使用文件补全器
        elif '@' in text:
            yield from self.file_completer.get_completions(document, complete_event)


class CommandProcessor:
    """指令处理器"""

    def __init__(self, agent):
        self.agent = agent
        self.commands = {
            "help": self._help_command,
            "exit": self._exit_command,
            "status": self._status_command,
            "get_messages": self._get_messages_command,
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
        print("  /help         - 显示此帮助信息")
        print("  /status       - 显示系统状态和上下文使用情况")
        print("  /get_messages - 显示当前对话消息历史")
        print("  /exit         - 退出程序")
        print("\n聊天模式:")
        print("  直接输入文本进行对话，无需使用 / 前缀")
        print("  输入 @ 后按 Tab 键可以补全文件路径")
        print("  文件列表会在每轮对话前自动刷新")

    def _exit_command(self, args):
        """退出指令"""
        print("\n感谢使用，再见！")
        sys.exit(0)

    def _status_command(self, args):
        """状态指令"""
        if not hasattr(self.agent, "message_manager"):
            print("\n状态信息不可用")
            return

        usage_percent = self.agent.message_manager.get_token_usage_percent()
        remaining_tokens = self.agent.message_manager.get_remaining_tokens()
        used_tokens = self.agent.message_manager.max_context_tokens - remaining_tokens
        max_tokens = self.agent.message_manager.max_context_tokens

        print(f"{'='*60}")
        print(
            f"上下文使用: {usage_percent:.1f}% ({used_tokens:,}/{max_tokens:,} tokens)"
        )
        print(f"剩余 tokens: {remaining_tokens:,}")
        print(f"{'='*60}")

    def _get_messages_command(self, args):
        """获取消息指令"""
        if not hasattr(self.agent, "message_manager"):
            print("\n消息管理器不可用")
            return

        messages = self.agent.message_manager.get_messages()

        print(f"\n{'='*60}")
        print("当前对话消息历史:")
        print(f"{'='*60}")

        for i, message in enumerate(messages, 1):
            role = message.get("role", "unknown")
            content = message.get("content", "")

            print(f"\n{i}. [{role.upper()}]")
            if content:
                # 显示内容，如果太长则截断
                if len(content) > 200:
                    print(f"   {content[:200]}...")
                else:
                    print(f"   {content}")

            # 如果是工具调用，显示相关信息
            if "tool_calls" in message:
                print("   [工具调用]")
                for tool_call in message.get("tool_calls", []):
                    if "function" in tool_call:
                        func = tool_call["function"]
                        print(f"     函数: {func.get('name', 'unknown')}")
                        print(f"     参数: {func.get('arguments', '')}")

            # 如果是工具结果，显示结果
            if "tool_call_id" in message:
                print(f"   [工具结果]")
                if len(content) > 200:
                    print(f"     结果: {content[:200]}...")
                else:
                    print(f"     结果: {content}")

        print(f"\n{'='*60}")
        print(f"总计 {len(messages)} 条消息")
        print(f"{'='*60}")


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

    # 创建文件列表管理器（启动时自动扫描）
    print("正在扫描工作目录...")
    file_list_manager = FileListManager(config.work_dir)
    print(f"已扫描 {file_list_manager.get_file_count()} 个文件")
    print(f"提示: 文件列表会在每轮对话前自动刷新")

    # 创建指令处理器
    command_processor = CommandProcessor(agent)
    
    # 创建命令补全器
    command_names = command_processor.get_command_names()
    command_completer = WordCompleter(
        command_names,
        ignore_case=True,
        match_middle=True,  # 允许中间匹配
        sentence=True,  # 允许部分匹配
    )
    
    # 创建文件补全器
    file_completer = FileCompleter(file_list_manager)
    
    # 创建合并补全器
    completer = MergedCompleter(command_completer, file_completer)

    # 定义完整的样式字典（列表风格）
    custom_style = Style.from_dict({
        # 输入区域样式
        "ansicyan": "#00ffcc",
        "ansigray": "#888888",
        
        # 补全菜单样式（列表风格）
        "completion-menu": "bg:#1a1a1a #ffffff",  # 菜单背景：深灰色，文字：白色
        "completion-menu.completion": "bg:#2a2a2a #cccccc",  # 补全项背景：中灰色
        "completion-menu.completion.current": "bg:#00ffcc #ffffff bold",  # 当前选中项：青色背景，白色粗体
        "completion-menu.completion.selected": "bg:#00ffcc #ffffff bold",  # 选中项：绿色背景，黄色粗体
        
        # 滚动条样式
        "scrollbar.background": "bg:#333333",
        "scrollbar.button": "bg:#00ffcc",
        "scrollbar.arrow": "#ffffff",
    })

    session = PromptSession(
        completer=completer,
        complete_style=CompleteStyle.COLUMN,  # 改为单列列表风格
        style=custom_style,
        placeholder=HTML("<ansigray>Plan, @ for context, / for commands</ansigray>"),
    )

    chat_count = 0
    # 主循环
    try:
        while True:
            chat_count += 1

            if chat_count == 1:
                message = HTML("\n<ansicyan>> </ansicyan>")
            else:
                message = HTML("\n\n<ansicyan>> </ansicyan>")

            task_message = session.prompt(message=message)

            # 处理指令
            if command_processor.process_command(task_message):
                continue

            # 处理聊天
            if task_message.strip():
                # 在每轮对话前自动刷新文件列表
                file_list_manager.refresh()
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
