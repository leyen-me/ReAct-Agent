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
        self.static_widget: Static = None
    
    def compose(self):
        self.static_widget = Static(self._format_content(), markup=True, id="message-content")
        yield self.static_widget
    
    def update_content(self, new_content: str) -> None:
        """更新消息内容"""
        self.content = new_content
        if self.static_widget:
            self.static_widget.update(self._format_content())


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
        return f"[#22c55e]■[/]  {escape(self.content)}"


class SystemMessage(ChatMessage):
    """系统消息组件
    
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def _format_content(self) -> str:
        return f"[#ef4444][SYSTEM][/] {escape(self.content)}"


class HistoryMessage(ChatMessage):
    """消息历史组件
    
    用于显示消息历史，支持 Rich markup 来区分不同角色
    样式定义在主应用 ReActAgentApp 的 CSS 中
    """
    
    def __init__(self, content: str, **kwargs):
        super().__init__(content, **kwargs)
    
    def _format_content(self) -> str:
        # 直接返回内容，因为内容已经包含 Rich markup
        return self.content
