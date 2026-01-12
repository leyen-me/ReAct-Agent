# -*- coding: utf-8 -*-
"""基于 Textual 的界面应用 - 简洁风格"""

from typing import List, Tuple

from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Input,
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

from agent import ReActAgent
from cli.commands import CommandProcessor
from cli.chat_widgets import (
    UserMessage,
    ThinkingMessage,
    ContentMessage,
    ToolMessage,
    SystemMessage,
)
from config import config
from utils import refresh_file_list, get_file_list, search_files


class CommandPaletteScreen(ModalScreen[str]):
    """命令面板对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]
    
    CSS = """
    CommandPaletteScreen {
        align: center middle;
    }
    
    #palette-container {
        width: 60;
        max-height: 20;
        background: #0d1117;
        border: solid #30363d;
        padding: 1 2;
    }
    
    #palette-search {
        width: 100%;
        margin-bottom: 1;
        background: #161b22;
        border: solid #8b5cf6;
    }
    
    #palette-search:focus {
        border: solid #8b5cf6;
    }
    
    #palette-list {
        height: auto;
        max-height: 14;
        background: #0d1117;
    }
    
    #palette-list > .option-list--option-highlighted {
        background: #1f2937;
    }
    """
    
    def __init__(self, commands: List[Tuple[str, str, str]], title: str = "Commands"):
        super().__init__()
        self.commands = commands
        self.title = title
        self.filtered_commands = commands.copy()
    
    def compose(self) -> ComposeResult:
        with Container(id="palette-container"):
            yield Input(placeholder="Type a command...", id="palette-search")
            yield OptionList(
                *[Option(f"{cmd[1]}  [dim]{cmd[2]}[/]", id=cmd[0]) for cmd in self.commands],
                id="palette-list"
            )
    
    def on_mount(self) -> None:
        self.query_one("#palette-search", Input).focus()
    
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
    
    @on(OptionList.OptionSelected, "#palette-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option.id:
            self.dismiss(event.option.id)
    
    @on(Input.Submitted, "#palette-search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
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
        max-height: 24;
        background: #0d1117;
        border: solid #30363d;
        padding: 1 2;
    }
    
    #filepicker-search {
        width: 100%;
        margin-bottom: 1;
        background: #161b22;
        border: solid #22c55e;
    }
    
    #filepicker-search:focus {
        border: solid #22c55e;
    }
    
    #filepicker-list {
        height: auto;
        max-height: 18;
        background: #0d1117;
    }
    
    #filepicker-list > .option-list--option-highlighted {
        background: #1f2937;
    }
    """
    
    def __init__(self, work_dir: str):
        super().__init__()
        self.work_dir = work_dir
        self.files: List[str] = []
    
    def compose(self) -> ComposeResult:
        with Container(id="filepicker-container"):
            yield Input(placeholder="Search files...", id="filepicker-search")
            yield OptionList(id="filepicker-list")
    
    def on_mount(self) -> None:
        self.query_one("#filepicker-search", Input).focus()
        self._load_files("")
    
    def _load_files(self, query: str) -> None:
        option_list = self.query_one("#filepicker-list", OptionList)
        option_list.clear_options()
        
        if query.strip():
            self.files = search_files(self.work_dir, query, limit=50)
        else:
            self.files = get_file_list(self.work_dir)[:30]
        
        for file_path in self.files:
            option_list.add_option(Option(file_path, id=file_path))
    
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
        # margin: 0 2;
    }
    
    #chat-log {
        width: 100%;
        height: auto;
        scrollbar-color: #30363d;
        scrollbar-color-hover: #484f58;
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
        border-left: solid #8b5cf6;
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
        min-height: 1;
        background: #ffffff;
        padding: 0 2;
        border-left: solid #ef4444;
        margin: 1 2 1 2;
        align-vertical: middle;
    }
    
    SystemMessage > Static {
        width: 100%;
        color: #ef4444;
        text-align: left;
        background: transparent;
    }
    
    /* ===== Footer 输入区域 ===== */
    #input-container {
        height: 3;
        background: #f3f3f3;
        margin: 1 2 1 2;
        border-left: ascii #8b5cf6;
        align-vertical: middle;
    }
    
    #user-input {
        width: 100%;
        height: 1;
        background: #f3f3f3;
        border: none;
        color: #303030;
        padding: 0 1;
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
    
    /* ===== 隐藏类 ===== */
    .hidden {
        display: none;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear", "清屏"),
        # Binding("ctrl+p", "open_palette", "命令"),
    ]
    
    def __init__(self, agent: ReActAgent, command_processor: CommandProcessor):
        super().__init__()
        self.agent = agent
        self.command_processor = command_processor
        self.chat_count = 0
        self.is_processing = False
    
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
            with Horizontal(id="input-container"):
                yield Input(id="user-input", placeholder="输入消息... @选择文件 /命令")
            
            # Setting: 底栏
            with Horizontal(id="setting-bar"):
                yield Static(self._get_model_info(), id="setting-left")
                yield Static(
                    "[#3b82f6]ctrl+c[/] quit  [#8b5cf6]ctrl+l[/] clear",
                    id="setting-right"
                )
    
    def _get_title(self) -> str:
        """获取标题"""
        return "[bold]# ReAct Agent[/]"
    
    def _get_stats(self) -> str:
        """获取统计信息"""
        if not hasattr(self.agent, "message_manager"):
            return ""
        
        mm = self.agent.message_manager
        usage = mm.get_token_usage_percent()
        used = mm.max_context_tokens - mm.get_remaining_tokens()
        
        return f"{used:,}  {usage:.0f}% ($0.00)"
    
    def _get_model_info(self) -> str:
        """获取模型信息"""
        model = getattr(config, 'model', 'unknown')
        return f"[#8b5cf6]■[/]  Build  [dim]{model}[/]"
    
    def refresh_header(self) -> None:
        """刷新 Header"""
        try:
            self.query_one("#header-stats", Static).update(self._get_stats())
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
        self.query_one("#user-input", Input).focus()
        refresh_file_list(config.work_dir)
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """监听输入变化"""
        text = event.value
        
        if self.is_processing:
            return
        
        if text.endswith("@"):
            self.set_timer(0.05, self._open_file_picker_from_at)
        elif text == "/":
            self.set_timer(0.05, self._open_palette_from_slash)
    
    def _open_file_picker_from_at(self) -> None:
        input_widget = self.query_one("#user-input", Input)
        current_value = input_widget.value
        if current_value.endswith("@"):
            input_widget.value = current_value[:-1]
        self._open_file_picker()
    
    def _open_palette_from_slash(self) -> None:
        input_widget = self.query_one("#user-input", Input)
        if input_widget.value == "/":
            input_widget.value = ""
        self.action_open_palette()
    
    def _open_file_picker(self) -> None:
        def handle_file_selection(file_path: str | None) -> None:
            if file_path:
                input_widget = self.query_one("#user-input", Input)
                current = input_widget.value
                input_widget.value = f"{current}`{file_path}` "
                input_widget.focus()
        
        self.push_screen(FilePickerScreen(config.work_dir), handle_file_selection)
    
    def action_open_palette(self) -> None:
        commands = [
            ("help", "Help", "Show help"),
            ("status", "Status", "Show context usage"),
            ("messages", "Messages", "Show message history"),
            ("clear", "Clear", "Clear chat"),
            ("file", "File", "Select file"),
            ("exit", "Exit", "Exit app"),
        ]
        
        def handle_command(cmd_id: str | None) -> None:
            if not cmd_id:
                self.query_one("#user-input", Input).focus()
                return
            
            if cmd_id == "help":
                self._show_help()
            elif cmd_id == "status":
                self._show_status()
            elif cmd_id == "messages":
                self._show_messages()
            elif cmd_id == "clear":
                self.action_clear()
            elif cmd_id == "file":
                self._open_file_picker()
            elif cmd_id == "exit":
                self.action_quit()
            else:
                self.query_one("#user-input", Input).focus()
        
        self.push_screen(CommandPaletteScreen(commands, "Commands"), handle_command)
    
    def _show_help(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        help_msg = ContentMessage("[dim]@[/] select file  [dim]/[/] commands", allow_markup=True)
        chat_container.mount(help_msg)
        self._scroll_to_bottom()
        self.query_one("#user-input", Input).focus()
    
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
        
        self.query_one("#user-input", Input).focus()
    
    def _show_messages(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        
        if hasattr(self.agent, "message_manager"):
            messages = self.agent.message_manager.get_messages()
            msg_count = ContentMessage(f"[dim]Messages: {len(messages)}[/]", allow_markup=True)
            chat_container.mount(msg_count)
            self._scroll_to_bottom()
        
        self.query_one("#user-input", Input).focus()
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.is_processing:
            return
        
        message = event.value.strip()
        if not message:
            return
        
        input_widget = self.query_one("#user-input", Input)
        input_widget.value = ""
        
        self.chat_count += 1
        self.add_user_message(message)
        refresh_file_list(config.work_dir)
        
        self.is_processing = True
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
                    if current_content:
                        app.call_from_thread(
                            lambda: app._flush_content(current_section, current_content)
                        )
                        current_content = ""
                    current_section = "reasoning"
                    return
                elif "最终回复" in text:
                    if current_content:
                        app.call_from_thread(
                            lambda: app._flush_content(current_section, current_content)
                        )
                        current_content = ""
                    current_section = "content"
                    return
                elif "工具调用" in text:
                    if current_content:
                        app.call_from_thread(
                            lambda: app._flush_content(current_section, current_content)
                        )
                        current_content = ""
                    current_section = "tool"
                    return
                
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
            
            self.agent.chat(message, output_callback)
            
            if current_content:
                app.call_from_thread(
                    lambda: app._flush_content(current_section, current_content)
                )
                
        except Exception as e:
            app = self.app
            app.call_from_thread(
                lambda: app.add_system_message(f"Error: {e}")
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
        self.is_processing = False
        self.refresh_header()
        self.query_one("#user-input", Input).focus()
    
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
    
    def update_section_content(self, section: str, content: str) -> None:
        if "\n" in content:
            chat_container = self.query_one("#chat-log", Vertical)
            if section == "reasoning":
                msg = ThinkingMessage(content)
                chat_container.mount(msg)
            elif section == "content":
                msg = ContentMessage(content)
                chat_container.mount(msg)
            elif section == "tool":
                msg = ToolMessage(content)
                chat_container.mount(msg)
            self._scroll_to_bottom()
    
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
    
    def action_clear(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        chat_container.remove_children()
        self.query_one("#user-input", Input).focus()
    
    def action_quit(self) -> None:
        self.exit()
