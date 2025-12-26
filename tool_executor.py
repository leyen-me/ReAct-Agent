# -*- coding: utf-8 -*-
"""安全的工具执行器"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from tools import Tool
from utils import parse_action

logger = logging.getLogger(__name__)


class ToolExecutor:
    """安全的工具执行器，替代 eval()"""
    
    def __init__(self, tools: Dict[str, Tool]):
        """
        初始化工具执行器
        
        Args:
            tools: 工具名称到工具实例的映射
        """
        self.tools = tools
    
    def execute(self, action_str: str) -> str:
        """
        安全地执行 action 字符串
        
        Args:
            action_str: action 字符串，格式: ToolName().run({'param': 'value'})
            
        Returns:
            执行结果字符串
        """
        try:
            # 解析 action 字符串
            tool_name, parameters = parse_action(action_str)
            
            # 查找工具
            tool = self.tools.get(tool_name)
            if not tool:
                available_tools = ", ".join(self.tools.keys())
                return f"工具 {tool_name} 不存在。可用工具: {available_tools}"
            
            # 执行工具
            logger.debug(f"执行工具 {tool_name}，参数: {parameters}")
            result = tool.run(parameters)
            return result
            
        except ValueError as e:
            logger.error(f"解析 action 失败: {e}")
            return f"执行工具失败: {e}"
        except Exception as e:
            logger.exception(f"执行工具时发生异常: {e}")
            return f"执行工具失败: {e}"


def create_tool_executor(tools: List[Tool]) -> ToolExecutor:
    """
    创建工具执行器
    
    Args:
        tools: 工具列表
        
    Returns:
        工具执行器实例
    """
    tool_dict = {tool.name: tool for tool in tools}
    return ToolExecutor(tool_dict)

