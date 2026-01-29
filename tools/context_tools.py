# -*- coding: utf-8 -*-
"""上下文管理工具"""

from pathlib import Path
from typing import Dict, Any, Optional, Callable

from tools.base import Tool


class SummarizeContextTool(Tool):
    """总结上下文并创建新对话段"""
    
    def __init__(self, work_dir: Path, on_summarize_callback: Optional[Callable[[str], None]] = None):
        """
        初始化总结上下文工具
        
        Args:
            work_dir: 工作目录路径
            on_summarize_callback: 总结完成后的回调函数，接收总结内容作为参数
        """
        super().__init__(work_dir)
        self.on_summarize_callback = on_summarize_callback
    
    def _get_description(self) -> str:
        return (
            "总结当前对话段的上下文并创建新的对话段。"
            "当上下文使用率达到 80% 时，应该调用此工具来总结当前任务进度，"
            "包括：用户当前任务、已完成的工作、下一步计划。"
            "调用此工具后，系统会自动创建新的对话段，但对话窗口保持不变。"
        )
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "上下文总结内容，必须包含：\n"
                        "1. 用户当前任务是什么\n"
                        "2. 已完成的工作有哪些\n"
                        "3. 下一步计划是什么"
                    )
                }
            },
            "required": ["summary"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """
        执行总结上下文
        
        Args:
            parameters: 参数字典，包含 summary 字段
            
        Returns:
            执行结果字符串
        """
        summary = parameters.get("summary", "")
        
        if not summary or not summary.strip():
            return "总结内容不能为空"
        
        # 调用回调函数，让 agent 处理总结和创建新段
        if self.on_summarize_callback:
            try:
                self.on_summarize_callback(summary)
                return (
                    "上下文总结成功，已创建新的对话段。"
                    "新段将包含历史总结信息，对话可以继续进行。"
                )
            except Exception as e:
                return f"创建新对话段失败: {e}"
        else:
            return "总结回调函数未设置"