# -*- coding: utf-8 -*-
"""Todo List 工具模块"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from tools.base import Tool


class TodoItem:
    """Todo 项目类"""
    
    def __init__(self, id: str, content: str, status: str = "pending", 
                 created_at: Optional[str] = None, updated_at: Optional[str] = None):
        self.id = id
        self.content = content
        self.status = status  # pending, in_progress, completed, cancelled
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TodoItem':
        """从字典创建实例"""
        return cls(
            id=data["id"],
            content=data["content"],
            status=data["status"],
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )


class TodoListManager:
    """Todo List 管理器"""
    
    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.todo_file = work_dir / "todos.json"
        self.todos: Dict[str, TodoItem] = {}
        self._load_todos()
    
    def _load_todos(self) -> None:
        """从文件加载 todos"""
        if self.todo_file.exists():
            try:
                with open(self.todo_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.todos = {item["id"]: TodoItem.from_dict(item) for item in data}
            except (json.JSONDecodeError, KeyError):
                # 文件损坏，重置为空
                self.todos = {}
    
    def _save_todos(self) -> None:
        """保存 todos 到文件"""
        data = [todo.to_dict() for todo in self.todos.values()]
        with open(self.todo_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def add_todo(self, content: str) -> str:
        """添加 todo"""
        todo_id = str(len(self.todos) + 1)
        todo = TodoItem(id=todo_id, content=content)
        self.todos[todo_id] = todo
        self._save_todos()
        return f"Todo 已添加 (ID: {todo_id})"
    
    def list_todos(self, status_filter: Optional[str] = None) -> str:
        """列出 todos"""
        todos_list = list(self.todos.values())
        
        if status_filter:
            todos_list = [todo for todo in todos_list if todo.status == status_filter]
        
        if not todos_list:
            return "没有找到匹配的 todo 项目"
        
        result = []
        for todo in todos_list:
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄", 
                "completed": "✅",
                "cancelled": "❌"
            }.get(todo.status, "❓")
            
            result.append(f"{status_emoji} [{todo.id}] {todo.content} ({todo.status})")
        
        return "\n".join(result)
    
    def update_todo_status(self, todo_id: str, status: str) -> str:
        """更新 todo 状态"""
        if todo_id not in self.todos:
            return f"Todo ID {todo_id} 不存在"
        
        valid_statuses = ["pending", "in_progress", "completed", "cancelled"]
        if status not in valid_statuses:
            return f"无效的状态: {status}，有效状态: {', '.join(valid_statuses)}"
        
        todo = self.todos[todo_id]
        todo.status = status
        todo.updated_at = datetime.now().isoformat()
        self._save_todos()
        
        return f"Todo {todo_id} 状态已更新为 {status}"
    
    def delete_todo(self, todo_id: str) -> str:
        """删除 todo"""
        if todo_id not in self.todos:
            return f"Todo ID {todo_id} 不存在"
        
        todo_content = self.todos[todo_id].content
        del self.todos[todo_id]
        self._save_todos()
        
        return f"Todo {todo_id} ({todo_content}) 已删除"
    
    def get_todo_stats(self) -> str:
        """获取统计信息"""
        total = len(self.todos)
        pending = len([todo for todo in self.todos.values() if todo.status == "pending"])
        in_progress = len([todo for todo in self.todos.values() if todo.status == "in_progress"])
        completed = len([todo for todo in self.todos.values() if todo.status == "completed"])
        cancelled = len([todo for todo in self.todos.values() if todo.status == "cancelled"])
        
        return (
            f"Todo 统计信息:\n"
            f"总计: {total} 个\n"
            f"⏳ 待处理: {pending} 个\n"
            f"🔄 进行中: {in_progress} 个\n"
            f"✅ 已完成: {completed} 个\n"
            f"❌ 已取消: {cancelled} 个"
        )


class AddTodoTool(Tool):
    """添加 Todo 工具"""
    
    def __init__(self, work_dir: Path):
        super().__init__(work_dir)
        self.todo_manager = TodoListManager(work_dir)
    
    def _get_description(self) -> str:
        return "添加一个新的 todo 项目到 todo list"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "todo 项目的内容描述"
                }
            },
            "required": ["content"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        content = parameters["content"]
        return self.todo_manager.add_todo(content)


class ListTodosTool(Tool):
    """列出 Todos 工具"""
    
    def __init__(self, work_dir: Path):
        super().__init__(work_dir)
        self.todo_manager = TodoListManager(work_dir)
    
    def _get_description(self) -> str:
        return "列出所有 todo 项目，可选的按状态筛选"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "筛选状态 (可选: pending, in_progress, completed, cancelled)",
                    "enum": ["pending", "in_progress", "completed", "cancelled"]
                }
            },
            "required": []
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        status_filter = parameters.get("status")
        return self.todo_manager.list_todos(status_filter)


class UpdateTodoStatusTool(Tool):
    """更新 Todo 状态工具"""
    
    def __init__(self, work_dir: Path):
        super().__init__(work_dir)
        self.todo_manager = TodoListManager(work_dir)
    
    def _get_description(self) -> str:
        return "更新 todo 项目的状态"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "todo_id": {
                    "type": "string",
                    "description": "要更新的 todo 项目 ID"
                },
                "status": {
                    "type": "string",
                    "description": "新的状态",
                    "enum": ["pending", "in_progress", "completed", "cancelled"]
                }
            },
            "required": ["todo_id", "status"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        todo_id = parameters["todo_id"]
        status = parameters["status"]
        return self.todo_manager.update_todo_status(todo_id, status)


class DeleteTodoTool(Tool):
    """删除 Todo 工具"""
    
    def __init__(self, work_dir: Path):
        super().__init__(work_dir)
        self.todo_manager = TodoListManager(work_dir)
    
    def _get_description(self) -> str:
        return "删除指定的 todo 项目"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "todo_id": {
                    "type": "string",
                    "description": "要删除的 todo 项目 ID"
                }
            },
            "required": ["todo_id"]
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        todo_id = parameters["todo_id"]
        return self.todo_manager.delete_todo(todo_id)


class GetTodoStatsTool(Tool):
    """获取 Todo 统计工具"""
    
    def __init__(self, work_dir: Path):
        super().__init__(work_dir)
        self.todo_manager = TodoListManager(work_dir)
    
    def _get_description(self) -> str:
        return "获取 todo list 的统计信息"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        return self.todo_manager.get_todo_stats()
