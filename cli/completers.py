# -*- coding: utf-8 -*-
"""命令行补全器模块"""

from typing import Iterable, Tuple
from prompt_toolkit.completion import Completion, Completer
from prompt_toolkit.document import Document
from prompt_toolkit.completion import WordCompleter

from file_manager import FileListManager


class FileCompleter(Completer):
    """文件补全器，处理 @ 符号后的文件补全"""
    
    # 默认显示的文件数量
    DEFAULT_DISPLAY_COUNT = 20
    # 最大补全结果数
    MAX_COMPLETIONS = 50
    
    def __init__(self, file_list_manager: FileListManager):
        """
        初始化文件补全器
        
        Args:
            file_list_manager: 文件列表管理器实例
        """
        self.file_list_manager = file_list_manager
    
    def _extract_query(self, text: str) -> Tuple[str, int]:
        """
        从输入文本中提取查询字符串和起始位置
        
        Args:
            text: 输入文本
            
        Returns:
            (查询字符串, @符号位置) 的元组，如果没有找到@则返回 ("", -1)
        """
        last_at_index = text.rfind('@')
        if last_at_index == -1:
            return "", -1
        
        query = text[last_at_index + 1:]
        return query, last_at_index
    
    def get_completions(
        self, 
        document: Document, 
        complete_event
    ) -> Iterable[Completion]:
        """
        获取补全项
        
        Args:
            document: 文档对象
            complete_event: 补全事件
            
        Yields:
            Completion: 补全项
        """
        text = document.text_before_cursor
        
        # 检查是否包含 @ 符号
        if '@' not in text:
            return
        
        query, at_index = self._extract_query(text)
        if at_index == -1:
            return
        
        # 获取匹配的文件列表
        if query.strip() == '':
            matching_files = self.file_list_manager.get_file_list()[:self.DEFAULT_DISPLAY_COUNT]
        else:
            matching_files = self.file_list_manager.search_files(query, limit=self.MAX_COMPLETIONS)
        
        # 生成补全项
        replace_length = len(text) - at_index - 1
        for file_path in matching_files:
            # 用反引号包裹文件路径，方便 AI 识别
            completion_text = f"`{file_path}`"
            
            yield Completion(
                completion_text,
                start_position=-replace_length,
                display=file_path,  # 显示时仍然显示原始路径（不带反引号）
                style="fg:#00ffcc",
            )


class MergedCompleter(Completer):
    """合并补全器，同时处理命令和文件补全"""
    
    def __init__(
        self, 
        command_completer: WordCompleter, 
        file_completer: FileCompleter
    ):
        """
        初始化合并补全器
        
        Args:
            command_completer: 命令补全器
            file_completer: 文件补全器
        """
        self.command_completer = command_completer
        self.file_completer = file_completer
    
    def get_completions(
        self, 
        document: Document, 
        complete_event
    ) -> Iterable[Completion]:
        """
        获取补全项
        
        Args:
            document: 文档对象
            complete_event: 补全事件
            
        Yields:
            Completion: 补全项
        """
        text = document.text_before_cursor
        
        # 如果以 / 开头，使用命令补全器
        if text.startswith('/'):
            yield from self.command_completer.get_completions(document, complete_event)
        # 如果包含 @ 符号，使用文件补全器
        elif '@' in text:
            yield from self.file_completer.get_completions(document, complete_event)

