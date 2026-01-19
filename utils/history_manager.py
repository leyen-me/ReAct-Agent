# -*- coding: utf-8 -*-
"""历史记录管理模块"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChatHistory:
    """单次对话历史记录"""
    
    def __init__(
        self,
        title: str,
        messages: List[Dict[str, Any]],
        token_usage: Dict[str, int],
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        chat_count: int = 0,
        last_chat_duration: Optional[float] = None,
        current_plan: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化对话历史记录
        
        Args:
            title: 对话标题
            messages: 消息列表
            token_usage: token 使用情况 {"used": int, "max": int, "percent": float}
            created_at: 创建时间（ISO 格式字符串）
            updated_at: 更新时间（ISO 格式字符串）
            chat_count: 对话轮数
            last_chat_duration: 最后一轮对话耗时（秒）
            current_plan: 当前任务计划（如果有）
        """
        self.title = title
        self.messages = messages
        self.token_usage = token_usage
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or datetime.now().isoformat()
        self.chat_count = chat_count
        self.last_chat_duration = last_chat_duration
        self.current_plan = current_plan
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "title": self.title,
            "messages": self.messages,
            "token_usage": self.token_usage,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "chat_count": self.chat_count,
            "last_chat_duration": self.last_chat_duration,
            "current_plan": self.current_plan,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatHistory":
        """从字典创建"""
        return cls(
            title=data.get("title", "未命名对话"),
            messages=data.get("messages", []),
            token_usage=data.get("token_usage", {"used": 0, "max": 0, "percent": 0.0}),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            chat_count=data.get("chat_count", 0),
            last_chat_duration=data.get("last_chat_duration"),
            current_plan=data.get("current_plan"),
        )


class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, history_dir: Path):
        """
        初始化历史记录管理器
        
        Args:
            history_dir: 历史记录存储目录
        """
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.history_dir / "chat_history.json"
        self._histories: List[ChatHistory] = []
        self._load_histories()
    
    def _load_histories(self) -> None:
        """从文件加载历史记录"""
        if not self.history_file.exists():
            self._histories = []
            return
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._histories = [
                    ChatHistory.from_dict(item) for item in data.get("histories", [])
                ]
            # 按更新时间倒序排列（最新的在前）
            self._histories.sort(key=lambda h: h.updated_at, reverse=True)
        except Exception as e:
            logger.error(f"加载历史记录失败: {e}")
            self._histories = []
    
    def _save_histories(self) -> None:
        """保存历史记录到文件"""
        try:
            data = {
                "histories": [h.to_dict() for h in self._histories]
            }
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史记录失败: {e}")
    
    def save_chat(
        self,
        title: str,
        messages: List[Dict[str, Any]],
        token_usage: Dict[str, int],
        chat_count: int = 0,
        last_chat_duration: Optional[float] = None,
        current_plan: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        保存对话历史
        
        Args:
            title: 对话标题
            messages: 消息列表
            token_usage: token 使用情况 {"used": int, "max": int, "percent": float}
            chat_count: 对话轮数
            last_chat_duration: 最后一轮对话耗时（秒）
            current_plan: 当前任务计划（如果有）
            
        Returns:
            历史记录 ID（时间戳）
        """
        history_id = datetime.now().isoformat()
        
        history = ChatHistory(
            title=title,
            messages=messages,
            token_usage=token_usage,
            created_at=history_id,
            updated_at=history_id,
            chat_count=chat_count,
            last_chat_duration=last_chat_duration,
            current_plan=current_plan,
        )
        
        # 添加到列表开头（最新的在前）
        self._histories.insert(0, history)
        
        # 限制历史记录数量（最多保留 100 条）
        if len(self._histories) > 100:
            self._histories = self._histories[:100]
        
        self._save_histories()
        return history_id
    
    def get_all_histories(self) -> List[ChatHistory]:
        """获取所有历史记录（按时间倒序）"""
        return self._histories.copy()
    
    def get_history_by_index(self, index: int) -> Optional[ChatHistory]:
        """根据索引获取历史记录"""
        if 0 <= index < len(self._histories):
            return self._histories[index]
        return None
    
    def delete_history(self, index: int) -> bool:
        """
        删除历史记录
        
        Args:
            index: 历史记录索引
            
        Returns:
            是否删除成功
        """
        if 0 <= index < len(self._histories):
            self._histories.pop(index)
            self._save_histories()
            return True
        return False
    
    def clear_all(self) -> None:
        """清空所有历史记录"""
        self._histories = []
        self._save_histories()
