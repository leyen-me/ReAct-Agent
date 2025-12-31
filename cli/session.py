# -*- coding: utf-8 -*-
"""命令行会话管理模块"""

from prompt_toolkit import PromptSession
from prompt_toolkit.shortcuts import CompleteStyle
from prompt_toolkit.formatted_text import HTML

from cli.completers import MergedCompleter
from cli.styles import get_custom_style


def create_session(completer: MergedCompleter) -> PromptSession:
    """
    创建提示会话
    
    Args:
        completer: 合并补全器实例
        
    Returns:
        PromptSession: 配置好的提示会话对象
    """
    return PromptSession(
        completer=completer,
        complete_style=CompleteStyle.COLUMN,  # 单列列表风格
        style=get_custom_style(),
        placeholder=HTML("<ansigray>Plan, @ for context, / for commands</ansigray>"),
    )


def get_prompt_message(chat_count: int) -> HTML:
    """
    获取提示消息
    
    Args:
        chat_count: 当前对话计数
        
    Returns:
        HTML: 格式化的提示消息
    """
    if chat_count == 1:
        return HTML("\n<ansicyan>> </ansicyan>")
    else:
        return HTML("\n\n<ansicyan>> </ansicyan>")

