# -*- coding: utf-8 -*-
"""安全的工具执行器"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable

from tools import Tool

logger = logging.getLogger(__name__)


class ToolExecutor:
    """安全的工具执行器，替代 eval()"""

    def __init__(self, tools: Dict[str, Tool], should_stop_check: Optional[Callable[[], bool]] = None):
        """
        初始化工具执行器

        Args:
            tools: 工具名称到工具实例的映射
            should_stop_check: 检查是否应该停止的函数，返回 True 表示应该停止
        """
        self.tools = tools
        self.should_stop_check = should_stop_check
        # 将检查函数传递给所有工具
        for tool in self.tools.values():
            tool.set_should_stop_check(should_stop_check)

    def execute(self, tool_name: str, parameters: str = "") -> dict:
        """
        安全地执行工具

        Args:
            tool_name: 工具名称
            parameters: 参数

        Returns:
            标准化结果字典，包含 success、result 和 error 字段
        """

        if parameters:
            try:
                parameters = json.loads(parameters)
            except json.JSONDecodeError:
                parameters = {}
            except Exception as e:
                logger.error(f"解析参数失败: {e}")
                return {
                    "success": False,
                    "result": None,
                    "error": f"解析参数失败: {e}"
                }
        try:
            # 检查是否应该停止
            if self.should_stop_check:
                should_stop_result = self.should_stop_check()
                logger.debug(f"工具 {tool_name} 执行前检查中断标志: {should_stop_result}")
                if should_stop_result:
                    logger.info(f"工具 {tool_name} 执行被用户中断")
                    return {
                        "success": False,
                        "result": None,
                        "error": "工具执行被用户中断"
                    }
            
            # 查找工具
            tool = self.tools.get(tool_name)
            if not tool:
                available_tools = ", ".join(self.tools.keys())
                return {
                    "success": False,
                    "result": None,
                    "error": f"工具 {tool_name} 不存在。可用工具: {available_tools}"
                }

            # 执行工具
            logger.debug(f"执行工具 {tool_name}，参数: {parameters}")
            result = tool.run(parameters)
            
            # 执行后再次检查是否应该停止
            if self.should_stop_check:
                should_stop_result = self.should_stop_check()
                logger.debug(f"工具 {tool_name} 执行后检查中断标志: {should_stop_result}")
                if should_stop_result:
                    logger.info(f"工具 {tool_name} 执行后被用户中断")
                    return {
                        "success": False,
                        "result": None,
                        "error": "工具执行被用户中断"
                    }
            return {
                "success": True,
                "result": result,
                "error": None
            }

        except ValueError as e:
            logger.error(f"解析 action 失败: {e}")
            return {
                "success": False,
                "result": None,
                "error": f"执行工具失败: {e}"
            }
        except Exception as e:
            logger.exception(f"执行工具时发生异常: {e}")
            return {
                "success": False,
                "result": None,
                "error": f"执行工具失败，回复的 JSON 可能有语法错误: {e}"
            }


def create_tool_executor(tools: List[Tool], should_stop_check: Optional[Callable[[], bool]] = None) -> ToolExecutor:
    """
    创建工具执行器

    Args:
        tools: 工具列表
        should_stop_check: 检查是否应该停止的函数，返回 True 表示应该停止

    Returns:
        工具执行器实例
    """
    tool_dict = {tool.name: tool for tool in tools}
    return ToolExecutor(tool_dict, should_stop_check)
