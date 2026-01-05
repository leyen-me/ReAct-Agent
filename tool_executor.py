# -*- coding: utf-8 -*-
"""安全的工具执行器"""

import json
import logging
from typing import Dict, Any, List

from tools import Tool

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
                "error": f"执行工具失败: {e}"
            }


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
