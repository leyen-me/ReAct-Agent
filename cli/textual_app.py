# -*- coding: utf-8 -*-
"""基于 Textual 的界面应用"""

import asyncio
import sys
from io import StringIO
from typing import Optional, List, Tuple
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import (
    Header,
    Footer,
    Input,
    RichLog,
    Static,
)
from textual.containers import (
    Horizontal,
    Vertical,
    Container,
    ScrollableContainer,
)
from textual.binding import Binding
from textual.message import Message
from textual import events
from textual.worker import Worker
from textual import on
from rich.text import Text
from rich.panel import Panel
from rich.markdown import Markdown

from agent import ReActAgent
from cli.commands import CommandProcessor
from config import config
from utils import refresh_file_list, get_file_list, search_files


class ChatMessage(Static):
    """聊天消息组件"""
    
    def __init__(self, role: str, content: str, **kwargs):
        super().__init__(**kwargs)
        self.role = role
        self.content = content
    
    def compose(self) -> ComposeResult:
        role_color = {
            "user": "cyan",
            "assistant": "green",
            "system": "yellow",
            "tool": "magenta",
        }.get(self.role.lower(), "white")
        
        role_text = Text(f"[{self.role.upper()}]", style=f"bold {role_color}")
        content_text = Text(self.content)
        
        # 如果是 markdown 格式，尝试渲染
        if self.role == "assistant" and self.content:
            try:
                # 使用 Rich 的 Markdown 渲染
                panel = Panel(
                    Markdown(self.content),
                    title=f"[{role_color}]{self.role.upper()}[/]",
                    border_style=role_color,
                )
                yield Static(panel, classes="message")
            except:
                # 如果渲染失败，使用纯文本
                yield Static(f"{role_text} {content_text}", classes="message")
        else:
            yield Static(f"{role_text} {content_text}", classes="message")


class StatusBar(Static):
    """状态栏组件"""
    
    def __init__(self, agent: ReActAgent, **kwargs):
        super().__init__(**kwargs)
        self.agent = agent
        self.update_status()
    
    def update_status(self) -> None:
        """更新状态显示"""
        if not hasattr(self.agent, "message_manager"):
            self.update("状态: 不可用")
            return
        
        message_manager = self.agent.message_manager
        usage_percent = message_manager.get_token_usage_percent()
        remaining_tokens = message_manager.get_remaining_tokens()
        used_tokens = message_manager.max_context_tokens - remaining_tokens
        max_tokens = message_manager.max_context_tokens
        
        status_text = (
            f"上下文: {usage_percent:.1f}% "
            f"({used_tokens:,}/{max_tokens:,} tokens) | "
            f"剩余: {remaining_tokens:,} tokens"
        )
        self.update(status_text)


class ReActAgentApp(App):
    """ReAct Agent Textual 应用"""
    
    CSS = """
    Screen {
        background: $surface;
    }
    
    #chat_area {
        height: 1fr;
        border: solid $primary;
        padding: 1;
    }
    
    #input_area {
        height: 3;
        border: solid $primary;
        padding: 1;
    }
    
    .message {
        margin: 1;
        padding: 1;
    }
    
    #status_bar {
        height: 1;
        background: $panel;
        padding: 1;
    }
    
    #completion_list {
        height: 10;
        border: solid $accent;
        background: $panel;
        padding: 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear", "清屏"),
        Binding("tab", "complete", "补全"),
        Binding("escape", "cancel_completion", "取消补全"),
    ]
    
    def __init__(self, agent: ReActAgent, command_processor: CommandProcessor):
        super().__init__()
        self.agent = agent
        self.command_processor = command_processor
        self.chat_count = 0
        self.current_completions: List[str] = []
        self.completion_index = 0
        self.showing_completions = False
        self.current_input = ""
        self.is_processing = False
    
    def compose(self) -> ComposeResult:
        """组合应用界面"""
        yield Header(show_clock=True)
        
        with Vertical():
            with ScrollableContainer(id="chat_area"):
                yield RichLog(id="chat_log", markup=True, wrap=True)
            
            with Container(id="completion_list", classes="hidden"):
                yield RichLog(id="completion_log", markup=True)
            
            with Horizontal():
                yield Input(
                    id="input",
                    placeholder="输入消息，@ 补全文件，/ 执行命令",
                )
            
            yield StatusBar(self.agent, id="status_bar")
        
        yield Footer()
    
    def on_mount(self) -> None:
        """应用挂载时的初始化"""
        self.query_one("#input", Input).focus()
        self.refresh_status()
        # 启动时刷新文件列表
        refresh_file_list(config.work_dir)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理输入提交"""
        if self.is_processing:
            return
        
        message = event.value.strip()
        if not message:
            return
        
        # 清空输入框
        input_widget = self.query_one("#input", Input)
        input_widget.value = ""
        self.hide_completions()
        
        # 处理命令（需要捕获输出）
        if message.startswith("/"):
            # 重定向命令输出到界面
            old_stdout = sys.stdout
            output_buffer = StringIO()
            sys.stdout = output_buffer
            
            try:
                is_command = self.command_processor.process_command(message)
                if is_command:
                    output_text = output_buffer.getvalue()
                    if output_text:
                        self.add_system_message(output_text.strip())
                    if message.startswith("/exit"):
                        self.exit()
                    return
            finally:
                sys.stdout = old_stdout
        
        # 处理聊天
        if message:
            self.chat_count += 1
            self.add_user_message(message)
            # 刷新文件列表
            refresh_file_list(config.work_dir)
            # 使用 Worker 处理聊天（避免阻塞 UI）
            self.is_processing = True
            # 使用 lambda 包装函数调用
            self.worker = self.run_worker(
                lambda: self.handle_chat(message),
                thread=True,
                name="chat_worker",
            )
    
    def handle_chat(self, message: str) -> None:
        """处理聊天（在 Worker 线程中运行）"""
        try:
            # 获取 App 实例
            app = self.app
            
            # 定义输出回调，使用 App 的 call_from_thread 在主线程中更新 UI
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
                        lambda: app.query_one("#chat_log", RichLog).write(
                            f"[dim]{'='*config.log_separator_length} 模型思考 {'='*config.log_separator_length}[/]\n"
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
                        lambda: app.query_one("#chat_log", RichLog).write(
                            f"[green]{'='*config.log_separator_length} 最终回复 {'='*config.log_separator_length}[/]\n"
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
                        lambda: app.query_one("#chat_log", RichLog).write(
                            f"[magenta]{'='*config.log_separator_length} 工具调用 {'='*config.log_separator_length}[/]\n"
                        )
                    )
                    return
                
                # 累积内容并定期更新
                if current_section:
                    current_content += text
                    if end_newline:
                        current_content += "\n"
                    
                    # 定期更新显示（每 50 个字符或遇到换行）
                    if end_newline or len(current_content) >= 50:
                        app.call_from_thread(
                            lambda: app._update_content(current_section, current_content)
                        )
                        current_content = ""
                else:
                    # 没有明确部分，直接输出
                    app.call_from_thread(
                        lambda: app._add_output(text, end_newline)
                    )
            
            # 在线程中运行 agent.chat
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
            app.call_from_thread(
                lambda: app._finish_chat()
            )
    
    def _finish_chat(self) -> None:
        """完成聊天处理"""
        self.is_processing = False
        self.refresh_status()
        self.query_one("#input", Input).focus()
    
    def _flush_content(self, section: str, content: str) -> None:
        """刷新内容（从 Worker 线程调用）"""
        self.flush_current_content(section, content)
    
    def _update_content(self, section: str, content: str) -> None:
        """更新内容（从 Worker 线程调用）"""
        self.update_section_content(section, content)
    
    def _add_output(self, text: str, end_newline: bool) -> None:
        """添加输出（从 Worker 线程调用）"""
        self.add_assistant_output(text, end_newline)
    
    def flush_current_content(self, section: str, content: str) -> None:
        """刷新当前部分的内容"""
        if not content.strip():
            return
        
        chat_log = self.query_one("#chat_log", RichLog)
        if section == "reasoning":
            chat_log.write(f"[dim]💭 模型思考:[/]\n{content}")
        elif section == "content":
            chat_log.write(f"[green]🤖 助手回复:[/]\n{content}")
        elif section == "tool":
            chat_log.write(f"[magenta]🔧 工具调用:[/]\n{content}")
        else:
            chat_log.write(content)
    
    def update_section_content(self, section: str, content: str) -> None:
        """更新部分内容（用于实时显示）"""
        # 由于 RichLog 不支持部分更新，我们每次显示完整内容
        # 为了更好的体验，只在换行时更新
        if "\n" in content:
            chat_log = self.query_one("#chat_log", RichLog)
            # 清除之前的内容并重新显示（简单实现）
            # 实际应用中可以使用更复杂的逻辑来只更新最后一行
            if section == "reasoning":
                chat_log.write(f"[dim]{content}[/]")
            elif section == "content":
                chat_log.write(f"[green]{content}[/]")
            elif section == "tool":
                chat_log.write(f"[magenta]{content}[/]")
    
    def add_user_message(self, message: str) -> None:
        """添加用户消息"""
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.write(f"[cyan]👤 USER[/]: {message}\n")
    
    def add_assistant_output(self, text: str, end_newline: bool = True) -> None:
        """添加助手输出"""
        chat_log = self.query_one("#chat_log", RichLog)
        if end_newline:
            chat_log.write(text)
        else:
            # 对于流式输出，我们需要累积
            # 但 RichLog 不支持追加，所以先简单处理
            chat_log.write(text)
    
    def add_system_message(self, message: str) -> None:
        """添加系统消息"""
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.write(f"[yellow]SYSTEM[/]: {message}")
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """处理输入变化，用于补全"""
        text = event.value
        self.current_input = text
        
        # 如果输入为空或正在处理，不显示补全
        if not text or self.is_processing:
            self.hide_completions()
            return
        
        # 检查是否需要补全
        completions = self.get_completions(text)
        if completions:
            self.show_completions(completions)
        else:
            self.hide_completions()
    
    def get_completions(self, text: str) -> List[str]:
        """获取补全列表"""
        completions = []
        
        # 命令补全（以 / 开头）
        if text.startswith("/"):
            command_names = self.command_processor.get_command_names()
            query = text[1:].lower()
            for cmd in command_names:
                if cmd[1:].lower().startswith(query):
                    completions.append(cmd)
        
        # 文件补全（包含 @）
        elif "@" in text:
            last_at_index = text.rfind("@")
            query = text[last_at_index + 1:]
            
            if query.strip() == "":
                files = get_file_list(config.work_dir)[:20]
            else:
                files = search_files(config.work_dir, query, limit=50)
            
            for file_path in files:
                # 构建补全文本：保留 @ 之前的内容，替换 @ 之后的内容
                before_at = text[:last_at_index + 1]
                completion_text = f"{before_at}`{file_path}`"
                completions.append(completion_text)
        
        return completions[:20]  # 限制最多 20 个
    
    def show_completions(self, completions: List[str]) -> None:
        """显示补全列表"""
        if not completions:
            self.hide_completions()
            return
        
        self.current_completions = completions
        self.completion_index = 0
        self.showing_completions = True
        
        completion_log = self.query_one("#completion_log", RichLog)
        completion_log.clear()
        
        for i, comp in enumerate(completions[:10]):  # 最多显示 10 个
            style = "bold cyan" if i == 0 else "white"
            completion_log.write(f"[{style}]{comp}[/]")
        
        completion_container = self.query_one("#completion_list", Container)
        completion_container.remove_class("hidden")
    
    def hide_completions(self) -> None:
        """隐藏补全列表"""
        self.showing_completions = False
        completion_container = self.query_one("#completion_list", Container)
        completion_container.add_class("hidden")
    
    def action_complete(self) -> None:
        """处理 Tab 补全"""
        if not self.showing_completions or not self.current_completions:
            return
        
        # 选择当前补全项
        selected = self.current_completions[self.completion_index]
        input_widget = self.query_one("#input", Input)
        input_widget.value = selected
        self.hide_completions()
    
    def action_cancel_completion(self) -> None:
        """取消补全"""
        self.hide_completions()
    
    def action_clear(self) -> None:
        """清屏"""
        chat_log = self.query_one("#chat_log", RichLog)
        chat_log.clear()
    
    def refresh_status(self) -> None:
        """刷新状态栏"""
        status_bar = self.query_one("#status_bar", StatusBar)
        status_bar.update_status()
    
    def action_quit(self) -> None:
        """退出应用"""
        self.exit()


# 为了兼容原有的 agent.chat 输出，我们需要修改 agent.py
# 或者创建一个包装器来捕获输出
# 但更好的方式是修改 agent.chat 接受一个输出回调
