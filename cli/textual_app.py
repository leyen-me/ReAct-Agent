# -*- coding: utf-8 -*-
"""基于 Textual 的界面应用 - 简洁风格"""

from typing import List, Tuple, Dict, Any, Set
import json
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import (
    Static,
    Input,
    TextArea,
    OptionList,
    DirectoryTree,
    Button,
    Tree,
)
from textual.widgets.option_list import Option
from textual.widgets.tree import TreeNode
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
from utils.history_manager import HistoryManager, ChatHistory
from logger_config import get_all_log_files
from task_planner import StepStatus


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
        background: rgba(0, 0, 0, 0.7);
    }
    
    #palette-container {
        width: 70;
        max-height: 20;
        background: #2d2d2d;
        border: none;
        padding: 0;
    }
    
    #palette-header {
        height: 3;
        background: #2d2d2d;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #404040;
        align-vertical: middle;
    }
    
    #palette-title {
        width: 1fr;
        color: #ffffff;
        text-style: bold;
    }
    
    #palette-hint {
        width: auto;
        color: #a0a0a0;
    }
    
    #palette-content {
        padding: 1 2;
    }
    
    #palette-search {
        width: 100%;
        height: 1;
        margin-bottom: 1;
        background: #2d2d2d;
        border: none;
        color: #ffffff;
        align-vertical: middle;
    }
    
    #palette-search:focus {
        border: none;
    }
    
    #palette-list {
        height: auto;
        max-height: 14;
        background: #1e1e1e;
        border: none;
    }
    
    #palette-list > .option-list--option-highlighted {
        background: #404040;
    }
    
    #palette-list > .option-list--option {
        color: #ffffff;
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


class DirectoryTreeCache:
    """DirectoryTree 展开状态缓存管理器（内存缓存）"""
    
    def __init__(self):
        """初始化缓存管理器"""
        self.cache: Dict[str, Set[str]] = {}  # {work_dir: {expanded_paths}}
    
    def get_expanded_paths(self, work_dir: str) -> Set[str]:
        """获取指定工作目录的展开路径集合"""
        work_dir = str(Path(work_dir).resolve())
        return self.cache.get(work_dir, set()).copy()
    
    def set_expanded_paths(self, work_dir: str, expanded_paths: Set[str]) -> None:
        """设置指定工作目录的展开路径集合"""
        work_dir = str(Path(work_dir).resolve())
        self.cache[work_dir] = expanded_paths
    
    def add_expanded_path(self, work_dir: str, path: str) -> None:
        """添加一个展开的路径"""
        work_dir = str(Path(work_dir).resolve())
        if work_dir not in self.cache:
            self.cache[work_dir] = set()
        self.cache[work_dir].add(str(Path(path).resolve()))
    
    def remove_expanded_path(self, work_dir: str, path: str) -> None:
        """移除一个展开的路径"""
        work_dir = str(Path(work_dir).resolve())
        if work_dir in self.cache:
            self.cache[work_dir].discard(str(Path(path).resolve()))


class CachedDirectoryTree(DirectoryTree):
    """带缓存功能的 DirectoryTree，可以记住展开状态"""
    
    def __init__(self, path: str, cache: DirectoryTreeCache | None = None, **kwargs):
        """
        初始化带缓存的 DirectoryTree
        
        Args:
            path: 目录路径
            cache: 缓存管理器实例，如果为 None 则创建新的实例
            **kwargs: 传递给 DirectoryTree 的其他参数
        """
        super().__init__(path, **kwargs)
        self.cache = cache or DirectoryTreeCache()
        self.work_dir = str(Path(path).resolve())
        self._restoring_expanded = False  # 标记是否正在恢复展开状态
    
    def on_mount(self) -> None:
        """挂载时恢复展开状态"""
        super().on_mount()
        # 延迟恢复展开状态，确保树已完全加载
        self.set_timer(0.1, self._restore_expanded_state)
    
    def _restore_expanded_state(self) -> None:
        """恢复展开状态"""
        if self._restoring_expanded:
            return
        
        self._restoring_expanded = True
        try:
            expanded_paths = self.cache.get_expanded_paths(self.work_dir)
            if not expanded_paths:
                return
            
            # 遍历所有节点，展开缓存的路径
            def expand_nodes(node: TreeNode) -> None:
                try:
                    # DirectoryTree 的节点数据是 Path 对象
                    if hasattr(node.data, 'path'):
                        node_path = str(Path(node.data.path).resolve())
                    elif isinstance(node.data, Path):
                        node_path = str(node.data.resolve())
                    else:
                        return
                    
                    if node_path in expanded_paths:
                        if not node.is_expanded:
                            node.expand()
                    
                    # 递归处理子节点（需要等待子节点加载）
                    # 延迟处理子节点，因为展开节点后子节点可能还没加载
                    if node.is_expanded:
                        def expand_children_delayed():
                            self._expand_children(node, expanded_paths)
                        self.set_timer(0.05, expand_children_delayed)
                except Exception:
                    pass
            
            # 从根节点开始恢复
            root = self.root
            if root:
                expand_nodes(root)
        finally:
            # 延迟清除标记，确保所有节点都已处理
            def clear_restoring_flag():
                self._restoring_expanded = False
            self.set_timer(0.5, clear_restoring_flag)
    
    def _expand_children(self, node: TreeNode, expanded_paths: Set[str]) -> None:
        """递归展开子节点"""
        try:
            for child in node.children:
                if hasattr(child.data, 'path'):
                    child_path = str(Path(child.data.path).resolve())
                elif isinstance(child.data, Path):
                    child_path = str(child.data.resolve())
                else:
                    continue
                
                if child_path in expanded_paths:
                    if not child.is_expanded:
                        child.expand()
                    # 继续递归处理子节点
                    if child.is_expanded:
                        def expand_child_delayed():
                            self._expand_children(child, expanded_paths)
                        self.set_timer(0.05, expand_child_delayed)
        except Exception:
            pass
    
    @on(Tree.NodeExpanded)
    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """处理树节点展开事件"""
        if self._restoring_expanded:
            return
        
        try:
            node = event.node
            if hasattr(node.data, 'path'):
                path = str(Path(node.data.path).resolve())
            elif isinstance(node.data, Path):
                path = str(node.data.resolve())
            else:
                return
            
            self.cache.add_expanded_path(self.work_dir, path)
        except Exception:
            pass
    
    @on(Tree.NodeCollapsed)
    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        """处理树节点折叠事件"""
        if self._restoring_expanded:
            return
        
        try:
            node = event.node
            if hasattr(node.data, 'path'):
                path = str(Path(node.data.path).resolve())
            elif isinstance(node.data, Path):
                path = str(node.data.resolve())
            else:
                return
            
            self.cache.remove_expanded_path(self.work_dir, path)
        except Exception:
            pass


class FilePickerScreen(ModalScreen[str]):
    """文件选择对话框 - 使用带缓存的 DirectoryTree"""
    
    # 共享的缓存管理器实例
    _cache: DirectoryTreeCache | None = None
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("enter", "select_file", "选择文件", show=False),
    ]
    
    CSS = """
    FilePickerScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    
    #filepicker-container {
        width: 80;
        height: 24;
        background: #2d2d2d;
        border: none;
        padding: 0;
    }
    
    #filepicker-header {
        height: 3;
        background: #2d2d2d;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #404040;
        align-vertical: middle;
    }
    
    #filepicker-title {
        width: 1fr;
        color: #ffffff;
        text-style: bold;
    }
    
    #filepicker-hint {
        width: auto;
        color: #a0a0a0;
    }
    
    #filepicker-content {
        height: 1fr;
        padding: 1;
    }
    
    #filepicker-footer {
        height: 3;
        padding: 0 2;
        border-top: solid #404040;
        align-vertical: middle;
    }
    
    /* DirectoryTree 基础样式 */
    #directory-tree {
        height: 100%;
        width: 100%;
        background: #1e1e1e;
        border: none;
        padding: 1;
        scrollbar-color: #404040;
        scrollbar-color-hover: #505050;
        scrollbar-size: 0 1;
    }
    
    /* 文件夹样式 - 使用紫色主题色 */
    #directory-tree .directory-tree--folder {
        color: #8b5cf6;
    }
    
    /* 文件样式 */
    #directory-tree .directory-tree--file {
        color: #ffffff;
    }
    
    /* 文件扩展名样式 */
    #directory-tree .directory-tree--extension {
        color: #a0a0a0;
    }
    
    /* 隐藏文件样式 */
    #directory-tree .directory-tree--hidden {
        color: #808080;
        opacity: 0.7;
    }
    
    /* 选中/光标所在节点的高亮背景 */
    #directory-tree .tree--highlight-line {
        background: #404040;
    }
    
    /* 选中/光标所在节点的文字样式 */
    #directory-tree .tree--cursor {
        background: #404040;
    }
    
    #directory-tree .tree--cursor .tree--label {
        color: #8b5cf6;
        text-style: bold;
    }
    
    /* 选中项中的文件夹和文件样式 */
    #directory-tree .tree--cursor.directory-tree--folder {
        color: #7c3aed;
    }
    
    #directory-tree .tree--cursor.directory-tree--file {
        color: #8b5cf6;
    }
    
    /* 引导线样式 - 使用深灰色 */
    #directory-tree .tree--guides {
        color: #404040;
    }
    
    /* 悬停时的引导线 */
    #directory-tree .tree--guides-hover {
        color: #505050;
    }
    
    /* 选中项的引导线 */
    #directory-tree .tree--guides-selected {
        color: #8b5cf6;
    }
    
    /* 标签文字基础样式 */
    #directory-tree .tree--label {
        color: #ffffff;
    }
    
    /* 高亮节点样式 */
    #directory-tree .tree--highlight {
        background: #2d2d2d;
    }
    
    #select-button {
        margin-left: 1;
    }
    """
    
    def __init__(self, work_dir: str):
        super().__init__()
        self.work_dir = work_dir
        self.selected_path: str | None = None
        # 使用共享的缓存管理器
        if FilePickerScreen._cache is None:
            FilePickerScreen._cache = DirectoryTreeCache()
    
    def compose(self) -> ComposeResult:
        from pathlib import Path
        work_path = Path(self.work_dir).resolve()
        
        with Container(id="filepicker-container"):
            with Horizontal(id="filepicker-header"):
                yield Static("选择文件", id="filepicker-title")
                yield Static("[dim]ESC[/] 退出  [dim]双击/Enter[/] 选择", id="filepicker-hint")
            with Container(id="filepicker-content"):
                yield CachedDirectoryTree(str(work_path), cache=FilePickerScreen._cache, id="directory-tree")
            with Horizontal(id="filepicker-footer"):
                yield Static("", id="selected-path")
                yield Button("选择", id="select-button", variant="primary")
    
    def on_mount(self) -> None:
        """挂载时聚焦到 DirectoryTree"""
        directory_tree = self.query_one("#directory-tree", CachedDirectoryTree)
        directory_tree.focus()
    
    @on(CachedDirectoryTree.FileSelected)
    def on_file_selected(self, event: CachedDirectoryTree.FileSelected) -> None:
        """处理文件选择事件（双击文件时直接选择并关闭）"""
        from pathlib import Path
        try:
            work_dir_path = Path(self.work_dir).resolve()
            file_path = Path(event.path).resolve()
            # 如果是文件，直接选择并关闭弹窗
            if file_path.is_file():
                self.selected_path = event.path
                self._dismiss_with_path(event.path)
            else:
                # 如果是目录，只更新显示，不关闭
                self.selected_path = event.path
                selected_path_widget = self.query_one("#selected-path", Static)
                selected_path_widget.update(f"[dim]已选择目录:[/] {event.path}")
        except Exception:
            # 如果出错，也尝试关闭
            self.selected_path = event.path
            self._dismiss_with_path(event.path)
    
    @on(Button.Pressed, "#select-button")
    def on_select_button_pressed(self) -> None:
        """处理选择按钮点击"""
        if self.selected_path:
            self._dismiss_with_path(self.selected_path)
    
    def action_select_file(self) -> None:
        """处理 Enter 键选择文件"""
        if self.selected_path:
            self._dismiss_with_path(self.selected_path)
    
    def _dismiss_with_path(self, path: str) -> None:
        """使用路径关闭对话框"""
        from pathlib import Path
        try:
            work_dir_path = Path(self.work_dir).resolve()
            file_path = Path(path).resolve()
            if file_path.is_file():
                # 计算相对路径
                try:
                    relative_path = file_path.relative_to(work_dir_path)
                    self.dismiss(str(relative_path))
                except ValueError:
                    # 如果文件不在工作目录内，使用绝对路径
                    self.dismiss(str(file_path))
            else:
                # 如果是目录，不关闭对话框，让用户继续选择
                pass
        except Exception:
            # 如果出错，直接使用原始路径
            self.dismiss(path)


class PlanViewerScreen(ModalScreen[None]):
    """计划查看对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
    ]
    
    CSS = """
    PlanViewerScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    
    #planviewer-container {
        width: 90%;
        height: 85%;
        background: #2d2d2d;
        border: none;
        padding: 0;
    }
    
    #planviewer-header {
        height: 3;
        background: #2d2d2d;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #404040;
        align-vertical: middle;
    }
    
    #planviewer-title {
        width: 1fr;
        color: #ffffff;
        text-style: bold;
    }
    
    #planviewer-hint {
        width: auto;
        color: #a0a0a0;
    }
    
    #planviewer-content {
        height: 1fr;
        padding: 1 2;
        background: #1e1e1e;
        border: none;
        overflow-y: auto;
        scrollbar-color: #404040;
        scrollbar-color-hover: #505050;
        scrollbar-size: 0 1;
    }
    
    #planviewer-text {
        width: 100%;
        height: auto;
        background: #1e1e1e;
        border: none;
        color: #ffffff;
    }
    """
    
    def __init__(self, plan):
        super().__init__()
        self.plan = plan
    
    def compose(self) -> ComposeResult:
        with Container(id="planviewer-container"):
            with Horizontal(id="planviewer-header"):
                yield Static("📋 任务计划详情", id="planviewer-title")
                yield Static("[dim]ESC[/] 关闭", id="planviewer-hint")
            with ScrollableContainer(id="planviewer-content"):
                yield Static("", id="planviewer-text", markup=True)
    
    def on_mount(self) -> None:
        plan_content = self._format_plan_content()
        static_widget = self.query_one("#planviewer-text", Static)
        static_widget.update(plan_content)
    
    def _format_plan_content(self) -> str:
        """格式化计划内容"""
        plan = self.plan
        progress = plan.get_progress()
        
        # 构建计划显示内容
        plan_lines = [
            f"[bold]📋 任务计划[/bold]",
            f"[dim]任务描述:[/] {plan.task_description}",
            f"[dim]创建时间:[/] {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"[bold]进度概览[/bold]",
            f"  总步骤: {progress['total']}",
            f"  ✅ 已完成: {progress['completed']}",
            f"  🔄 执行中: {progress['in_progress']}",
            f"  ⏳ 待执行: {progress['pending']}",
            f"  ❌ 失败: {progress['failed']}",
            f"  完成度: {progress['progress_percent']:.1f}%",
            "",
            f"[bold]执行步骤[/bold]",
        ]
        
        # 添加每个步骤的详细信息
        for step in plan.steps:
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }.get(step.status, "❓")
            
            # 根据状态设置颜色
            if step.status == StepStatus.COMPLETED:
                step_line = f"  {status_icon} [#22c55e]步骤 {step.step_number}:[/] {step.description}"
            elif step.status == StepStatus.FAILED:
                step_line = f"  {status_icon} [#ef4444]步骤 {step.step_number}:[/] {step.description}"
            elif step.status == StepStatus.IN_PROGRESS:
                step_line = f"  {status_icon} [#3b82f6]步骤 {step.step_number}:[/] {step.description}"
            else:
                step_line = f"  {status_icon} [dim]步骤 {step.step_number}:[/] {step.description}"
            
            plan_lines.append(step_line)
            
            # 显示预期工具
            if step.expected_tools:
                plan_lines.append(f"    [dim]工具:[/] {', '.join(step.expected_tools)}")
            
            # 显示结果或错误
            if step.status == StepStatus.COMPLETED and step.result:
                result_display = step.result[:300] + "..." if len(step.result) > 300 else step.result
                plan_lines.append(f"    [#22c55e]✓ 结果:[/] {result_display}")
            elif step.status == StepStatus.FAILED and step.error:
                plan_lines.append(f"    [#ef4444]✗ 错误:[/] {step.error}")
            
            # 显示时间信息
            if step.start_time:
                plan_lines.append(f"    [dim]开始:[/] {step.start_time.strftime('%H:%M:%S')}")
            if step.end_time:
                plan_lines.append(f"    [dim]结束:[/] {step.end_time.strftime('%H:%M:%S')}")
                if step.start_time:
                    duration = (step.end_time - step.start_time).total_seconds()
                    plan_lines.append(f"    [dim]耗时:[/] {duration:.1f}s")
            
            plan_lines.append("")  # 空行分隔
        
        return "\n".join(plan_lines)


class LogViewerScreen(ModalScreen[None]):
    """日志查看对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("tab", "toggle_focus", "切换焦点"),
    ]
    
    CSS = """
    LogViewerScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    
    #logviewer-container {
        width: 90%;
        height: 85%;
        background: #2d2d2d;
        border: none;
        padding: 0;
    }
    
    #logviewer-header {
        height: 3;
        background: #2d2d2d;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #404040;
        align-vertical: middle;
    }
    
    #logviewer-title {
        width: 1fr;
        color: #ffffff;
        text-style: bold;
    }
    
    #logviewer-hint {
        width: auto;
        color: #a0a0a0;
    }
    
    #logviewer-content {
        height: 1fr;
        padding: 0;
    }
    
    #logviewer-file-list {
        width: 28;
        height: 100%;
        background: #1e1e1e;
        border: none;
        padding: 1 2;
    }
    
    #logviewer-file-list > .option-list--option-highlighted {
        background: #404040;
    }
    
    #logviewer-file-list > .option-list--option {
        color: #ffffff;
    }
    
    #logviewer-text {
        width: 1fr;
        height: 100%;
        background: #1e1e1e;
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


class HistoryScreen(ModalScreen[ChatHistory]):
    """历史记录选择对话框"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "关闭"),
        Binding("tab", "toggle_focus", "切换焦点"),
    ]
    
    CSS = """
    HistoryScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    
    #history-container {
        width: 80;
        height: 24;
        background: #2d2d2d;
        border: none;
        padding: 0;
    }
    
    #history-header {
        height: 3;
        background: #2d2d2d;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #404040;
        align-vertical: middle;
    }
    
    #history-title {
        width: 1fr;
        color: #ffffff;
        text-style: bold;
    }
    
    #history-hint {
        width: auto;
        color: #a0a0a0;
    }
    
    #history-content {
        height: 1fr;
        padding: 1 2;
    }
    
    #history-search {
        width: 100%;
        height: 1;
        margin-bottom: 1;
        background: #2d2d2d;
        border: none;
        color: #ffffff;
        align-vertical: middle;
    }
    
    #history-search:focus {
        border: none;
    }
    
    #history-list {
        height: auto;
        max-height: 16;
        background: #1e1e1e;
        border: none;
    }
    
    #history-list > .option-list--option-highlighted {
        background: #404040;
    }
    
    #history-list > .option-list--option {
        color: #ffffff;
    }
    """
    
    def __init__(self, history_manager: HistoryManager):
        super().__init__()
        self.history_manager = history_manager
        self.histories: List[ChatHistory] = []
        self.filtered_histories: List[ChatHistory] = []
        self.focus_on_input = True
    
    def compose(self) -> ComposeResult:
        with Container(id="history-container"):
            with Horizontal(id="history-header"):
                yield Static("📚 历史记录", id="history-title")
                yield Static("[dim]ESC[/] 退出  [dim]Enter[/] 加载", id="history-hint")
            with Container(id="history-content"):
                yield Input(placeholder="搜索历史记录...", id="history-search")
                yield OptionList(id="history-list")
    
    def on_mount(self) -> None:
        self._load_histories()
        option_list = self.query_one("#history-list", OptionList)
        # 不自动高亮第一项，让用户明确选择
        # 只在有历史记录时设置 highlighted，但不触发选择事件
        if self.filtered_histories:
            # 延迟设置 highlighted，避免立即触发选择
            def set_highlight():
                option_list.highlighted = 0
            self.set_timer(0.1, set_highlight)
        self.query_one("#history-search", Input).focus()
        self.focus_on_input = True
    
    def _load_histories(self) -> None:
        """加载历史记录"""
        self.histories = self.history_manager.get_all_histories()
        self.filtered_histories = self.histories.copy()
        self._update_list()
    
    def _update_list(self) -> None:
        """更新列表显示"""
        option_list = self.query_one("#history-list", OptionList)
        option_list.clear_options()
        
        if not self.filtered_histories:
            option_list.add_option(Option("无历史记录", id="empty"))
            return
        
        for i, history in enumerate(self.filtered_histories):
            # 格式化显示：标题 | 时间 | Token使用
            from datetime import datetime
            try:
                created_time = datetime.fromisoformat(history.created_at)
                time_str = created_time.strftime("%m-%d %H:%M")
            except:
                time_str = history.created_at[:10] if history.created_at else "未知"
            
            token_info = f"{history.token_usage.get('used', 0):,}/{history.token_usage.get('max', 0):,}"
            token_percent = history.token_usage.get('percent', 0.0)
            
            display_text = f"{history.title}  [dim]| {time_str} | Token: {token_info} ({token_percent:.0f}%)[/]"
            # 使用历史记录对象作为 id（通过序列化）
            import json
            history_id = json.dumps({"index": i}, ensure_ascii=False)
            option_list.add_option(Option(display_text, id=history_id))
        
        if self.filtered_histories:
            option_list.highlighted = 0
    
    @on(Input.Changed, "#history-search")
    def filter_histories(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        
        if not query:
            self.filtered_histories = self.histories.copy()
        else:
            self.filtered_histories = [
                h for h in self.histories
                if query in h.title.lower() or query in h.created_at.lower()
            ]
        
        self._update_list()
    
    @on(OptionList.OptionSelected, "#history-list")
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        """处理列表项选择（双击时触发）"""
        if event.option.id and event.option.id != "empty":
            try:
                import json
                data = json.loads(event.option.id)
                index = data.get("index", 0)
                if 0 <= index < len(self.filtered_histories):
                    # 用户明确选择了记录，加载它
                    self.dismiss(self.filtered_histories[index])
            except (ValueError, json.JSONDecodeError, KeyError):
                pass
    
    @on(Input.Submitted, "#history-search")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        # 搜索框提交时，将焦点切换到列表，让用户选择
        # 不要自动选择第一条，让用户明确选择
        option_list = self.query_one("#history-list", OptionList)
        if self.filtered_histories:
            option_list.focus()
            if option_list.highlighted is None:
                option_list.highlighted = 0
            self.focus_on_input = False
            event.prevent_default()
    
    @on(Key)
    def on_key(self, event: Key) -> None:
        """处理按键事件"""
        focused = self.focused
        option_list = self.query_one("#history-list", OptionList)
        
        if isinstance(focused, Input):
            # 输入框获得焦点时，上下键操作列表
            if event.key == "up":
                if self.filtered_histories:
                    option_list.focus()
                    current = option_list.highlighted or 0
                    option_list.highlighted = max(0, current - 1)
                    self.focus_on_input = False
                    event.prevent_default()
            elif event.key == "down":
                if self.filtered_histories:
                    option_list.focus()
                    current = option_list.highlighted or 0
                    option_list.highlighted = min(len(self.filtered_histories) - 1, current + 1)
                    self.focus_on_input = False
                    event.prevent_default()
            elif event.key == "tab":
                self.action_toggle_focus()
                event.prevent_default()
        elif isinstance(focused, OptionList):
            if event.key == "enter":
                highlighted = option_list.highlighted
                if highlighted is not None and self.filtered_histories:
                    self.dismiss(self.filtered_histories[highlighted])
                    event.prevent_default()
            elif event.key == "tab":
                self.action_toggle_focus()
                event.prevent_default()
    
    def action_toggle_focus(self) -> None:
        """切换焦点"""
        if self.focus_on_input:
            option_list = self.query_one("#history-list", OptionList)
            if self.filtered_histories:
                option_list.focus()
                if option_list.highlighted is None:
                    option_list.highlighted = 0
                self.focus_on_input = False
        else:
            self.query_one("#history-search", Input).focus()
            self.focus_on_input = True


class ConfigEditScreen(ModalScreen[bool]):
    """配置编辑界面"""
    
    BINDINGS = [
        Binding("escape", "dismiss", "取消"),
        Binding("ctrl+s", "save", "保存"),
    ]
    
    CSS = """
    ConfigEditScreen {
        align: center middle;
        background: rgba(0, 0, 0, 0.7);
    }
    
    #config-container {
        width: 80;
        height: 85%;
        max-height: 85%;
        background: #2d2d2d;
        border: none;
        padding: 0;
    }
    
    #config-header {
        height: 3;
        background: #2d2d2d;
        padding: 0 2;
        margin-top: 1;
        border-bottom: solid #404040;
        align-vertical: middle;
    }
    
    #config-title {
        width: 1fr;
        color: #ffffff;
        text-style: bold;
    }
    
    #config-hint {
        width: auto;
        color: #a0a0a0;
    }
    
    #config-content {
        height: 1fr;
        padding: 1 2;
        background: #1e1e1e;
        border: none;
        overflow-y: auto;
        scrollbar-color: #404040;
        scrollbar-color-hover: #505050;
        scrollbar-size: 0 1;
    }
    
    #config-form {
        width: 100%;
        height: auto;
        background: #1e1e1e;
        border: none;
    }
    
    .config-row {
        height: 3;
        margin-bottom: 1;
        align: left middle;
    }
    
    .config-label {
        width: 25;
        height: 3;
        color: #ffffff;
        text-style: bold;
        margin-right: 1;
        padding: 0;
        content-align: left middle;
        text-align: left;
        align-vertical: middle;
    }
    
    .config-input {
        width: 1fr;
        height: 3;
        background: #2d2d2d;
        border: solid #404040;
        color: #ffffff;
        padding: 0 1;
        margin: 0;
        text-align: left;
        align-vertical: middle;
    }
    
    .config-input:focus {
        border: solid #3b82f6;
    }
    """
    
    def __init__(self):
        super().__init__()
        self.config_data: Dict[str, Any] = {}
        self.input_widgets: Dict[str, Input] = {}
    
    def compose(self) -> ComposeResult:
        from config import Config
        default_os = Config.detect_operating_system()
        
        with Container(id="config-container"):
            with Horizontal(id="config-header"):
                yield Static("⚙️  配置编辑", id="config-title")
                yield Static("[dim]ESC[/] 取消  [dim]Ctrl+S[/] 保存", id="config-hint")
            with ScrollableContainer(id="config-content"):
                with Vertical(id="config-form"):
                    # 模型配置
                    with Horizontal(classes="config-row config-row-planning_model"):
                        yield Static("规划模型", classes="config-label")
                        yield Input(value="deepseek-ai/deepseek-v3.1-terminus", classes="config-input", id="config-planning_model")
                    
                    with Horizontal(classes="config-row config-row-execution_model"):
                        yield Static("执行模型", classes="config-label")
                        yield Input(value="deepseek-ai/deepseek-v3.1-terminus", classes="config-input", id="config-execution_model")
                    
                    with Horizontal(classes="config-row config-row-api_key"):
                        yield Static("API Key", classes="config-label")
                        yield Input(value="", classes="config-input", id="config-api_key", password=True)
                    
                    with Horizontal(classes="config-row config-row-base_url"):
                        yield Static("Base URL", classes="config-label")
                        yield Input(value="https://integrate.api.nvidia.com/v1", classes="config-input", id="config-base_url")
                    
                    # 系统配置
                    with Horizontal(classes="config-row config-row-operating_system"):
                        yield Static("操作系统", classes="config-label")
                        yield Input(value=default_os, classes="config-input", id="config-operating_system")
                    
                    with Horizontal(classes="config-row config-row-work_dir"):
                        yield Static("工作目录", classes="config-label")
                        yield Input(value="", classes="config-input", id="config-work_dir", placeholder="留空使用当前目录")
                    
                    # 命令执行配置
                    with Horizontal(classes="config-row config-row-command_timeout"):
                        yield Static("命令超时(秒)", classes="config-label")
                        yield Input(value="300", classes="config-input", id="config-command_timeout")
                    
                    # 搜索配置
                    with Horizontal(classes="config-row config-row-max_search_results"):
                        yield Static("最大搜索结果", classes="config-label")
                        yield Input(value="50", classes="config-input", id="config-max_search_results")
                    
                    with Horizontal(classes="config-row config-row-max_find_files"):
                        yield Static("最大查找文件数", classes="config-label")
                        yield Input(value="100", classes="config-input", id="config-max_find_files")
                    
                    # 上下文配置
                    with Horizontal(classes="config-row config-row-max_context_tokens"):
                        yield Static("最大上下文Token", classes="config-label")
                        yield Input(value="128000", classes="config-input", id="config-max_context_tokens")
                    
                    # 用户语言偏好
                    with Horizontal(classes="config-row config-row-user_language_preference"):
                        yield Static("用户语言", classes="config-label")
                        yield Input(value="中文", classes="config-input", id="config-user_language_preference")
                    
                    # 日志配置
                    with Horizontal(classes="config-row config-row-log_separator_length"):
                        yield Static("日志分隔符长度", classes="config-label")
                        yield Input(value="20", classes="config-input", id="config-log_separator_length")
                    
                    # 任务规划配置
                    with Horizontal(classes="config-row config-row-enable_task_planning"):
                        yield Static("启用任务规划", classes="config-label")
                        yield Input(value="true", classes="config-input", id="config-enable_task_planning")
                    
                    with Horizontal(classes="config-row config-row-max_plan_steps"):
                        yield Static("最大计划步骤", classes="config-label")
                        yield Input(value="6", classes="config-input", id="config-max_plan_steps")
    
    def on_mount(self) -> None:
        """挂载时加载配置"""
        self._load_config()
        # 聚焦到第一个输入框
        first_input = self.query_one("Input.config-input", Input)
        if first_input:
            first_input.focus()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        from config import Config
        config_file = Config.get_config_file()
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
            except Exception:
                self.config_data = Config.get_default_config()
        else:
            self.config_data = Config.get_default_config()
        
        # 更新所有输入框的值
        for key, value in self.config_data.items():
            input_widget = self.query_one(f"#config-{key}", Input)
            if input_widget:
                if value is None:
                    input_widget.value = ""
                else:
                    input_widget.value = str(value)
    
    def _collect_config(self) -> Dict[str, Any]:
        """收集所有配置值"""
        config = {}
        for key in self.config_data.keys():
            input_widget = self.query_one(f"#config-{key}", Input)
            if input_widget:
                value = input_widget.value.strip()
                if not value:
                    # 空值根据配置项类型处理
                    if key in ["api_key", "work_dir"]:
                        config[key] = None
                    else:
                        # 其他配置项使用默认值
                        from config import Config
                        default_config = Config.get_default_config()
                        config[key] = default_config.get(key)
                else:
                    config[key] = value
        return config
    
    def action_save(self) -> None:
        """保存配置"""
        config = self._collect_config()
        
        # 验证 user_language_preference
        if config.get("user_language_preference") not in ["中文", "English"]:
            self.notify("用户语言必须为 '中文' 或 'English'", severity="error")
            return
        
        # 如果 operating_system 为空，自动检测
        from config import Config
        if not config.get("operating_system"):
            config["operating_system"] = Config.detect_operating_system()
        
        # 保存到文件
        if Config().save_config_file(config):
            self.notify("配置已保存", severity="success")
            self.dismiss(True)
        else:
            self.notify("保存配置失败", severity="error")
    
    def action_dismiss(self) -> None:
        """取消编辑"""
        self.dismiss(False)
    
    @on(Key)
    def on_key(self, event: Key) -> None:
        """处理按键事件"""
        if event.key == "escape":
            self.action_dismiss()
            event.prevent_default()


class ReActAgentApp(App):
    """ReAct Agent Textual 应用 - 简洁风格"""
    
    CSS = """
    /* ===== 全局 - 深色简洁主题 ===== */
    Screen {
        background: #121212;
    }
    
    /* ===== 主布局 ===== */
    #app-layout {
        height: 100%;
        width: 100%;
    }
    
    /* ===== Header ===== */
    #app-header {
        height: 3;
        background: #1e1e1e;
        padding: 0 2;
        border-left: ascii #404040;
        margin: 1 2 1 2;
        align-vertical: middle;
    }
    
    #header-title {
        width: auto;
        color: #ffffff;
        text-style: bold;
    }
    
    #header-plan-status {
        width: 1fr;
        color: #8b5cf6;
        text-align: right;
        text-overflow: ellipsis;
        overflow: hidden;
    }
    
    #header-plan-status:focus {
        text-style: underline;
    }
    
    #header-plan-status.clickable:hover {
        color: #7c3aed;
        text-style: underline;
    }
    
    /* ===== Main 聊天区域 ===== */
    #main-container {
        height: 1fr;
        width: 100%;
        overflow-y: auto;
        scrollbar-color: #404040;
        scrollbar-color-hover: #505050;
        scrollbar-size: 0 1;
    }
    
    #chat-log {
        width: 100%;
        height: auto;
        scrollbar-color: #404040;
        scrollbar-color-hover: #505050;
        scrollbar-size: 0 1;
        background: #121212;
    }
    
    /* ===== 聊天消息组件样式 ===== */
    UserMessage {
        width: 100%;
        height: auto;
        min-height: 3;
        background: #2d2d2d;
        border-left: ascii #8b5cf6;
        margin: 0 2 1 2;
        align-vertical: middle;
    }
    
    UserMessage > Static {
        width: 100%;
        color: #ffffff;
        text-align: left;
        background: transparent;
        padding: 0 2;
    }
    
    ThinkingMessage {
        width: 100%;
        height: auto;
        min-height: 3;
        background: #1e1e1e;
        padding: 0 2;
        border-left: solid #404040;
        margin: 0 2 1 2;
        align-vertical: middle;
    }
    
    ThinkingMessage > Static {
        width: 100%;
        color: #a0a0a0;
        text-style: italic;
        text-align: left;
        background: transparent;
    }
    
    ContentMessage {
        width: 100%;
        height: auto;
        min-height: 1;
        background: #1e1e1e;
        padding: 1 2;
        margin: 0 2 1 2;
        align-vertical: middle;
    }
    
    ContentMessage > Static {
        width: 100%;
        color: #ffffff;
        text-align: left;
        background: transparent;
    }
    
    ToolMessage {
        width: 100%;
        height: auto;
        min-height: 1;
        background: #1e1e1e;
        padding: 1 2;
        border-left: ascii #22c55e;
        margin: 0 2 1 2;
        align-vertical: middle;
    }
    
    ToolMessage > Static {
        width: 100%;
        color: #ffffff;
        text-align: left;
        background: transparent;
    }
    
    SystemMessage {        
        width: 100%;
        height: auto;
        min-height: 3;
        background: #2d2d2d;
        border-left: ascii #ef4444;
        margin: 0 2 1 2;
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
        background: #1e1e1e;
        padding: 0 2;
        margin: 0 2 1 2;
        align-vertical: middle;
        border-left: solid #ef4444;
    }
    
    HistoryMessage > Static {
        width: 100%;
        color: #ffffff;
        text-align: left;
        background: transparent;
    }
    
    /* ===== Footer 输入区域 ===== */
    #input-container {
        height: auto;
        min-height: 3;
        background: #2d2d2d;
        margin: 1 2 1 2;
        border-left: heavy #8b5cf6;
        padding: 0;
    }
    
    #user-input {
        width: 100%;
        height: auto;
        min-height: 1;
        max-height: 10;
        background: #2d2d2d;
        border: none;
        color: #ffffff;
        padding: 0 1;
        margin: 1 0 0 0;
    }
    
    #user-input.placeholder {
        color: #808080;
    }
    
    #input-model-info {
        width: 100%;
        height: 1;
        background: #2d2d2d;
        padding: 0 1;
        margin: 1 0 1 0;
        color: #a0a0a0;
        align-vertical: middle;
    }
    
    #user-input:focus {
        border: none;
    }
    
    /* ===== Setting 底栏 ===== */
    #setting-bar {
        height: 1;
        padding: 0 2;
        margin: 0 2 1 2;
        align-vertical: middle;
    }
    
    #setting-left {
        width: 1fr;
        color: #a0a0a0;
    }
    
    #setting-left > Static {
        color: #a0a0a0;
    }
    
    #setting-right {
        width: auto;
        color: #a0a0a0;
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
        self.current_chat_title: str | None = None  # 当前对话的标题
        self.is_generating_title = False  # 是否正在生成标题
        self.is_loading_history = False  # 是否正在加载历史记录（防止重复保存）
        self.current_history_id: str | None = None  # 当前对话的历史记录 ID
        self._quit_confirmed = False  # Ctrl+C 退出确认状态
        self._quit_timer = None  # 退出确认定时器
        self.status_update_timer = None  # 状态更新定时器（用于实时显示token和耗时）
        # 初始化历史记录管理器
        # 历史记录目录放在项目根目录下，而不是工作目录（workspace）
        import sys
        from pathlib import Path
        # 如果是 PyInstaller 打包后的可执行文件
        if getattr(sys, 'frozen', False):
            # 使用可执行文件所在目录（而不是临时目录）
            project_root = Path(sys.executable).parent
        else:
            # 开发环境：textual_app.py 在 cli/ 目录下，所以需要向上两级到项目根目录
            project_root = Path(__file__).parent.parent
        history_dir = project_root / ".agent_history"
        self.history_manager = HistoryManager(history_dir)
    
    def compose(self) -> ComposeResult:
        """组合应用界面"""
        with Vertical(id="app-layout"):
            # Header
            with Horizontal(id="app-header"):
                yield Static(self._get_title(), id="header-title")
                yield Static("", id="header-plan-status")
            
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
                yield Static(self._get_status_info_with_stats(), id="setting-left")
                yield Static(
                    self._get_shortcuts_info(),
                    id="setting-right"
                )
    
    def _get_title(self) -> str:
        """获取标题"""
        if self.current_chat_title:
            return f"[bold]{self.current_chat_title}[/]"
        elif self.is_generating_title:
            return "[bold]ReAct Agent[/] [dim]生成标题中...[/]"
        else:
            return "[bold]ReAct Agent[/]"
    
    def _get_stats(self) -> str:
        """获取统计信息"""
        if not hasattr(self.agent, "message_manager"):
            return ""
        
        mm = self.agent.message_manager
        usage = mm.get_token_usage_percent()
        used = mm.max_context_tokens - mm.get_remaining_tokens()
        
        return f"Token: {used:,}  Usage: {usage:.0f}%"
    
    def _get_status_info_with_stats(self) -> str:
        """获取状态信息（包含统计信息）"""
        if self.is_processing:
            status = "[#22c55e]●[/] 对话中"
        else:
            status = "[#7d8590]○[/] 空闲"
        
        # 添加统计信息，确保始终显示
        stats = ""
        try:
            if hasattr(self.agent, "message_manager") and self.agent.message_manager is not None:
                mm = self.agent.message_manager
                # 如果正在处理中，使用估算值；否则使用实际值
                if self.is_processing:
                    # 使用估算值（实时更新）
                    usage = mm.get_estimated_token_usage_percent()
                    used = mm.max_context_tokens - mm.get_estimated_remaining_tokens()
                    stats = f"  Token: {used:,} ({usage:.0f}%) [估算]"
                else:
                    # 使用实际值
                    usage = mm.get_token_usage_percent()
                    used = mm.max_context_tokens - mm.get_remaining_tokens()
                    stats = f"  Token: {used:,} ({usage:.0f}%)"
            else:
                # 如果 message_manager 不存在，显示默认值
                stats = "  Token: --"
        except Exception:
            # 如果获取 token 信息出错，显示默认值
            stats = "  Token: --"
        
        # 实时显示当前对话耗时（如果正在对话中）
        if self.is_processing and self.chat_start_time is not None:
            import time
            current_duration = time.time() - self.chat_start_time
            duration = f"  [dim]本轮耗时: {current_duration:.1f}s[/]"
            return f"{status}{stats}{duration}"
        elif self.last_chat_duration is not None:
            duration = f"  [dim]上轮耗时: {self.last_chat_duration:.1f}s[/]"
            return f"{status}{stats}{duration}"
        else:
            return f"{status}{stats}"
    
    def _get_model_info(self) -> str:
        """获取模型信息"""
        execution_model = getattr(config, 'execution_model', 'unknown')
        planning_model = getattr(config, 'planning_model', 'unknown')
        # 如果规划模型和执行模型相同，只显示一个
        if planning_model == execution_model:
            return f"[#8b5cf6]■[/] Build [dim]{execution_model}[/]"
        else:
            return f"[#8b5cf6]■[/] Build [dim]planning:{planning_model} execution:{execution_model}[/]"
    
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
            # 刷新标题
            self.query_one("#header-title", Static).update(self._get_title())
            # 刷新统计信息（现在在 setting-left 中）
            self.query_one("#setting-left", Static).update(self._get_status_info_with_stats())
        except Exception:
            pass
    
    def update_plan_status(self, status: str) -> None:
        """更新规划状态显示"""
        try:
            plan_status_widget = self.query_one("#header-plan-status", Static)
            # 限制长度，超出部分用省略号
            max_length = 60
            if len(status) > max_length:
                status = status[:max_length-3] + "..."
            plan_status_widget.update(status)
            
            # 如果有计划状态文本，添加可点击样式
            if status:
                plan_status_widget.add_class("clickable")
            else:
                plan_status_widget.remove_class("clickable")
        except Exception:
            pass
    
    def refresh_status(self) -> None:
        """刷新状态栏"""
        try:
            # 统一使用包含 token 信息的版本，确保 token 信息一直显示
            self.query_one("#setting-left", Static).update(self._get_status_info_with_stats())
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
        # 延迟刷新状态，确保 token 信息显示（等待 message_manager 初始化）
        self.set_timer(0.2, lambda: self.refresh_status())
    
    @on(Click, "#header-plan-status")
    def on_plan_status_click(self, event: Click) -> None:
        """处理计划状态点击事件"""
        # 检查是否有计划可以显示
        if hasattr(self.agent, "current_plan") and self.agent.current_plan is not None:
            self._open_plan_viewer()
            event.stop()
            return
    
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
            
            # 立即尝试设置光标位置到文本末尾（即使没有焦点）
            def set_cursor_immediately():
                try:
                    # 使用 document.end 获取文档末尾位置
                    end_location = input_widget.document.end
                    input_widget.cursor_location = end_location
                except Exception:
                    # 如果失败，尝试使用 move_cursor
                    try:
                        end_location = input_widget.document.end
                        input_widget.move_cursor(end_location, select=False)
                    except Exception:
                        pass
            
            # 延迟设置光标位置，确保文档已更新
            self.set_timer(0.05, set_cursor_immediately)
            
            # 延迟恢复焦点
            def restore_focus():
                input_widget.focus()
                # 再次确保光标在末尾（因为恢复焦点可能会重置光标）
                def ensure_cursor_end():
                    if input_widget.has_focus and self._programmatic_value_set:
                        try:
                            end_location = input_widget.document.end
                            input_widget.cursor_location = end_location
                        except Exception:
                            try:
                                end_location = input_widget.document.end
                                input_widget.move_cursor(end_location, select=False)
                            except Exception:
                                try:
                                    input_widget.action_end()
                                except AttributeError:
                                    pass
                        self._programmatic_value_set = False
                self.set_timer(0.05, ensure_cursor_end)
            self.set_timer(0.1, restore_focus)
        self._open_file_picker()
    
    def _open_palette_from_slash(self) -> None:
        input_widget = self.query_one("#user-input", ChatInput)
        if input_widget.text == "/":
            input_widget.text = ""
        self.action_open_palette()
    
    def _open_plan_viewer(self) -> None:
        """打开计划查看弹窗"""
        # 如果已经有弹窗打开，不重复打开
        if isinstance(self.screen, ModalScreen):
            return
        
        # 检查是否有当前计划
        if not hasattr(self.agent, "current_plan") or self.agent.current_plan is None:
            return
        
        def handle_close(result: None) -> None:
            # 关闭后聚焦到输入框
            input_widget = self.query_one("#user-input", ChatInput)
            input_widget.focus()
        
        # 移除 user-input 的焦点
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.blur()
        self.push_screen(PlanViewerScreen(self.agent.current_plan), handle_close)
    
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
                
                # 立即尝试设置光标位置到文本末尾（即使没有焦点）
                def set_cursor_immediately():
                    try:
                        # 使用 document.end 获取文档末尾位置
                        end_location = input_widget.document.end
                        input_widget.cursor_location = end_location
                    except Exception:
                        # 如果失败，尝试使用 move_cursor
                        try:
                            end_location = input_widget.document.end
                            input_widget.move_cursor(end_location, select=False)
                        except Exception:
                            pass
                
                # 延迟设置光标位置，确保文档已更新
                self.set_timer(0.05, set_cursor_immediately)
                
                # 延迟恢复焦点
                def restore_focus():
                    input_widget.focus()
                    # 再次确保光标在末尾（因为恢复焦点可能会重置光标）
                    def ensure_cursor_end():
                        if input_widget.has_focus and self._programmatic_value_set:
                            try:
                                end_location = input_widget.document.end
                                input_widget.cursor_location = end_location
                            except Exception:
                                try:
                                    end_location = input_widget.document.end
                                    input_widget.move_cursor(end_location, select=False)
                                except Exception:
                                    try:
                                        input_widget.action_end()
                                    except AttributeError:
                                        pass
                            self._programmatic_value_set = False
                    self.set_timer(0.05, ensure_cursor_end)
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
            ("new", "New", "新建对话"),
            ("help", "Help", "显示帮助"),
            ("status", "Status", "上下文使用情况"),
            ("plan", "Plan", "查看任务计划进度"),
            ("messages", "Messages", "消息历史"),
            ("history", "History", "历史记录"),
            ("logs", "Logs", "查看日志"),
            ("config", "Config", "编辑配置"),
            ("clear", "Clear", "清空聊天"),
            ("exit", "Exit", "退出应用"),
        ]
        
        def handle_command(cmd_id: str | None) -> None:
            input_widget = self.query_one("#user-input", ChatInput)
            
            if not cmd_id:
                # 取消选择，聚焦到 user-input
                input_widget.focus()
                return
            
            if cmd_id == "new":
                self.action_new_chat()
            elif cmd_id == "help":
                self._show_help()
                input_widget.focus()
            elif cmd_id == "status":
                self._show_status()
                input_widget.focus()
            elif cmd_id == "plan":
                self._show_plan()
                input_widget.focus()
            elif cmd_id == "messages":
                self._show_messages()
                input_widget.focus()
            elif cmd_id == "history":
                self._open_history_screen()
            elif cmd_id == "logs":
                self._open_log_viewer()
            elif cmd_id == "config":
                self._open_config_editor()
            elif cmd_id == "clear":
                self.action_clear()
                input_widget.focus()
            elif cmd_id == "exit":
                self.action_quit(skip_confirmation=True)
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
    
    def _show_plan(self) -> None:
        """显示任务计划进度"""
        chat_container = self.query_one("#chat-log", Vertical)
        
        # 检查是否有当前计划
        if not hasattr(self.agent, "current_plan") or self.agent.current_plan is None:
            no_plan_msg = ContentMessage("[dim]当前没有任务计划[/]", allow_markup=True)
            chat_container.mount(no_plan_msg)
            self._scroll_to_bottom()
            self.query_one("#user-input", ChatInput).focus()
            return
        
        plan = self.agent.current_plan
        progress = plan.get_progress()
        
        # 构建计划显示内容
        plan_lines = [
            f"[bold]📋 任务计划[/bold]",
            f"[dim]任务描述:[/] {plan.task_description}",
            f"[dim]创建时间:[/] {plan.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"[bold]进度概览[/bold]",
            f"  总步骤: {progress['total']}",
            f"  ✅ 已完成: {progress['completed']}",
            f"  🔄 执行中: {progress['in_progress']}",
            f"  ⏳ 待执行: {progress['pending']}",
            f"  ❌ 失败: {progress['failed']}",
            f"  完成度: {progress['progress_percent']:.1f}%",
            "",
            f"[bold]执行步骤[/bold]",
        ]
        
        # 添加每个步骤的详细信息
        for step in plan.steps:
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }.get(step.status, "❓")
            
            # 根据状态设置颜色
            if step.status == StepStatus.COMPLETED:
                step_line = f"  {status_icon} [#22c55e]步骤 {step.step_number}:[/] {step.description}"
            elif step.status == StepStatus.FAILED:
                step_line = f"  {status_icon} [#ef4444]步骤 {step.step_number}:[/] {step.description}"
            elif step.status == StepStatus.IN_PROGRESS:
                step_line = f"  {status_icon} [#3b82f6]步骤 {step.step_number}:[/] {step.description}"
            else:
                step_line = f"  {status_icon} [dim]步骤 {step.step_number}:[/] {step.description}"
            
            plan_lines.append(step_line)
            
            # 显示预期工具
            if step.expected_tools:
                plan_lines.append(f"    [dim]工具:[/] {', '.join(step.expected_tools)}")
            
            # 显示结果或错误
            if step.status == StepStatus.COMPLETED and step.result:
                result_display = step.result[:150] + "..." if len(step.result) > 150 else step.result
                plan_lines.append(f"    [#22c55e]✓ 结果:[/] {result_display}")
            elif step.status == StepStatus.FAILED and step.error:
                plan_lines.append(f"    [#ef4444]✗ 错误:[/] {step.error}")
            
            # 显示时间信息
            if step.start_time:
                plan_lines.append(f"    [dim]开始:[/] {step.start_time.strftime('%H:%M:%S')}")
            if step.end_time:
                plan_lines.append(f"    [dim]结束:[/] {step.end_time.strftime('%H:%M:%S')}")
                if step.start_time:
                    duration = (step.end_time - step.start_time).total_seconds()
                    plan_lines.append(f"    [dim]耗时:[/] {duration:.1f}s")
            
            plan_lines.append("")  # 空行分隔
        
        plan_content = "\n".join(plan_lines)
        plan_msg = ContentMessage(plan_content, allow_markup=True)
        chat_container.mount(plan_msg)
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
        
        # 检查是否是命令
        if message == "/plan":
            self._show_plan()
            return
        elif message == "/history":
            self._open_history_screen()
            return
        elif message == "/config":
            self._open_config_editor()
            return
        elif message.lower() == "exit":
            # 直接输入 exit 也可以退出
            self.action_quit(skip_confirmation=True)
            return
        
        self.chat_count += 1
        self.add_user_message(message)
        
        # 如果是新对话（没有标题），异步生成标题
        if self.current_chat_title is None:
            self._generate_chat_title_async(message)
        
        # 记录对话开始时间
        import time
        self.chat_start_time = time.time()
        self.is_processing = True
        self.refresh_status()
        
        # 启动状态更新定时器（在主线程中，每0.5秒更新一次）
        def update_status_periodically() -> None:
            """定期更新状态（实时显示耗时）"""
            if self.is_processing:
                self.refresh_status()
                # 继续设置下一个定时器
                self.status_update_timer = self.set_timer(0.5, update_status_periodically)
            else:
                # 如果对话已结束，停止定时器
                self.status_update_timer = None
        
        self.status_update_timer = self.set_timer(0.5, update_status_periodically)
        
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
                
                # 过滤掉规划相关的输出（这些会显示在 header 中）
                if any(keyword in text for keyword in ["Task Analysis", "执行计划", "开始执行", "任务完成", "已完成", "步骤失败"]):
                    return
                
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
            
            def plan_status_callback(status: str) -> None:
                """规划状态回调，更新 header 显示"""
                app.call_from_thread(lambda: app.update_plan_status(status))
            
            def status_callback() -> None:
                """状态更新回调，实时更新token和耗时显示"""
                app.call_from_thread(lambda: app.refresh_status())
            
            # 清空规划状态
            app.call_from_thread(lambda: app.update_plan_status(""))
            
            self.agent.chat(message, output_callback, plan_status_callback, status_callback)
            
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
            # 清空规划状态
            app.call_from_thread(lambda: app.update_plan_status(""))
            app.call_from_thread(lambda: app._finish_chat())
    
    def _finish_chat(self) -> None:
        # 停止状态更新定时器
        if self.status_update_timer is not None:
            try:
                self.status_update_timer.stop()
                self.status_update_timer = None
            except:
                pass
        
        # 计算对话耗时
        import time
        if self.chat_start_time is not None:
            self.last_chat_duration = time.time() - self.chat_start_time
            self.chat_start_time = None
        
        # 保存历史记录（如果有对话内容）
        self._save_chat_history()
        
        self.is_processing = False
        self.refresh_header()
        self.refresh_status()
        input_widget = self.query_one("#user-input", ChatInput)
        if not input_widget.text:
            input_widget._show_placeholder()
        input_widget.focus()
    
    def _save_chat_history(self) -> None:
        """保存当前对话历史"""
        try:
            # 如果正在加载历史记录，不保存（避免重复保存）
            if self.is_loading_history:
                return
            
            # 检查是否有对话内容（至少有一条用户消息）
            if not hasattr(self.agent, "message_manager"):
                return
            
            messages = self.agent.message_manager.get_messages()
            # 只保存有实际对话内容的记录（至少有一条用户消息和一条助手消息）
            user_messages = [m for m in messages if m.get("role") == "user"]
            assistant_messages = [m for m in messages if m.get("role") == "assistant"]
            
            if not user_messages or not assistant_messages:
                return
            
            # 获取 token 使用情况
            mm = self.agent.message_manager
            token_usage = {
                "used": mm.max_context_tokens - mm.get_remaining_tokens(),
                "max": mm.max_context_tokens,
                "percent": mm.get_token_usage_percent(),
            }
            
            # 获取标题（如果没有则使用第一条用户消息的前15个字符）
            title = self.current_chat_title or (user_messages[0].get("content", "")[:15] if user_messages else "未命名对话")
            
            # 获取任务计划（如果有）
            current_plan = None
            if hasattr(self.agent, "current_plan") and self.agent.current_plan is not None:
                current_plan = self.agent.current_plan.to_dict()
            
            # 保存或更新历史记录（如果有 current_history_id 则更新，否则创建新的）
            saved_id = self.history_manager.save_chat(
                title=title,
                messages=messages,
                token_usage=token_usage,
                history_id=self.current_history_id,  # 如果有当前 ID 则更新，否则创建新的
                chat_count=self.chat_count,
                last_chat_duration=self.last_chat_duration,
                current_plan=current_plan,
            )
            # 更新当前历史记录 ID
            self.current_history_id = saved_id
        except Exception as e:
            # 保存失败不影响正常使用
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"保存历史记录失败: {e}")
    
    def _open_config_editor(self) -> None:
        """打开配置编辑界面"""
        # 如果已经有弹窗打开，不重复打开
        if isinstance(self.screen, ModalScreen):
            return
        
        def handle_config_save(saved: bool) -> None:
            input_widget = self.query_one("#user-input", ChatInput)
            
            if saved:
                # 配置已保存，显示提示消息
                chat_container = self.query_one("#chat-log", Vertical)
                success_msg = ContentMessage("[dim]配置已保存，重启应用后生效[/]", allow_markup=True)
                chat_container.mount(success_msg)
                self._scroll_to_bottom()
            
            input_widget.focus()
        
        # 移除 user-input 的焦点
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.blur()
        self.push_screen(ConfigEditScreen(), handle_config_save)
    
    def _open_history_screen(self) -> None:
        """打开历史记录选择弹窗"""
        # 如果已经有弹窗打开，不重复打开
        if isinstance(self.screen, ModalScreen):
            return
        
        def handle_history_selection(history: ChatHistory | None) -> None:
            input_widget = self.query_one("#user-input", ChatInput)
            
            if history is None:
                # 取消选择，聚焦到 user-input
                input_widget.focus()
                return
            
            # 加载选中的历史记录
            self._load_history(history)
            input_widget.focus()
        
        # 移除 user-input 的焦点
        input_widget = self.query_one("#user-input", ChatInput)
        input_widget.blur()
        self.push_screen(HistoryScreen(self.history_manager), handle_history_selection)
    
    def _load_history(self, history: ChatHistory) -> None:
        """加载历史记录并恢复对话状态"""
        try:
            if not history:
                self.add_system_message("无法加载历史记录：记录不存在")
                return
            
            # 设置加载标志，防止在加载过程中触发保存
            self.is_loading_history = True
            
            # 如果当前有未保存的对话，先保存
            if hasattr(self.agent, "message_manager"):
                messages = self.agent.message_manager.get_messages()
                user_messages = [m for m in messages if m.get("role") == "user"]
                assistant_messages = [m for m in messages if m.get("role") == "assistant"]
                if user_messages and assistant_messages:
                    # 临时清除加载标志以允许保存当前对话
                    was_loading = self.is_loading_history
                    self.is_loading_history = False
                    self._save_chat_history()
                    self.is_loading_history = was_loading
            
            # 清空当前聊天记录
            chat_container = self.query_one("#chat-log", Vertical)
            chat_container.remove_children()
            
            # 恢复消息历史
            if hasattr(self.agent, "message_manager"):
                # 保留系统消息，替换其他消息
                system_message = self.agent.message_manager.messages[0] if self.agent.message_manager.messages else None
                self.agent.message_manager.messages = history.messages.copy()
                # 如果原系统消息存在且历史记录中没有系统消息，则添加
                if system_message and not any(m.get("role") == "system" for m in history.messages):
                    self.agent.message_manager.messages.insert(0, system_message)
                
                # 恢复 token 使用情况（使用历史记录中的值）
                used_tokens = history.token_usage.get("used", 0)
                max_tokens = history.token_usage.get("max", self.agent.message_manager.max_context_tokens)
                # 注意：这里我们只能设置 current_tokens，无法直接设置 remaining_tokens
                self.agent.message_manager.current_tokens = used_tokens
            
            # 恢复对话标题
            self.current_chat_title = history.title
            self.is_generating_title = False
            
            # 恢复对话轮数
            self.chat_count = history.chat_count
            
            # 恢复最后一轮对话耗时
            self.last_chat_duration = history.last_chat_duration
            
            # 恢复历史记录 ID（后续更新会使用这个 ID）
            self.current_history_id = history.history_id
            
            # 恢复任务计划（如果有）
            if history.current_plan and hasattr(self.agent, "task_planner"):
                try:
                    from task_planner import TaskPlan, PlanStep, StepStatus
                    from datetime import datetime
                    
                    plan_data = history.current_plan
                    steps = []
                    for step_data in plan_data.get("steps", []):
                        step = PlanStep(
                            step_number=step_data["step_number"],
                            description=step_data["description"],
                            expected_tools=step_data.get("expected_tools", []),
                            status=StepStatus(step_data.get("status", "pending")),
                            result=step_data.get("result"),
                            error=step_data.get("error"),
                            start_time=datetime.fromisoformat(step_data["start_time"]) if step_data.get("start_time") else None,
                            end_time=datetime.fromisoformat(step_data["end_time"]) if step_data.get("end_time") else None,
                        )
                        steps.append(step)
                    
                    plan = TaskPlan(
                        task_description=plan_data["task_description"],
                        steps=steps,
                        created_at=datetime.fromisoformat(plan_data["created_at"]),
                        current_step=plan_data.get("current_step", 0),
                    )
                    self.agent.current_plan = plan
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"恢复任务计划失败: {e}")
                    self.agent.current_plan = None
            else:
                self.agent.current_plan = None
            
            # 恢复聊天界面显示
            self._restore_chat_display(history.messages)
            
            # 刷新界面
            self.refresh_header()
            self.refresh_status()
            
            # 显示加载成功消息
            self.add_system_message(f"已加载历史记录：{history.title}")
            
            # 清除加载标志，允许后续保存
            self.is_loading_history = False
            
        except Exception as e:
            import traceback
            error_msg = f"加载历史记录失败: {e}\n\n{traceback.format_exc()}"
            self.add_system_message(error_msg)
            # 确保在异常情况下也清除加载标志
            self.is_loading_history = False
    
    def _restore_chat_display(self, messages: List[Dict[str, Any]]) -> None:
        """恢复聊天界面显示"""
        chat_container = self.query_one("#chat-log", Vertical)
        
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            if role == "user":
                # 用户消息
                if content:
                    msg = UserMessage(content)
                    chat_container.mount(msg)
            elif role == "assistant":
                # 助手消息
                if tool_calls:
                    # 工具调用消息
                    tool_info = []
                    for tool_call in tool_calls:
                        if "function" in tool_call:
                            func = tool_call["function"]
                            name = func.get("name", "unknown")
                            args = func.get("arguments", "")
                            tool_info.append(f"工具: {name}\n参数: {args}")
                    if tool_info:
                        msg = ToolMessage("\n".join(tool_info))
                        chat_container.mount(msg)
                elif content:
                    # 普通助手消息
                    msg = ContentMessage(content)
                    chat_container.mount(msg)
            elif role == "tool":
                # 工具结果消息
                if content:
                    msg = ToolMessage(f"工具结果: {content[:500]}{'...' if len(content) > 500 else ''}")
                    chat_container.mount(msg)
            elif role == "system":
                # 系统消息（跳过，不显示在聊天界面）
                pass
        
        self._scroll_to_bottom()
    
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
    
    def action_new_chat(self) -> None:
        """新建对话"""
        if self.is_processing:
            return
        
        # 保存当前对话历史（如果有内容）
        self._save_chat_history()
        
        # 清空聊天记录
        chat_container = self.query_one("#chat-log", Vertical)
        chat_container.remove_children()
        # 重置 agent 的消息历史
        if hasattr(self.agent, "message_manager"):
            # 保留系统消息，清空其他消息
            if self.agent.message_manager.messages:
                system_message = self.agent.message_manager.messages[0]
                self.agent.message_manager.messages = [system_message]
            self.agent.message_manager.current_tokens = 0
        # 重置对话标题
        self.current_chat_title = None
        self.is_generating_title = False
        # 重置对话轮数
        self.chat_count = 0
        # 重置任务计划
        self.agent.current_plan = None
        # 重置历史记录 ID（新建对话时生成新的 ID）
        self.current_history_id = None
        # 刷新 header 和状态
        self.refresh_header()
        self.refresh_status()
        # 聚焦输入框
        self.query_one("#user-input", ChatInput).focus()
    
    def action_clear(self) -> None:
        chat_container = self.query_one("#chat-log", Vertical)
        chat_container.remove_children()
        # 重置对话标题，以便下次发送消息时生成新标题
        self.current_chat_title = None
        self.is_generating_title = False
        self.refresh_header()
        self.query_one("#user-input", ChatInput).focus()
    
    def action_quit(self, skip_confirmation: bool = False) -> None:
        """退出应用
        
        Args:
            skip_confirmation: 如果为 True，跳过确认直接退出（用于命令调用）
        """
        if skip_confirmation:
            # 命令调用，直接退出
            self.exit()
        elif self._quit_confirmed:
            # 第二次按 Ctrl+C，真正退出
            self.exit()
        else:
            # 第一次按 Ctrl+C，显示提示
            self._quit_confirmed = True
            self.add_system_message("按 Ctrl+C 再次确认退出")
            
            # 取消之前的定时器（如果存在）
            if self._quit_timer is not None:
                self._quit_timer.stop()
            
            # 设置定时器，3秒后重置确认状态
            def reset_quit_confirmed():
                self._quit_confirmed = False
                self._quit_timer = None
            
            self._quit_timer = self.set_timer(3.0, reset_quit_confirmed)
    
    def _generate_chat_title_async(self, first_message: str) -> None:
        """异步生成对话标题"""
        if self.is_generating_title:
            return
        
        self.is_generating_title = True
        self.refresh_header()  # 更新显示"生成标题中..."
        
        def generate_title():
            """在后台线程中生成标题"""
            app = self.app
            try:
                from config import config
                
                # 构建生成标题的提示词
                prompt = f"""请为以下用户消息生成一个简洁的对话标题。

要求：
- 标题长度不超过15个字符
- 简洁明了，能概括对话主题
- 只返回标题文本，不要包含引号、标点符号或其他内容

用户消息：{first_message[:200]}

标题："""
                
                # 调用 AI 生成标题（使用规划模型）
                response = self.agent.client.chat.completions.create(
                    model=config.planning_model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的标题生成助手，能够根据用户消息生成简洁明了的对话标题。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=50,
                )
                
                # 提取标题
                title = response.choices[0].message.content.strip()
                # 清理标题（移除可能的引号、换行、多余空格等）
                title = title.replace('"', '').replace("'", '').replace('\n', ' ').replace('\r', ' ')
                # 移除多余空格
                title = ' '.join(title.split())
                # 限制长度
                if len(title) > 15:
                    title = title[:15].strip()
                # 如果标题为空，使用回退标题
                if not title:
                    title = first_message[:15] if len(first_message) > 0 else "新对话"
                
                # 在主线程中更新标题
                app.call_from_thread(lambda: self._update_chat_title(title))
                
            except Exception as e:
                # 如果生成失败，使用默认标题或用户消息的前几个字
                fallback_title = first_message[:15] if len(first_message) > 0 else "新对话"
                app.call_from_thread(lambda: self._update_chat_title(fallback_title))
        
        # 在后台线程中执行
        self.run_worker(
            generate_title,
            thread=True,
            name="title_generator",
        )
    
    def _update_chat_title(self, title: str) -> None:
        """更新对话标题"""
        self.current_chat_title = title
        self.is_generating_title = False
        self.refresh_header()
