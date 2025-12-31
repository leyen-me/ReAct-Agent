# -*- coding: utf-8 -*-
"""工具基类"""

import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod

from utils import validate_path


class Tool(ABC):
    """工具基类"""
    
    def __init__(self, work_dir: Path):
        """
        初始化工具
        
        Args:
            work_dir: 工作目录路径
        """
        self.work_dir = work_dir
        # 将类名从大驼峰转换为小写下划线命名
        class_name = self.__class__.__name__
        # 移除末尾的 "Tool"（如果存在）
        if class_name.endswith("Tool"):
            class_name = class_name[:-4]
        # 将大驼峰转换为小写下划线
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
        self.name = name
        self._init_metadata()
    
    def _init_metadata(self) -> None:
        """初始化元数据，子类可以重写"""
        self.description = self._get_description()
        self.parameters = self._get_parameters()
    
    @abstractmethod
    def _get_description(self) -> str:
        """获取工具描述"""
        pass
    
    @abstractmethod
    def _get_parameters(self) -> Dict[str, Any]:
        """获取工具参数定义"""
        pass
    
    def validate_path(self, path: str) -> Tuple[bool, str]:
        """
        验证路径是否在工作目录内
        
        Args:
            path: 要验证的路径
            
        Returns:
            (是否有效, 错误信息)
        """
        return validate_path(path, self.work_dir)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（用于 API）
        
        Returns:
            工具定义字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
    
    @abstractmethod
    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行工具
        
        Args:
            parameters: 参数字典
            
        Returns:
            执行结果字符串
        """
        pass

