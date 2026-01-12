# -*- coding: utf-8 -*-
"""基于 Textual 的界面应用"""

import asyncio
import sys
from io import StringIO
from typing import Optional, List, Tuple, Callable
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Input,
    RichLog,
    Button,
    Label,
    ListItem,
    ListView,
    OptionList,
)
from textual.widgets.option_list import Option
from textual.containers import (
    Horizontal,
    Vertical,
    Container,
    ScrollableContainer,
    Center,
)
from textual.binding import Binding
from textual.message import Message
from textual import events
from textual.worker import Worker
from textual import on
from textual.screen import ModalScreen
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

from agent import ReActAgent
from cli.commands import CommandProcessor
from config import config
from utils import refresh_file_list, get_file_list, search_files


class CommandPaletteScreen(ModalScreen[str]):
    """命令面板对话框 - 整合 / 命令和设置功能"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("up", "cursor_up", "上移"),
        Binding("down", "cursor_down", "下移"),
        Binding("enter", "select", "选择"),
    ]
    
    CSS = """
    CommandPaletteScreen {
        align: center middle;
    }
    
    #palette-container {
        width: 60;
        max-height: 24;
        background: #1a1b26;
        border: thick #7aa2f7;
        border-title-color: #bb9af7;
        padding: 1 2;
    }
    
    #palette-search {
        width: 100%;
        margin-bottom: 1;
        background: #24283b;
        border: solid #414868;
    }
    
    #palette-search:focus {
        border: solid #7aa2f7;
    }
    
    #palette-list {
        height: auto;
        max-height: 16;
        background: #1a1b26;
    }
    
    #palette-list > .option-list--option {
        padding: 0 1;
    }
    
    #palette-list > .option-list--option-highlighted {
        background: #364a82;
        color: #c0caf5;
    }
    """
    
    def __init__(self, commands: List[Tuple[str, str, str]], title: str = "命令面板"):
        """
        初始化命令面板
        
        Args:
            commands: 命令列表，每项为 (id, 显示名, 描述)
            title: 对话框标题
        """
        super().__init__()
        self.commands = commands
        self.title = title
        self.filtered_commands = commands.copy()
    
    def compose(self) -> ComposeResult:
        with Container(id="palette-container"):
            yield Static(f"[bold #bb9af7]⚡ {self.title}[/]", id="palette-title")
            yield Input(placeholder="搜索命令...", id="palette-search")
            yield OptionList(
                *[Option(f"[#7aa2f7]{cmd[1]}[/]  [dim]{cmd[2]}[/]", id=cmd[0]) for cmd in self.commands],
                id="palette-list"
            )
    
    def on_mount(self) -> None:
        self.query_one("#palette-search", Input).focus()
    
    @on(Input.Changed, "#palette-search")
    def filter_commands(self, event: Input.Changed) -> None:
        """过滤命令列表"""
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
            option_list.add_option(Option(f"[#7aa2f7]{cmd[1]}[/]  [dim]{cmd[2]}[/]", id=cmd[0]))
    
    @on(OptionList.OptionSelected, "#palette-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """选中命令"""
        if event.option.id:
            self.dismiss(event.option.id)
    
    @on(Input.Submitted, "#palette-search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """搜索框回车时选择第一个"""
        if self.filtered_commands:
            self.dismiss(self.filtered_commands[0][0])


class FilePickerScreen(ModalScreen[str]):
    """文件选择对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]
    
    CSS = """
    FilePickerScreen {
        align: center middle;
    }
    
    #filepicker-container {
        width: 70;
        max-height: 28;
        background: #1a1b26;
        border: thick #9ece6a;
        border-title-color: #9ece6a;
        padding: 1 2;
    }
    
    #filepicker-search {
        width: 100%;
        margin-bottom: 1;
        background: #24283b;
        border: solid #414868;
    }
    
    #filepicker-search:focus {
        border: solid #9ece6a;
    }
    
    #filepicker-list {
        height: auto;
        max-height: 20;
        background: #1a1b26;
    }
    
    #filepicker-list > .option-list--option-highlighted {
        background: #3d5a3d;
        color: #c0caf5;
    }
    """
    
    def __init__(self, work_dir: str):
        super().__init__()
        self.work_dir = work_dir
        self.files: List[str] = []
    
    def compose(self) -> ComposeResult:
        with Container(id="filepicker-container"):
            yield Static("[bold #9ece6a]📁 选择文件[/]", id="filepicker-title")
            yield Input(placeholder="搜索文件...", id="filepicker-search")
            yield OptionList(id="filepicker-list")
    
    def on_mount(self) -> None:
        self.query_one("#filepicker-search", Input).focus()
        self._load_files("")
    
    def _load_files(self, query: str) -> None:
        """加载文件列表"""
        option_list = self.query_one("#filepicker-list", OptionList)
        option_list.clear_options()
        
        if query.strip():
            self.files = search_files(self.work_dir, query, limit=50)
        else:
            self.files = get_file_list(self.work_dir)[:30]
        
        for file_path in self.files:
            # 根据文件类型显示不同图标
            icon = self._get_file_icon(file_path)
            option_list.add_option(Option(f"{icon} {file_path}", id=file_path))
    
    def _get_file_icon(self, path: str) -> str:
        """根据文件扩展名获取图标"""
        ext = Path(path).suffix.lower()
        icons = {
            ".py": "🐍",
            ".js": "📜",
            ".ts": "📘",
            ".tsx": "⚛️",
            ".jsx": "⚛️",
            ".html": "🌐",
            ".css": "🎨",
            ".json": "📋",
            ".md": "📝",
            ".txt": "📄",
            ".yml": "⚙️",
            ".yaml": "⚙️",
            ".toml": "⚙️",
            ".sh": "💻",
            ".go": "🐹",
            ".rs": "🦀",
        }
        return icons.get(ext, "📄")
    
    @on(Input.Changed, "#filepicker-search")
    def filter_files(self, event: Input.Changed) -> None:
        """过滤文件"""
        self._load_files(event.value)
    
    @on(OptionList.OptionSelected, "#filepicker-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """选中文件"""
        if event.option.id:
            self.dismiss(event.option.id)
    
    @on(Input.Submitted, "#filepicker-search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        """搜索框回车选择第一个"""
        if self.files:
            self.dismiss(self.files[0])


class ReActAgentApp(App):
    """ReAct Agent Textual 应用"""
    
    CSS = """
    /* ===== 全局主题 - Tokyo Night 风格 ===== */
    Screen {
        background: #1a1b26;
    }
    
    /* ===== Header 区域 ===== */
    #app-header {
        height: 3;
        background: #16161e;
        border-bottom: solid #414868;
        padding: 0 1;
    }
    
    #header-title {
        width: 1fr;
        color: #bb9af7;
        text-style: bold;
        padding: 1 0;
    }
    
    #header-context {
        width: auto;
        color: #7aa2f7;
        padding: 1 0;
    }
    
    /* ===== Main 聊天区域 ===== */
    #main-container {
        height: 1fr;
        background: #1a1b26;
    }
    
    #chat-area {
        height: 1fr;
        padding: 1;
        scrollbar-color: #414868;
        scrollbar-color-hover: #7aa2f7;
        scrollbar-color-active: #bb9af7;
    }
    
    #chat-log {
        background: #1a1b26;
    }
    
    /* ===== Footer 输入区域 ===== */
    #input-container {
        height: 3;
        background: #16161e;
        border-top: solid #414868;
        padding: 0 1;
    }
    
    #user-input {
        width: 1fr;
        background: #24283b;
        border: solid #414868;
        color: #c0caf5;
        padding: 0 1;
    }
    
    #user-input:focus {
        border: solid #7aa2f7;
    }
    
    #user-input.-invalid {
        border: solid #f7768e;
    }
    
    /* ===== Setting 底栏 ===== */
    #setting-bar {
        height: 1;
        background: #16161e;
        border-top: solid #414868;
        padding: 0 1;
    }
    
    #setting-left {
        width: 1fr;
        color: #565f89;
    }
    
    #setting-right {
        width: auto;
        color: #565f89;
    }
    
    .key-hint {
        color: #7aa2f7;
        text-style: bold;
    }
    
    .key-desc {
        color: #565f89;
    }
    
    /* ===== 消息样式 ===== */
    .user-message {
        color: #7dcfff;
        margin: 1 0;
    }
    
    .assistant-message {
        color: #9ece6a;
        margin: 1 0;
    }
    
    .system-message {
        color: #e0af68;
        margin: 1 0;
    }
    
    .tool-message {
        color: #bb9af7;
        margin: 1 0;
    }
    
    /* ===== 隐藏类 ===== */
    .hidden {
        display: none;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear", "清屏"),
        Binding("ctrl+p", "open_palette", "命令面板"),
    ]
    
    def __init__(self, agent: ReActAgent, command_processor: CommandProcessor):
        super().__init__()
        self.agent = agent
        self.command_processor = command_processor
        self.chat_count = 0
        self.is_processing = False
    
    def compose(self) -> ComposeResult:
        """组合应用界面 - 四部分布局"""
        # Header: 标题 + 上下文信息
        with Horizontal(id="app-header"):
            yield Static("🤖 ReAct Agent", id="header-title")
            yield Static(self._get_context_info(), id="header-context")
        
        # Main: 可滚动的聊天区域
        with ScrollableContainer(id="main-container"):
            yield RichLog(id="chat-log", markup=True, wrap=True, highlight=True)
        
        # Footer: 输入框
        with Horizontal(id="input-container"):
            yield Input(
                id="user-input",
                placeholder="输入消息... (@ 选择文件, / 或 Ctrl+P 打开命令面板)",
            )
        
        # Setting: 快捷键提示
        with Horizontal(id="setting-bar"):
            yield Static(
                "[bold #7aa2f7]Ctrl+C[/] [#565f89]退出[/]  "
                "[bold #7aa2f7]Ctrl+L[/] [#565f89]清屏[/]",
                id="setting-left"
            )
            yield Static(
                "[bold #7aa2f7]Ctrl+P[/] [#565f89]命令面板[/]",
                id="setting-right"
            )
    
    def _get_context_info(self) -> str:
        """获取上下文使用信息"""
        if not hasattr(self.agent, "message_manager"):
            return "[dim]上下文: 不可用[/]"
        
        mm = self.agent.message_manager
        usage = mm.get_token_usage_percent()
        remaining = mm.get_remaining_tokens()
        used = mm.max_context_tokens - remaining
        max_tokens = mm.max_context_tokens
        
        # 根据使用率选择颜色
        if usage < 50:
            color = "#9ece6a"  # 绿色
        elif usage < 80:
            color = "#e0af68"  # 橙色
        else:
            color = "#f7768e"  # 红色
        
        return f"[{color}]📊 {usage:.1f}%[/] [{color}]({used:,}/{max_tokens:,})[/]"
    
    def refresh_header(self) -> None:
        """刷新 Header 中的上下文信息"""
        try:
            context_widget = self.query_one("#header-context", Static)
            context_widget.update(self._get_context_info())
        except Exception:
            pass
    
    def on_mount(self) -> None:
        """应用挂载时的初始化"""
        self.query_one("#user-input", Input).focus()
        # 启动时刷新文件列表
        refresh_file_list(config.work_dir)
        # 显示欢迎信息
        self._show_welcome()
    
    def _show_welcome(self) -> None:
        """显示欢迎信息"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("[bold #bb9af7]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        chat_log.write("[bold #7aa2f7]          欢迎使用 ReAct Agent![/]")
        chat_log.write("")
        chat_log.write("[#565f89]快捷操作:[/]")
        chat_log.write("  [#7aa2f7]@[/]  [dim]输入 @ 选择文件引用[/]")
        chat_log.write("  [#7aa2f7]/[/]  [dim]输入 / 打开命令面板[/]")
        chat_log.write("  [#7aa2f7]Ctrl+P[/]  [dim]打开命令面板[/]")
        chat_log.write("[bold #bb9af7]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        chat_log.write("")
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """监听输入变化，检测 @ 和 / 触发对话框"""
        text = event.value
        
        if self.is_processing:
            return
        
        # 检测输入 @ 触发文件选择
        if text.endswith("@"):
            # 使用 set_timer 延迟打开，避免 @ 被输入
            self.set_timer(0.05, self._open_file_picker_from_at)
        
        # 检测输入 / 触发命令面板
        elif text == "/":
            self.set_timer(0.05, self._open_palette_from_slash)
    
    def _open_file_picker_from_at(self) -> None:
        """从 @ 触发打开文件选择器"""
        input_widget = self.query_one("#user-input", Input)
        current_value = input_widget.value
        
        # 移除尾部的 @
        if current_value.endswith("@"):
            input_widget.value = current_value[:-1]
        
        self._open_file_picker()
    
    def _open_palette_from_slash(self) -> None:
        """从 / 触发打开命令面板"""
        input_widget = self.query_one("#user-input", Input)
        # 清空 /
        if input_widget.value == "/":
            input_widget.value = ""
        self.action_open_palette()
    
    def _open_file_picker(self) -> None:
        """打开文件选择对话框"""
        def handle_file_selection(file_path: str | None) -> None:
            if file_path:
                input_widget = self.query_one("#user-input", Input)
                # 在当前位置插入文件引用
                current = input_widget.value
                input_widget.value = f"{current}`{file_path}` "
                input_widget.focus()
        
        self.push_screen(FilePickerScreen(config.work_dir), handle_file_selection)
    
    def action_open_palette(self) -> None:
        """打开命令面板"""
        commands = [
            ("help", "帮助", "显示帮助信息"),
            ("status", "状态", "显示系统状态和上下文使用情况"),
            ("get_messages", "消息历史", "显示当前对话消息历史"),
            ("clear", "清屏", "清空聊天记录"),
            ("file", "选择文件", "选择文件添加到输入"),
            ("exit", "退出", "退出程序"),
        ]
        
        def handle_command(cmd_id: str | None) -> None:
            if not cmd_id:
                self.query_one("#user-input", Input).focus()
                return
            
            if cmd_id == "help":
                self._show_help()
            elif cmd_id == "status":
                self._show_status()
            elif cmd_id == "get_messages":
                self._show_messages()
            elif cmd_id == "clear":
                self.action_clear()
            elif cmd_id == "file":
                self._open_file_picker()
            elif cmd_id == "exit":
                self.action_quit()
            else:
                self.query_one("#user-input", Input).focus()
        
        self.push_screen(CommandPaletteScreen(commands, "命令面板"), handle_command)
    
    def _show_help(self) -> None:
        """显示帮助信息"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("\n[bold #bb9af7]📖 帮助信息[/]")
        chat_log.write("[#565f89]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        chat_log.write("[#7aa2f7]基本操作:[/]")
        chat_log.write("  直接输入文本进行对话")
        chat_log.write("  输入 [bold]@[/] 选择文件引用")
        chat_log.write("  输入 [bold]/[/] 或按 [bold]Ctrl+P[/] 打开命令面板")
        chat_log.write("")
        chat_log.write("[#7aa2f7]快捷键:[/]")
        chat_log.write("  [bold]Ctrl+C[/]  退出程序")
        chat_log.write("  [bold]Ctrl+L[/]  清空聊天记录")
        chat_log.write("  [bold]Ctrl+P[/]  打开命令面板")
        chat_log.write("[#565f89]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]\n")
        self.query_one("#user-input", Input).focus()
    
    def _show_status(self) -> None:
        """显示状态信息"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("\n[bold #bb9af7]📊 系统状态[/]")
        chat_log.write("[#565f89]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        
        if hasattr(self.agent, "message_manager"):
            mm = self.agent.message_manager
            usage = mm.get_token_usage_percent()
            remaining = mm.get_remaining_tokens()
            used = mm.max_context_tokens - remaining
            max_tokens = mm.max_context_tokens
            
            chat_log.write(f"  上下文使用: [bold]{usage:.1f}%[/]")
            chat_log.write(f"  已用 tokens: [bold]{used:,}[/]")
            chat_log.write(f"  最大 tokens: [bold]{max_tokens:,}[/]")
            chat_log.write(f"  剩余 tokens: [bold]{remaining:,}[/]")
        else:
            chat_log.write("  [dim]状态信息不可用[/]")
        
        chat_log.write("[#565f89]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]\n")
        self.query_one("#user-input", Input).focus()
    
    def _show_messages(self) -> None:
        """显示消息历史"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write("\n[bold #bb9af7]📜 消息历史[/]")
        chat_log.write("[#565f89]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]")
        
        if hasattr(self.agent, "message_manager"):
            messages = self.agent.message_manager.get_messages()
            for i, msg in enumerate(messages, 1):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                
                role_colors = {
                    "user": "#7dcfff",
                    "assistant": "#9ece6a",
                    "system": "#e0af68",
                    "tool": "#bb9af7",
                }
                color = role_colors.get(role, "#c0caf5")
                
                # 截断长内容
                if len(content) > 100:
                    content = content[:100] + "..."
                
                chat_log.write(f"  [{color}]{i}. [{role.upper()}][/]")
                if content:
                    chat_log.write(f"     {content}")
            
            chat_log.write(f"\n  [dim]共 {len(messages)} 条消息[/]")
        else:
            chat_log.write("  [dim]消息历史不可用[/]")
        
        chat_log.write("[#565f89]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]\n")
        self.query_one("#user-input", Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理输入提交"""
        if self.is_processing:
            return
        
        message = event.value.strip()
        if not message:
            return
        
        # 清空输入框
        input_widget = self.query_one("#user-input", Input)
        input_widget.value = ""
        
        # 处理聊天
        self.chat_count += 1
        self.add_user_message(message)
        # 刷新文件列表
        refresh_file_list(config.work_dir)
        # 使用 Worker 处理聊天（避免阻塞 UI）
        self.is_processing = True
        self.worker = self.run_worker(
            lambda: self.handle_chat(message),
            thread=True,
            name="chat_worker",
        )
    
    def handle_chat(self, message: str) -> None:
        """处理聊天（在 Worker 线程中运行）"""
        try:
            app = self.app
            current_section = None
            current_content = ""
            
            def output_callback(text: str, end_newline: bool = True) -> None:
                nonlocal current_section, current_content
                
                # 检测新的部分
                if "模型思考" in text:
                    if current_content:
                        app.call_from_thread(
                            lambda: app._flush_content(current_section, current_content)
                        )
                        current_content = ""
                    current_section = "reasoning"
                    app.call_from_thread(
                        lambda: app.query_one("#chat-log", RichLog).write(
                            f"\n[dim #565f89]{'─'*20} 💭 模型思考 {'─'*20}[/]"
                        )
                    )
                    return
                elif "最终回复" in text:
                    if current_content:
                        app.call_from_thread(
                            lambda: app._flush_content(current_section, current_content)
                        )
                        current_content = ""
                    current_section = "content"
                    app.call_from_thread(
                        lambda: app.query_one("#chat-log", RichLog).write(
                            f"\n[#9ece6a]{'─'*20} ✨ 最终回复 {'─'*20}[/]"
                        )
                    )
                    return
                elif "工具调用" in text:
                    if current_content:
                        app.call_from_thread(
                            lambda: app._flush_content(current_section, current_content)
                        )
                        current_content = ""
                    current_section = "tool"
                    app.call_from_thread(
                        lambda: app.query_one("#chat-log", RichLog).write(
                            f"\n[#bb9af7]{'─'*20} 🔧 工具调用 {'─'*20}[/]"
                        )
                    )
                    return
                
                # 累积内容
                if current_section:
                    current_content += text
                    if end_newline:
                        current_content += "\n"
                    
                    if end_newline or len(current_content) >= 50:
                        app.call_from_thread(
                            lambda: app._update_content(current_section, current_content)
                        )
                        current_content = ""
                else:
                    app.call_from_thread(
                        lambda: app._add_output(text, end_newline)
                    )
            
            # 运行 agent.chat
            self.agent.chat(message, output_callback)
            
            # 刷新剩余内容
            if current_content:
                app.call_from_thread(
                    lambda: app._flush_content(current_section, current_content)
                )
                
        except Exception as e:
            app = self.app
            app.call_from_thread(
                lambda: app.add_system_message(f"错误: {e}")
            )
            import traceback
            if config.debug_mode:
                app.call_from_thread(
                    lambda: app.add_system_message(traceback.format_exc())
                )
        finally:
            app = self.app
            app.call_from_thread(lambda: app._finish_chat())
    
    def _finish_chat(self) -> None:
        """完成聊天处理"""
        self.is_processing = False
        self.refresh_header()
        self.query_one("#user-input", Input).focus()
    
    def _flush_content(self, section: str, content: str) -> None:
        """刷新内容"""
        self.flush_current_content(section, content)
    
    def _update_content(self, section: str, content: str) -> None:
        """更新内容"""
        self.update_section_content(section, content)
    
    def _add_output(self, text: str, end_newline: bool) -> None:
        """添加输出"""
        self.add_assistant_output(text, end_newline)
    
    def flush_current_content(self, section: str, content: str) -> None:
        """刷新当前部分的内容"""
        if not content.strip():
            return
        
        chat_log = self.query_one("#chat-log", RichLog)
        if section == "reasoning":
            chat_log.write(f"[dim]{content}[/]")
        elif section == "content":
            chat_log.write(f"[#9ece6a]{content}[/]")
        elif section == "tool":
            chat_log.write(f"[#bb9af7]{content}[/]")
        else:
            chat_log.write(content)
    
    def update_section_content(self, section: str, content: str) -> None:
        """更新部分内容"""
        if "\n" in content:
            chat_log = self.query_one("#chat-log", RichLog)
            if section == "reasoning":
                chat_log.write(f"[dim]{content}[/]")
            elif section == "content":
                chat_log.write(f"[#9ece6a]{content}[/]")
            elif section == "tool":
                chat_log.write(f"[#bb9af7]{content}[/]")
    
    def add_user_message(self, message: str) -> None:
        """添加用户消息"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"\n[bold #7dcfff]👤 USER[/]: {message}")
    
    def add_assistant_output(self, text: str, end_newline: bool = True) -> None:
        """添加助手输出"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(text)
    
    def add_system_message(self, message: str) -> None:
        """添加系统消息"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.write(f"[bold #e0af68]⚠️ SYSTEM[/]: {message}")
    
    def action_clear(self) -> None:
        """清屏"""
        chat_log = self.query_one("#chat-log", RichLog)
        chat_log.clear()
        self._show_welcome()
        self.query_one("#user-input", Input).focus()
    
    def action_quit(self) -> None:
        """退出应用"""
        self.exit()
