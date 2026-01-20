# -*- coding: utf-8 -*-
"""聊天消息组件模块"""

import time
from textual.widgets import Static
from textual.containers import Horizontal
from textual.events import Click
from rich.markup import escape
from rich.text import Text


class ChatMessage(Horizontal):
    """聊天消息基类"""
    
    def __init__(self, content: str, **kwargs):
        super().__init__(**kwargs)
        self.content = content
        self.static_widget: Static = None
        self._last_click_time = 0
        self._double_click_threshold = 0.5  # 双击时间阈值（秒）
    
    def compose(self):
        self.static_widget = Static(self._format_content(), markup=True, id="message-content")
        yield self.static_widget
    
    def update_content(self, new_content: str) -> None:
        """更新消息内容"""
        self.content = new_content
        if self.static_widget:
            self.static_widget.update(self._format_content())
    
    def on_click(self, event: Click) -> None:
        """处理点击事件，检测双击"""
        current_time = time.time()
        time_since_last_click = current_time - self._last_click_time
        
        if time_since_last_click < self._double_click_threshold:
            # 检测到双击
            self._handle_double_click()
            self._last_click_time = 0  # 重置，避免三次点击触发
        else:
            # 单次点击，记录时间
            self._last_click_time = current_time
    
    def _handle_double_click(self) -> None:
        """处理双击事件：复制消息文本"""
        # 获取原始文本内容（去除 markup）
        text_to_copy = self._get_plain_text()
        if text_to_copy:
            # 使用应用的 copy_to_clipboard 方法复制文本
            app = self.app
            if app:
                app.copy_to_clipboard(text_to_copy)
                # 显示复制成功的提示
                self.notify(f"已复制到剪贴板", severity="information", timeout=1.5)
    
    def _get_plain_text(self) -> str:
        """获取纯文本内容（去除 markup）"""
        # 获取格式化后的内容（包含前缀等）
        formatted_content = self._format_content()
        try:
            # 尝试从 markup 中提取纯文本
            text = Text.from_markup(formatted_content)
            return text.plain
        except Exception:
            # 如果解析失败，直接返回格式化后的内容
            return formatted_content


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
        return f"[bold yellow]Thinking:[/] [italic #7d8590]{escape(self.content)}[/]"


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
