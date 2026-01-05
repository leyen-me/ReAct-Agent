# -*- coding: utf-8 -*-
"""命令行指令处理器模块"""

import sys
from typing import List, Dict, Callable, Any, Optional

from agent import ReActAgent


class CommandProcessor:
    """指令处理器，负责处理用户输入的命令"""
    
    def __init__(self, agent: ReActAgent):
        """
        初始化指令处理器
        
        Args:
            agent: ReActAgent 实例
        """
        self.agent = agent
        self.commands: Dict[str, Callable[[List[str]], None]] = {
            "help": self._help_command,
            "exit": self._exit_command,
            "status": self._status_command,
            "get_messages": self._get_messages_command,
        }
    
    def get_command_names(self) -> List[str]:
        """
        获取所有指令名称（带 / 前缀）
        
        Returns:
            指令名称列表
        """
        return [f"/{cmd}" for cmd in self.commands.keys()]
    
    def process_command(self, command_str: str) -> bool:
        """
        处理指令
        
        Args:
            command_str: 指令字符串
            
        Returns:
            如果是指令则返回 True，否则返回 False
        """
        if not command_str.startswith("/"):
            return False
        
        # 如果只有 /，显示指令帮助
        if command_str.strip() == "/":
            self._show_command_list()
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
            self._show_unknown_command(command_name)
            return True
    
    def _show_command_list(self) -> None:
        """显示可用指令列表"""
        print("\n💡 可用指令:")
        for cmd_name in self.commands.keys():
            print(f"  /{cmd_name}")
        print("\n💡 提示: 输入 / 后按 Tab 键自动补全")
    
    def _show_unknown_command(self, command_name: str) -> None:
        """
        显示未知指令提示
        
        Args:
            command_name: 未知的指令名称
        """
        print(f"未知指令: /{command_name}")
        print("使用 /help 查看可用指令")
    
    def _help_command(self, args: List[str]) -> None:
        """
        帮助指令
        
        Args:
            args: 指令参数（未使用）
        """
        print("\n可用指令:")
        print("  /help         - 显示此帮助信息")
        print("  /status       - 显示系统状态和上下文使用情况")
        print("  /get_messages - 显示当前对话消息历史")
        print("  /exit         - 退出程序")
        print("\n聊天模式:")
        print("  直接输入文本进行对话，无需使用 / 前缀")
        print("  输入 @ 后按 Tab 键可以补全文件路径")
        print("  文件列表会在每轮对话前自动刷新")
    
    def _exit_command(self, args: List[str]) -> None:
        """
        退出指令
        
        Args:
            args: 指令参数（未使用）
        """
        print("\n感谢使用，再见！")
        sys.exit(0)
    
    def _status_command(self, args: List[str]) -> None:
        """
        状态指令，显示系统状态和上下文使用情况
        
        Args:
            args: 指令参数（未使用）
        """
        if not hasattr(self.agent, "message_manager"):
            print("\n状态信息不可用")
            return
        
        message_manager = self.agent.message_manager
        usage_percent = message_manager.get_token_usage_percent()
        remaining_tokens = message_manager.get_remaining_tokens()
        used_tokens = message_manager.max_context_tokens - remaining_tokens
        max_tokens = message_manager.max_context_tokens
        
        print(f"{'='*60}")
        print(
            f"上下文使用: {usage_percent:.1f}% ({used_tokens:,}/{max_tokens:,} tokens)"
        )
        print(f"剩余 tokens: {remaining_tokens:,}")
        print(f"{'='*60}")
    
    def _get_messages_command(self, args: List[str]) -> None:
        """
        获取消息指令，显示当前对话消息历史
        
        Args:
            args: 指令参数（未使用）
        """
        if not hasattr(self.agent, "message_manager"):
            print("\n消息管理器不可用")
            return
        
        messages = self.agent.message_manager.get_messages()
        
        print(f"\n{'='*60}")
        print("当前对话消息历史:")
        print(f"{'='*60}")
        
        for i, message in enumerate(messages, 1):
            self._print_message(i, message)
        
        print(f"\n{'='*60}")
        print(f"总计 {len(messages)} 条消息")
        print(f"{'='*60}")
    
    def _print_message(self, index: int, message: Dict[str, Any]) -> None:
        """
        打印单条消息
        
        Args:
            index: 消息索引
            message: 消息字典
        """
        role = message.get("role", "unknown")
        content = message.get("content", "")
        
        print(f"\n{index}. [{role.upper()}]")
        
        # 显示内容，如果太长则截断
        if content:
            self._print_content(content)
        
        # 如果是工具调用，显示相关信息
        if "tool_calls" in message:
            print("   [工具调用]")
            for tool_call in message.get("tool_calls", []):
                self._print_tool_call(tool_call)
    
    def _print_content(self, content: str, prefix: str = "   ", max_length: int = 200) -> None:
        """
        打印内容，如果太长则截断
        
        Args:
            content: 要打印的内容
            prefix: 前缀字符串
            max_length: 最大显示长度
        """
        if len(content) > max_length:
            print(f"{prefix}{content[:max_length]}...")
        else:
            print(f"{prefix}{content}")
    
    def _print_tool_call(self, tool_call: Dict[str, Any]) -> None:
        """
        打印工具调用信息
        
        Args:
            tool_call: 工具调用字典
        """
        if "function" in tool_call:
            func = tool_call["function"]
            print(f"     函数: {func.get('name', 'unknown')}")
            print(f"     参数: {func.get('arguments', '')}")

