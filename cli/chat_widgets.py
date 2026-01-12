# -*- coding: utf-8 -*-
"""聊天消息组件模块"""

from textual.widgets import Static
from textual.containers import Horizontal
from rich.markup import escape


class ChatMessage(Horizontal):
    """聊天消息基类"""
    
    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self.content = content
    
    def compose(self):
        yield Static(self._format_content(), markup=True)


class UserMessage(ChatMessage):
    """用户消息组件
    
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def _format_content(self) -> str:
        return escape(self.content)


class ThinkingMessage(ChatMessage):
    """思考消息组件
    
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def _format_content(self) -> str:
        return f"[italic #7d8590]{escape(self.content)}[/]"


class ContentMessage(ChatMessage):
    """内容消息组件
    
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def __init__(self, content: str, allow_markup: bool = False, **kwargs):
        super().__init__(content, **kwargs)
        self.allow_markup = allow_markup
    
    def _format_content(self) -> str:
        if self.allow_markup:
            return self.content
        return escape(self.content)


class ToolMessage(ChatMessage):
    """工具调用消息组件
    
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def _format_content(self) -> str:
        return f"[#8b5cf6]■[/]  {escape(self.content)}"


class SystemMessage(ChatMessage):
    """系统消息组件
    
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def _format_content(self) -> str:
        return f"[#ef4444]│[/] {escape(self.content)}"
