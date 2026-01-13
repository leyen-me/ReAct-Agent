# -*- coding: utf-8 -*-
"""基于 Textual 的界面应用 - 简洁风格"""

from typing import List, Tuple

from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Input,
    TextArea,
    OptionList,
)
from textual.widgets.option_list import Option
from textual.containers import (
    Horizontal,
    Vertical,
    Container,
    ScrollableContainer,
)
from textual.binding import Binding
from textual import on
from textual.screen import ModalScreen
from textual.events import Click, Key
from textual.message import Message

from agent import ReActAgent
from cli.commands import CommandProcessor
from cli.chat_widgets import (
    UserMessage,
    ThinkingMessage,
    ContentMessage,
    ToolMessage,
    SystemMessage,
    HistoryMessage,
)
from config import config
from utils import refresh_file_list, get_file_list, search_files
from logger_config import get_all_log_files


class ChatInput(TextArea):
    """自定义聊天输入框，Enter 提交，Shift+Enter 换行"""
    
    class Submitted(Message):
        """提交消息事件"""
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.placeholder = "输入消息... (/ 打开命令, @ 选择文件)"
        self._showing_placeholder = False
    
    def on_mount(self) -> None:
        """挂载时显示 placeholder"""
        if not self.text:
            self._show_placeholder()
    
    def _show_placeholder(self) -> None:
        """显示 placeholder"""
        if not self.text and not self._showing_placeholder:
            self.load_text(self.placeholder)
            self._showing_placeholder = True
            # 设置为只读样式（通过添加类）
            self.add_class("placeholder")
    
    def _clear_placeholder(self) -> None:
        """清除 placeholder"""
        if self._showing_placeholder:
            self.clear()
            self._showing_placeholder = False
            self.remove_class("placeholder")
    
    def on_focus(self) -> None:
        """获得焦点时清除 placeholder"""
        if self._showing_placeholder:
            self._clear_placeholder()
    
    def on_blur(self) -> None:
        """失去焦点时恢复 placeholder"""
        if not self.text and not self._showing_placeholder:
            self._show_placeholder()
    
    def _on_key(self, event: Key) -> None:
        """拦截 Enter 键"""
        # 如果显示 placeholder，任何输入都要先清除它
        if self._showing_placeholder and event.key not in ("escape", "tab", "up", "down", "left", "right", "home", "end", "pageup", "pagedown"):
            if event.key != "enter":
                self._clear_placeholder()
        
        if event.key == "enter":
            # 检查是否按住 Shift 键（Shift+Enter 换行）
            # 如果不是 Shift+Enter，则提交
            # Textual 中 Shift+Enter 通常表示为不同的 key 值
            # 直接让 Enter 提交消息
            event.prevent_default()
            event.stop()
            # 不提交 placeholder 文本
            if not self._showing_placeholder:
                self.post_message(self.Submitted(self.text))
            return
        super()._on_key(event)


class CommandPaletteScreen(ModalScreen[str]):
    """命令面板对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("tab", "toggle_focus", "切换焦点"),
    ]
    
    CSS = """
    CommandPaletteScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }
    
    #palette-container {
        width: 70;
        max-height: 20;
        background: #ffffff;
        border: none;
        padding: 0;
    }
    
    #palette-header {
        height: 3;
        background: #ffffff;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #e5e7eb;
        align-vertical: middle;
    }
    
    #palette-title {
        width: 1fr;
        color: #000000;
        text-style: bold;
    }
    
    #palette-hint {
        width: auto;
        color: #7d8590;
    }
    
    #palette-content {
        padding: 1 2;
    }
    
    #palette-search {
        width: 100%;
        height: 1;
        margin-bottom: 1;
        background: #ffffff;
        border: none;
        color: #000000;
        align-vertical: middle;
    }
    
    #palette-search:focus {
        border: none;
    }
    
    #palette-list {
        height: auto;
        max-height: 14;
        background: #ffffff;
        border: none;
    }
    
    #palette-list > .option-list--option-highlighted {
        background: #f3f3f3;
    }
    
    #palette-list > .option-list--option {
        color: #000000;
    }
    """
    
    def __init__(self, commands: List[Tuple[str, str, str]], title: str = "Commands"):
        super().__init__()
        self.commands = commands
        self.title = title
        self.filtered_commands = commands.copy()
        self.focus_on_input = True
    
    def compose(self) -> ComposeResult:
        with Container(id="palette-container"):
            with Horizontal(id="palette-header"):
                yield Static(self.title, id="palette-title")
                yield Static("[dim]ESC[/] 退出", id="palette-hint")
            with Container(id="palette-content"):
                yield Input(placeholder="输入命令名称搜索...", id="palette-search")
                yield OptionList(
                    *[Option(f"{cmd[1]}  [dim]{cmd[2]}[/]", id=cmd[0]) for cmd in self.commands],
                    id="palette-list"
                )
    
    def on_mount(self) -> None:
        # 默认让搜索框获得焦点，方便用户直接输入
        option_list = self.query_one("#palette-list", OptionList)
        if self.filtered_commands:
            option_list.highlighted = 0
        self.query_one("#palette-search", Input).focus()
        self.focus_on_input = True
    
    def action_toggle_focus(self) -> None:
        """切换焦点"""
        if self.focus_on_input:
            option_list = self.query_one("#palette-list", OptionList)
            if self.filtered_commands:
                option_list.focus()
                if option_list.highlighted is None:
                    option_list.highlighted = 0
                self.focus_on_input = False
        else:
            self.query_one("#palette-search", Input).focus()
            self.focus_on_input = True
    
    @on(Input.Changed, "#palette-search")
    def filter_commands(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        option_list = self.query_one("#palette-list", OptionList)
        option_list.clear_options()
        
        if not query:
            self.filtered_commands = self.commands.copy()
        else:
            self.filtered_commands = [
                cmd for cmd in self.commands
                if query in cmd[1].lower() or query in cmd[2].lower()
            ]
        
        for cmd in self.filtered_commands:
            option_list.add_option(Option(f"{cmd[1]}  [dim]{cmd[2]}[/]", id=cmd[0]))
        
        # 如果有结果，默认选中第一个
        if self.filtered_commands:
            option_list.highlighted = 0
    
    @on(OptionList.OptionSelected, "#palette-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(event.option.id)
    
    @on(Input.Submitted, "#palette-search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        if self.filtered_commands:
            self.dismiss(self.filtered_commands[0][0])
    
    @on(Key)
    def on_key(self, event: Key) -> None:
        """处理按键事件"""
        focused = self.focused
        option_list = self.query_one("#palette-list", OptionList)
        
        if isinstance(focused, Input):
            # 输入框获得焦点时，上下键操作列表
            if event.key == "up":
                if self.filtered_commands:
                    option_list.focus()
                    current = option_list.highlighted or 0
                    option_list.highlighted = max(0, current - 1)
                    self.focus_on_input = False
                    event.prevent_default()
            elif event.key == "down":
                if self.filtered_commands:
                    option_list.focus()
                    current = option_list.highlighted or 0
                    option_list.highlighted = min(len(self.filtered_commands) - 1, current + 1)
                    self.focus_on_input = False
                    event.prevent_default()
            elif event.key == "tab":
                # Tab 键切换焦点
                self.action_toggle_focus()
                event.prevent_default()
        elif isinstance(focused, OptionList):
            if event.key == "enter":
                highlighted = option_list.highlighted
                if highlighted is not None and self.filtered_commands:
                    self.dismiss(self.filtered_commands[highlighted][0])
                    event.prevent_default()
            elif event.key == "tab":
                # Tab 键切换焦点
                self.action_toggle_focus()
                event.prevent_default()


class FilePickerScreen(ModalScreen[str]):
    """文件选择对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("tab", "toggle_focus", "切换焦点"),
    ]
    
    CSS = """
    FilePickerScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }
    
    #filepicker-container {
        width: 80;
        max-height: 24;
        background: #ffffff;
        border: none;
        padding: 0;
    }
    
    #filepicker-header {
        height: 3;
        background: #ffffff;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #e5e7eb;
        align-vertical: middle;
    }
    
    #filepicker-title {
        width: 1fr;
        color: #000000;
        text-style: bold;
    }
    
    #filepicker-hint {
        width: auto;
        color: #7d8590;
    }
    
    #filepicker-content {
        padding: 1 2;
    }
    
    #filepicker-search {
        width: 100%;
        height: 1;
        margin-bottom: 1;
        background: #ffffff;
        border: none;
        color: #000000;
        align-vertical: middle;
    }
    
    #filepicker-search:focus {
        border: none;
    }
    
    #filepicker-list {
        height: auto;
        max-height: 18;
        background: #ffffff;
        border: none;
    }
    
    #filepicker-list > .option-list--option-highlighted {
        background: #f3f3f3;
    }
    
    #filepicker-list > .option-list--option {
        color: #000000;
    }
    """
    
    def __init__(self, work_dir: str):
        super().__init__()
        self.work_dir = work_dir
        self.files: List[str] = []
        self.focus_on_input = True
    
    def compose(self) -> ComposeResult:
        with Container(id="filepicker-container"):
            with Horizontal(id="filepicker-header"):
                yield Static("选择文件", id="filepicker-title")
                yield Static("[dim]ESC[/] 退出", id="filepicker-hint")
            with Container(id="filepicker-content"):
                yield Input(placeholder="输入文件名搜索...", id="filepicker-search")
                yield OptionList(id="filepicker-list")
    
    def on_mount(self) -> None:
        self._load_files("")
        # 默认让搜索框获得焦点，方便用户直接输入
        option_list = self.query_one("#filepicker-list", OptionList)
        if self.files:
            option_list.highlighted = 0
        self.query_one("#filepicker-search", Input).focus()
        self.focus_on_input = True
    
    def action_toggle_focus(self) -> None:
        """切换焦点"""
        if self.focus_on_input:
            option_list = self.query_one("#filepicker-list", OptionList)
            if self.files:
                option_list.focus()
                if option_list.highlighted is None:
                    option_list.highlighted = 0
                self.focus_on_input = False
        else:
            self.query_one("#filepicker-search", Input).focus()
            self.focus_on_input = True
    
    def _load_files(self, query: str) -> None:
        option_list = self.query_one("#filepicker-list", OptionList)
        option_list.clear_options()
        
        if query.strip():
            self.files = search_files(self.work_dir, query, limit=50)
        else:
            self.files = get_file_list(self.work_dir)[:30]
        
        for file_path in self.files:
            option_list.add_option(Option(file_path, id=file_path))
        
        # 如果有结果，默认选中第一个
        if self.files:
            option_list.highlighted = 0
    
    @on(Input.Changed, "#filepicker-search")
    def filter_files(self, event: Input.Changed) -> None:
        self._load_files(event.value)
    
    @on(OptionList.OptionSelected, "#filepicker-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(event.option.id)
    
    @on(Input.Submitted, "#filepicker-search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        if self.files:
            self.dismiss(self.files[0])
    
    @on(Key)
    def on_key(self, event: Key) -> None:
        """处理按键事件"""
        focused = self.focused
        option_list = self.query_one("#filepicker-list", OptionList)
        
        if isinstance(focused, Input):
            # 输入框获得焦点时，上下键操作列表
            if event.key == "up":
                if self.files:
                    option_list.focus()
                    current = option_list.highlighted or 0
                    option_list.highlighted = max(0, current - 1)
                    self.focus_on_input = False
                    event.prevent_default()
            elif event.key == "down":
                if self.files:
                    option_list.focus()
                    current = option_list.highlighted or 0
                    option_list.highlighted = min(len(self.files) - 1, current + 1)
                    self.focus_on_input = False
                    event.prevent_default()
            elif event.key == "tab":
                # Tab 键切换焦点
                self.action_toggle_focus()
                event.prevent_default()
        elif isinstance(focused, OptionList):
            if event.key == "enter":
                highlighted = option_list.highlighted
                if highlighted is not None and self.files:
                    self.dismiss(self.files[highlighted])
                    event.prevent_default()
            elif event.key == "tab":
                # Tab 键切换焦点
                self.action_toggle_focus()
                event.prevent_default()


class LogViewerScreen(ModalScreen[None]):
    """日志查看对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("tab", "toggle_focus", "切换焦点"),
    ]
    
    CSS = """
    LogViewerScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.5);
    }
    
    #logviewer-container {
        width: 90%;
        height: 85%;
        background: #ffffff;
        border: none;
        padding: 0;
    }
    
    #logviewer-header {
        height: 3;
        background: #ffffff;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #e5e7eb;
        align-vertical: middle;
    }
    
    #logviewer-title {
        width: 1fr;
        color: #000000;
        text-style: bold;
    }
    
    #logviewer-hint {
        width: auto;
        color: #7d8590;
    }
    
    #logviewer-content {
        height: 1fr;
        padding: 0;
    }
    
    #logviewer-file-list {
        width: 28;
        height: 100%;
        background: #ffffff;
        border: none;
        padding: 1 2;
    }
    
    #logviewer-file-list > .option-list--option-highlighted {
        background: #f3f3f3;
    }
    
    #logviewer-file-list > .option-list--option {
        color: #000000;
    }
    
    #logviewer-text {
        width: 1fr;
        height: 100%;
        background: #ffffff;
        padding: 1 2;
        border: none;
    }
    
    #logviewer-text:focus {
        border: none;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.log_files = []
        self.current_log_content = ""
    
    def compose(self) -> ComposeResult:
        with Container(id="logviewer-container"):
            with Horizontal(id="logviewer-header"):
                yield Static("日志查看器", id="logviewer-title")
                yield Static("[dim]ESC[/] 关闭", id="logviewer-hint")
            with Horizontal(id="logviewer-content"):
                yield OptionList(id="logviewer-file-list")
                yield TextArea("", id="logviewer-text", read_only=True)
    
    def on_mount(self) -> None:
        self._load_log_files()
        option_list = self.query_one("#logviewer-file-list", OptionList)
        if self.log_files:
            option_list.highlighted = 0
            option_list.focus()
            self._load_log_content(self.log_files[0])
        else:
            text_area = self.query_one("#logviewer-text", TextArea)
            text_area.load_text("没有找到日志文件")
    
    def _load_log_files(self) -> None:
        option_list = self.query_one("#logviewer-file-list", OptionList)
        option_list.clear_options()
        
        self.log_files = get_all_log_files()
        
        if not self.log_files:
            option_list.add_option(Option("无日志文件", id="empty"))
            return
        
        for log_file in self.log_files:
            # 显示文件名
            display_name = log_file.name
            option_list.add_option(Option(display_name, id=str(log_file)))
        
        if self.log_files:
            option_list.highlighted = 0
    
    def _load_log_content(self, log_file_path) -> None:
        try:
            with open(log_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if not content.strip():
                content = "日志文件为空"
            
            text_area = self.query_one("#logviewer-text", TextArea)
            text_area.load_text(content)
            text_area.scroll_end(animate=False)
        except Exception as e:
            text_area = self.query_one("#logviewer-text", TextArea)
            text_area.load_text(f"无法读取日志文件: {e}")
    
    @on(OptionList.OptionSelected, "#logviewer-file-list")
    def on_log_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id and event.option.id != "empty":
            from pathlib import Path
            log_file = Path(event.option.id)
            self._load_log_content(log_file)


class ReActAgentApp(App):
    """ReAct Agent Textual 应用 - 简洁风格"""
    
    CSS = """
    /* ===== 全局 - 深色简洁主题 ===== */
    Screen {
        background: #FFF;
    }
    
    /* ===== 主布局 ===== */
    #app-layout {
        height: 100%;
        width: 100%;
    }
    
    /* ===== Header ===== */
    #app-header {
        height: 3;
        background: #f9f9f9;
        padding: 0 2;
        border-left: ascii #b5b5b5;
        margin: 1 2 1 2;
        align-vertical: middle;
    }
    
    #header-title {
        width: 1fr;
        color: #000000;
        text-style: bold;
    }
    
    #header-stats {
        width: auto;
        color: #7f7f7f;
    }
    
    /* ===== Main 聊天区域 ===== */
    #main-container {
        height: 1fr;
        width: 100%;
        overflow-y: auto;
        scrollbar-color: #e5e7eb;
        scrollbar-color-hover: #d1d5db;
        scrollbar-size: 0 1;
    }
    
    #chat-log {
        width: 100%;
        height: auto;
        scrollbar-color: #e5e7eb;
        scrollbar-color-hover: #d1d5db;
        scrollbar-size: 0 1;
        background: #ffffff;
    }
    
    /* ===== 聊天消息组件样式 ===== */
    UserMessage {
        width: 100%;
        height: auto;
        min-height: 3;
        background: #f9f9f9;
        border-left: ascii #8b5cf6;
        margin: 0 2;
        align-vertical: middle;
    }
    
    UserMessage > Static {
        width: 100%;
        color: #000000;
        text-align: left;
        background: transparent;
        padding: 0 2;
    }
    
    ThinkingMessage {
        width: 100%;
        height: auto;
        min-height: 3;
        background: #ffffff;
        padding: 0 2;
        border-left: solid #f3f3f3;
        margin: 1 2 1 2;
        align-vertical: middle;
    }
    
    ThinkingMessage > Static {
        width: 100%;
        color: #7d8590;
        text-style: italic;
        text-align: left;
        background: transparent;
    }
    
    ContentMessage {
        width: 100%;
        height: auto;
        min-height: 1;
        background: #ffffff;
        padding: 0 2;
        margin: 1 2 1 2;
        align-vertical: middle;
    }
    
    ContentMessage > Static {
        width: 100%;
        color: #000000;
        text-align: left;
        background: transparent;
    }
    
    ToolMessage {
        width: 100%;
        height: auto;
        min-height: 1;
        background: #ffffff;
        padding: 0 2;
        border-left: ascii #22c55e;
        margin: 1 2 1 2;
        align-vertical: middle;
    }
    
    ToolMessage > Static {
        width: 100%;
        color: #000000;
        text-align: left;
        background: transparent;
    }
    
    SystemMessage {        
        width: 100%;
        height: auto;
        min-height: 3;
        background: #f9f9f9;
        border-left: ascii #ef4444;
        margin: 0 2;
        align-vertical: middle;
    }
    
    SystemMessage > Static {
        width: 100%;
        color: #ef4444;
        text-align: left;
        background: transparent;
    }
    
    HistoryMessage {
        width: 100%;
        height: auto;
        min-height: 1;
        background: #ffffff;
        padding: 0 2;
        margin: 1 2 1 2;
        align-vertical: middle;
        border-left: solid #ef4444;
    }
    
    HistoryMessage > Static {
        width: 100%;
        color: #000000;
        text-align: left;
        background: transparent;
    }
    
    /* ===== Footer 输入区域 ===== */
    #input-container {
        height: auto;
        min-height: 3;
        background: #f3f3f3;
        margin: 1 2 1 2;
        border-left: heavy #8b5cf6;
        padding: 0;
    }
    
    #user-input {
        width: 100%;
        height: auto;
        min-height: 1;
        max-height: 10;
        background: #f3f3f3;
        border: none;
        color: #303030;
        padding: 0 1;
        margin: 1 0 0 0;
    }
    
    #user-input.placeholder {
        color: #9ca3af;
    }
    
    #input-model-info {
        width: 100%;
        height: 1;
        background: #f3f3f3;
        padding: 0 1;
        margin: 1 0 1 0;
        color: #7d8590;
        align-vertical: middle;
    }
    
    #user-input:focus {
        border: none;
    }
    
    /* ===== Setting 底栏 ===== */
    #setting-bar {
        height: 1;
        background: #ffffff;
        padding: 0 2;
        margin: 0 2 1 2;
        align-vertical: middle;
    }
    
    #setting-left {
        width: 1fr;
        color: #7d8590;
    }
    
    #setting-right {
        width: auto;
        color: #7d8590;
    }
    
    #setting-right.chatting {
        color: #ef4444;
    }
    
    /* ===== 隐藏类 ===== */
    .hidden {
        display: none;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear", "清屏"),
        Binding("escape", "stop_chat", "停止对话", show=False),
        # Binding("ctrl+p", "open_palette", "命令"),
    ]
    
    def __init__(self, agent: ReActAgent, command_processor: CommandProcessor):
        super().__init__()
        self.agent = agent
        self.command_processor = command_processor
        self.chat_count = 0
        self.is_processing = False
        self.current_message_widget = None  # 当前正在更新的消息组件
        self._programmatic_value_set = False  # 标记是否是程序设置的文本
        self.chat_start_time = None  # 对话开始时间
        self.last_chat_duration = None  # 上一轮对话耗时（秒）
    
    def compose(self) -> ComposeResult:
        """组合应用界面"""
        with Vertical(id="app-layout"):
            # Header
            with Horizontal(id="app-header"):
                yield Static(self._get_title(), id="header-title")
                yield Static(self._get_stats(), id="header-stats")
            
            # Main: 聊天区域
            with ScrollableContainer(id="main-container"):
                with Vertical(id="chat-log"):
                    pass
            
            # Footer: 输入框
            with Vertical(id="input-container"):
                yield ChatInput(id="user-input")
                yield Static(self._get_model_info(), id="input-model-info")
            
            # Setting: 底栏
            with Horizontal(id="setting-bar"):
                yield Static(self._get_status_info(), id="setting-left")
                yield Static(
                    self._get_shortcuts_info(),
                    id="setting-right"
                )
    
    def _get_title(self) -> str:
        """获取标题"""
        return "[bold]ReAct Agent[/]"
    
    def _get_stats(self) -> str:
        """获取统计信息"""
        if not hasattr(self.agent, "message_manager"):
            return ""
        
        mm = self.agent.message_manager
        usage = mm.get_token_usage_percent()
        used = mm.max_context_tokens - mm.get_remaining_tokens()
        
        return f"Token: {used:,}  Usage: {usage:.0f}%"
    
    def _get_model_info(self) -> str:
        """获取模型信息"""
        model = getattr(config, 'model', 'unknown')
        return f"[#8b5cf6]■[/] Build [dim]{model}[/]"
    
    def _get_status_info(self) -> str:
        """获取状态信息"""
        if self.is_processing:
            status = "[#22c55e]●[/] 对话中"
        else:
            status = "[#7d8590]○[/] 空闲"
        
        if self.last_chat_duration is not None:
            duration = f"[dim]上轮耗时: {self.last_chat_duration:.1f}s[/]"
            return f"{status}  {duration}"
        else:
            return status
    
    def _get_shortcuts_info(self) -> str:
        """获取快捷键信息"""
        if self.is_processing:
            return "[#ef4444]ESC[/] 停止对话  [#3b82f6]CTRL+C[/] 退出  [#8b5cf6]CTRL+L[/] 清屏"
        else:
            return "[#3b82f6]CTRL+C[/] 退出  [#8b5cf6]CTRL+L[/] 清屏"
    
    def refresh_header(self) -> None:
        """刷新 Header"""
        try:
            self.query_one("#header-stats", Static).update(self._get_stats())
        except Exception:
            pass
    
    def refresh_status(self) -> None:
        """刷新状态栏"""
        try:
            self.query_one("#setting-left", Static).update(self._get_status_info())
            self.query_one("#setting-right", Static).update(self._get_shortcuts_info())
        except Exception:
            pass
    
    def _scroll_to_bottom(self) -> None:
        """滚动到底部"""
        try:
            chat_container = self.query_one("#chat-log", Vertical)
            main_container = self.query_one("#main-container", ScrollableContainer)
            # 等待布局更新后滚动
            self.set_timer(0.1, lambda: main_container.scroll_end(animate=False))
        except Exception:
            pass
    
    def on_mount(self) -> None:
        """应用挂载"""
        self.query_one("#user-input", ChatInput).focus()
        refresh_file_list(config.work_dir)
    
    @on(Click)
    def on_click(self, event: Click) -> None:
        """处理点击事件，保持输入框焦点"""
        # 检查当前焦点是否在输入框上
        input_widget = self.query_one("#user-input", ChatInput)
        focused_widget = self.focused
        
        # 如果焦点不在输入框上，且不在模态对话框中，则重新聚焦输入框
        if focused_widget != input_widget:
            # 检查是否在模态对话框中（命令面板或文件选择器）
            if not isinstance(self.screen, ModalScreen):
                # 延迟一下再聚焦，避免与点击事件冲突
                self.set_timer(0.05, lambda: input_widget.focus())
    
    @on(TextArea.Changed, "#user-input")
    def on_input_changed(self, event: TextArea.Changed) -> None:
        """监听输入变化"""
        # TextArea.Changed 事件没有 value 属性，需要从组件获取文本
        input_widget = self.query_one("#user-input", ChatInput)
        text = input_widget.text
        
        if self.is_processing:
            return
        
        # 如果已经有弹窗打开，不处理触发逻辑，避免嵌套弹窗
        if isinstance(self.screen, ModalScreen):
            return
        
        if text.endswith("@"):
            self.set_timer(0.05, self._open_file_picker_from_at)
        elif text == "/":
            self.set_timer(0.05, self._open_palette_from_slash)
    
    def _open_file_picker_from_at(self) -> None:
        input_widget = self.query_one("#user-input", ChatInput)
        current_value = input_widget.text
        if current_value.endswith("@"):
            new_value = current_value[:-1]
            
            # 标记这是程序设置的文本
            self._programmatic_value_set = True
            
            # 先移除焦点，避免设置值时自动选中所有文本
            input_widget.blur()
            
            # 设置新值（此时没有焦点，不会选中）
            input_widget.text = new_value
            
            # 延迟恢复焦点并清除选中状态
            def restore_focus():
                input_widget.focus()
                # 延迟清除选中状态
                def clear_selection():
                    if input_widget.has_focus and self._programmatic_value_set:
                        # 设置光标位置到文本末尾，这会取消选中
                        try:
                            input_widget.action_end()
                        except AttributeError:
                            # 如果 action_end 不存在，尝试其他方法
                            pass
                        self._programmatic_value_set = False
                self.set_timer(0.05, clear_selection)
            self.set_timer(0.05, restore_focus)
        self._open_file_picker()
    
    def _open_palette_from_slash(self) -> None:
        input_widget = self.query_one("#user-input", ChatInput)
        if input_widget.text == "/":
            input_widget.text = ""
        self.action_open_palette()
    
    def _open_log_viewer(self) -> None:
        # 如果已经有弹窗打开，不重复打开
        if isinstance(self.screen, ModalScreen):
            return
        
        def handle_close(result: None) -> None:
            # 关闭后聚焦到输入框
            input_widget = self.query_one("#user-input", ChatInput)
            input_widget.focus()
        
        # 移除 user-input 的焦点
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.blur()
        self.push_screen(LogViewerScreen(), handle_close)
    
    def _open_file_picker(self) -> None:
        # 如果已经有弹窗打开，不重复打开
        if isinstance(self.screen, ModalScreen):
            return
        
        def handle_file_selection(file_path: str | None) -> None:
            input_widget = self.query_one("#user-input", ChatInput)
            if file_path:
                current = input_widget.text
                new_value = f"{current}`{file_path}` "
                
                # 标记这是程序设置的文本
                self._programmatic_value_set = True
                
                # 先移除焦点，避免设置值时自动选中所有文本
                input_widget.blur()
                
                # 设置新值（此时没有焦点，不会选中）
                input_widget.text = new_value
                
                # 延迟恢复焦点并清除选中状态
                def restore_focus():
                    input_widget.focus()
                    # 延迟清除选中状态
                    def clear_selection():
                        if input_widget.has_focus and self._programmatic_value_set:
                            # 设置光标位置到文本末尾，这会取消选中
                            try:
                                input_widget.action_end()
                            except AttributeError:
                                # 如果 action_end 不存在，尝试其他方法
                                pass
                            self._programmatic_value_set = False
                    self.set_timer(0.05, clear_selection)
                self.set_timer(0.1, restore_focus)
            else:
                # 无论是否选择文件，关闭弹窗后都聚焦到 user-input
                input_widget.focus()
        
        # 移除 user-input 的焦点，避免弹窗打开时还能输入
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.blur()
        self.push_screen(FilePickerScreen(config.work_dir), handle_file_selection)
    
    def action_open_palette(self) -> None:
        # 如果已经有弹窗打开，不重复打开
        if isinstance(self.screen, ModalScreen):
            return
        
        commands = [
            ("help", "Help", "显示帮助"),
            ("status", "Status", "上下文使用情况"),
            ("messages", "Messages", "消息历史"),
            ("logs", "Logs", "查看日志"),
            ("clear", "Clear", "清空聊天"),
            ("exit", "Exit", "退出应用"),
        ]
        
        def handle_command(cmd_id: str | None) -> None:
            input_widget = self.query_one("#user-input", ChatInput)
            
            if not cmd_id:
                # 取消选择，聚焦到 user-input
                input_widget.focus()
                return
            
            if cmd_id == "help":
                self._show_help()
                input_widget.focus()
            elif cmd_id == "status":
                self._show_status()
                input_widget.focus()
            elif cmd_id == "messages":
                self._show_messages()
                input_widget.focus()
            elif cmd_id == "logs":
                self._open_log_viewer()
            elif cmd_id == "clear":
                self.action_clear()
                input_widget.focus()
            elif cmd_id == "exit":
                self.action_quit()
            else:
                input_widget.focus()
        
        # 移除 user-input 的焦点，避免弹窗打开时还能输入
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.blur()
        self.push_screen(CommandPaletteScreen(commands, "Commands"), handle_command)
    
    def _show_help(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        
        help_content = """[bold]ReAct Agent[/bold]

[bold]快捷键[/bold]
  [dim]Ctrl+C[/dim]  退出
  [dim]Ctrl+L[/dim]  清屏
  [dim]/[/dim]       命令面板
  [dim]@[/dim]       文件选择

[bold]可用工具[/bold]
  文件操作、代码搜索、Git 管理、命令执行、任务管理"""
        
        help_msg = HistoryMessage(help_content)
        chat_container.mount(help_msg)
        self._scroll_to_bottom()
        self.query_one("#user-input", ChatInput).focus()
    
    def _show_status(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        
        if hasattr(self.agent, "message_manager"):
            mm = self.agent.message_manager
            usage = mm.get_token_usage_percent()
            remaining = mm.get_remaining_tokens()
            used = mm.max_context_tokens - remaining
            max_tokens = mm.max_context_tokens
            
            status_msg = ContentMessage(f"[dim]Context:[/] {usage:.1f}% ({used:,}/{max_tokens:,})", allow_markup=True)
            chat_container.mount(status_msg)
            self._scroll_to_bottom()
        
        self.query_one("#user-input", ChatInput).focus()
    
    def _show_messages(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        
        if not hasattr(self.agent, "message_manager"):
            return
        
        messages = self.agent.message_manager.get_messages()
        
        # 显示标题
        title_msg = ContentMessage(f"[dim]消息历史 (共 {len(messages)} 条):[/]", allow_markup=True)
        chat_container.mount(title_msg)
        
        # 显示每条消息，统一使用 HistoryMessage，用颜色区分角色
        for i, message in enumerate(messages, 1):
            role = message.get("role", "unknown")
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            # 根据角色设置不同的颜色和格式
            if role == "system":
                # 系统消息：红色
                role_label = "[#ef4444][SYSTEM][/]"
                content_display = content[:500] + ('...' if len(content) > 500 else '')
                display_content = f"[dim][{i}][/] {role_label}\n{content_display}"
            elif role == "user":
                # 用户消息：蓝色
                role_label = "[#3b82f6][USER][/]"
                content_display = content[:500] + ('...' if len(content) > 500 else '')
                display_content = f"[dim][{i}][/] {role_label}\n{content_display}"
            elif role == "assistant":
                # 助手消息：如果有工具调用，显示工具调用信息；否则显示内容
                if tool_calls:
                    role_label = "[#22c55e][ASSISTANT - 工具调用][/]"
                    tool_info = []
                    for tool_call in tool_calls:
                        if "function" in tool_call:
                            func = tool_call["function"]
                            name = func.get("name", "unknown")
                            args = func.get("arguments", "")
                            args_display = args[:200] + ('...' if len(args) > 200 else '')
                            tool_info.append(f"工具: {name}\n参数: {args_display}")
                    display_content = f"[dim][{i}][/] {role_label}\n" + "\n".join(tool_info)
                else:
                    role_label = "[#8b5cf6][ASSISTANT][/]"
                    content_display = content[:500] + ('...' if len(content) > 500 else '')
                    display_content = f"[dim][{i}][/] {role_label}\n{content_display}"
            elif role == "tool":
                # 工具结果消息：绿色
                role_label = "[#22c55e][TOOL RESULT][/]"
                tool_call_id = message.get("tool_call_id", "")
                tool_id_display = tool_call_id[:20] + ('...' if len(tool_call_id) > 20 else '')
                content_display = content[:500] + ('...' if len(content) > 500 else '')
                display_content = f"[dim][{i}][/] {role_label} {tool_id_display}\n{content_display}"
            else:
                # 未知角色：灰色
                role_label = f"[#7d8590][{role.upper()}][/]"
                content_display = content[:500] + ('...' if len(content) > 500 else '')
                display_content = f"[dim][{i}][/] {role_label}\n{content_display}"
            
            # 使用 HistoryMessage 显示
            msg = HistoryMessage(display_content)
            chat_container.mount(msg)
        
        self._scroll_to_bottom()
        self.query_one("#user-input", ChatInput).focus()
    
    @on(ChatInput.Submitted)
    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        """处理聊天输入提交"""
        if self.is_processing:
            return
        
        message = event.value.strip()
        if not message:
            return
        
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.clear()
        input_widget._showing_placeholder = False
        
        self.chat_count += 1
        self.add_user_message(message)
        refresh_file_list(config.work_dir)
        
        # 记录对话开始时间
        import time
        self.chat_start_time = time.time()
        self.is_processing = True
        self.refresh_status()
        
        self.worker = self.run_worker(
            lambda: self.handle_chat(message),
            thread=True,
            name="chat_worker",
        )
    
    def handle_chat(self, message: str) -> None:
        """处理聊天"""
        try:
            app = self.app
            current_section = None
            current_content = ""
            
            def output_callback(text: str, end_newline: bool = True) -> None:
                nonlocal current_section, current_content
                
                if "模型思考" in text:
                    # 内容已经通过流式更新显示在 current_message_widget 中了
                    # 只需要清空引用，准备下一个 section
                    current_content = ""
                    app.call_from_thread(lambda: setattr(app, 'current_message_widget', None))
                    current_section = "reasoning"
                    return
                elif "最终回复" in text:
                    # 内容已经通过流式更新显示在 current_message_widget 中了
                    # 只需要清空引用，准备下一个 section
                    current_content = ""
                    app.call_from_thread(lambda: setattr(app, 'current_message_widget', None))
                    current_section = "content"
                    return
                elif "工具调用" in text:
                    # 内容已经通过流式更新显示在 current_message_widget 中了
                    # 只需要清空引用，准备下一个 section
                    current_content = ""
                    app.call_from_thread(lambda: setattr(app, 'current_message_widget', None))
                    current_section = "tool"
                    return
                
                if current_section:
                    current_content += text
                    if end_newline:
                        current_content += "\n"
                    
                    # 流式更新：如果还没有消息组件，创建一个；否则更新现有组件
                    app.call_from_thread(
                        lambda: app._stream_update_message(current_section, current_content)
                    )
                else:
                    app.call_from_thread(
                        lambda: app._add_output(text, end_newline)
                    )
            
            self.agent.chat(message, output_callback)
            
            # 最后确保当前消息已更新（如果还有内容且消息组件存在，已经通过流式更新显示过了）
            # 只有在没有消息组件的情况下才需要 flush（这种情况应该不会发生）
            if current_content and current_section:
                # 如果已经有消息组件，确保内容已更新；如果没有，创建新消息
                app.call_from_thread(
                    lambda: app._ensure_message_finalized(current_section, current_content)
                )
            app.call_from_thread(lambda: setattr(app, 'current_message_widget', None))
                
        except Exception as e:
            app = self.app
            import traceback
            error_msg = f"Error: {e}\n\n{traceback.format_exc()}"
            app.call_from_thread(
                lambda: app.add_system_message(error_msg)
            )
        finally:
            app = self.app
            app.call_from_thread(lambda: app._finish_chat())
    
    def _finish_chat(self) -> None:
        # 计算对话耗时
        import time
        if self.chat_start_time is not None:
            self.last_chat_duration = time.time() - self.chat_start_time
            self.chat_start_time = None
        
        self.is_processing = False
        self.refresh_header()
        self.refresh_status()
        input_widget = self.query_one("#user-input", ChatInput)
        if not input_widget.text:
            input_widget._show_placeholder()
        input_widget.focus()
    
    def _flush_content(self, section: str, content: str) -> None:
        self.flush_current_content(section, content)
    
    def _update_content(self, section: str, content: str) -> None:
        self.update_section_content(section, content)
    
    def _add_output(self, text: str, end_newline: bool) -> None:
        self.add_assistant_output(text, end_newline)
    
    def flush_current_content(self, section: str, content: str) -> None:
        if not content.strip():
            return
        
        chat_container = self.query_one("#chat-log", Vertical)
        if section == "reasoning":
            # 思考消息
            msg = ThinkingMessage(content.strip())
            chat_container.mount(msg)
        elif section == "content":
            # 内容消息
            msg = ContentMessage(content.strip())
            chat_container.mount(msg)
        elif section == "tool":
            # 工具调用消息
            msg = ToolMessage(content.strip())
            chat_container.mount(msg)
        else:
            msg = ContentMessage(content)
            chat_container.mount(msg)
        self._scroll_to_bottom()
    
    def _stream_update_message(self, section: str, content: str) -> None:
        """流式更新消息内容"""
        # 如果还没有当前消息组件，创建一个
        if self.current_message_widget is None:
            chat_container = self.query_one("#chat-log", Vertical)
            if section == "reasoning":
                self.current_message_widget = ThinkingMessage("")
            elif section == "content":
                self.current_message_widget = ContentMessage("")
            elif section == "tool":
                self.current_message_widget = ToolMessage("")
            else:
                self.current_message_widget = ContentMessage("")
            chat_container.mount(self.current_message_widget)
            self._scroll_to_bottom()
        
        # 更新当前消息组件的内容
        if self.current_message_widget:
            self.current_message_widget.update_content(content)
            self._scroll_to_bottom()
    
    def _ensure_message_finalized(self, section: str, content: str) -> None:
        """确保消息已最终化（避免重复显示）"""
        # 如果已经有消息组件，说明内容已经通过流式更新显示过了，不需要再创建
        if self.current_message_widget is None and content.strip():
            # 只有在没有消息组件的情况下才创建新消息（这种情况应该很少见）
            self.flush_current_content(section, content)
    
    def update_section_content(self, section: str, content: str) -> None:
        """更新部分内容 - 此方法已废弃，改为使用 _stream_update_message"""
        # 这个方法不再使用，保留是为了兼容性
        pass
    
    def add_user_message(self, message: str) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        msg = UserMessage(message)
        chat_container.mount(msg)
        self._scroll_to_bottom()
    
    def add_assistant_output(self, text: str, end_newline: bool = True) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        msg = ContentMessage(text)
        chat_container.mount(msg)
        self._scroll_to_bottom()
    
    def add_system_message(self, message: str) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        msg = SystemMessage(message)
        chat_container.mount(msg)
        self._scroll_to_bottom()
    
    def action_stop_chat(self) -> None:
        """停止当前对话"""
        if self.is_processing:
            # 设置 agent 的中断标志
            self.agent.stop_chat()
            # 添加系统消息提示
            self.add_system_message("[用户在此处中断了对话，未完成的任务已暂停]")
    
    def action_clear(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        chat_container.remove_children()
        self.query_one("#user-input", ChatInput).focus()
    
    def action_quit(self) -> None:
        self.exit()
