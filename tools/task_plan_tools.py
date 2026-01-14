# -*- coding: utf-8 -*-
"""任务计划管理工具"""

import json
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from tools.base import Tool
from task_planner import TaskPlan, PlanStep, StepStatus


class UpdateStepStatusTool(Tool):
    """更新步骤状态工具"""
    
    def __init__(self, work_dir: Path, get_plan_callback: Callable[[], Optional[TaskPlan]]):
        """
        初始化工具
        
        Args:
            work_dir: 工作目录路径
            get_plan_callback: 获取当前任务计划的回调函数
        """
        self.get_plan_callback = get_plan_callback
        super().__init__(work_dir)
    
    def _get_description(self) -> str:
        """获取工具描述"""
        return """更新任务计划中某个步骤的状态。当你开始执行某个步骤时，调用此工具标记为"in_progress"；当步骤完成时，标记为"completed"并记录结果；如果步骤失败，标记为"failed"并记录错误信息；如果某个步骤不需要执行，可以标记为"skipped"。
        
使用场景：
- 开始执行计划中的某个步骤时，先调用此工具标记为"in_progress"
- 步骤执行成功后，调用此工具标记为"completed"并记录执行结果
- 步骤执行失败时，调用此工具标记为"failed"并记录错误原因
- 如果某个步骤不需要执行（例如任务已完成或步骤不适用），可以标记为"skipped"
"""
    
    def _get_parameters(self) -> Dict[str, Any]:
        """获取工具参数定义"""
        return {
            "type": "object",
            "properties": {
                "step_number": {
                    "type": "integer",
                    "description": "要更新的步骤编号（从1开始）",
                },
                "status": {
                    "type": "string",
                    "enum": ["in_progress", "completed", "failed", "skipped"],
                    "description": "步骤的新状态：in_progress(执行中), completed(已完成), failed(失败), skipped(已跳过)",
                },
                "result": {
                    "type": "string",
                    "description": "步骤的执行结果（当status为completed时使用，可选，建议提供简要结果摘要）",
                },
                "error": {
                    "type": "string",
                    "description": "错误信息（当status为failed时使用，可选）",
                },
            },
            "required": ["step_number", "status"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具"""
        step_number = parameters.get("step_number")
        status_str = parameters.get("status")
        result = parameters.get("result")
        error = parameters.get("error")
        
        if not isinstance(step_number, int) or step_number < 1:
            return json.dumps({
                "success": False,
                "error": f"无效的步骤编号: {step_number}",
            }, ensure_ascii=False)
        
        plan = self.get_plan_callback()
        if not plan:
            return json.dumps({
                "success": False,
                "error": "当前没有任务计划",
            }, ensure_ascii=False)
        
        # 查找步骤
        step = None
        for s in plan.steps:
            if s.step_number == step_number:
                step = s
                break
        
        if not step:
            return json.dumps({
                "success": False,
                "error": f"未找到步骤 {step_number}",
            }, ensure_ascii=False)
        
        # 更新状态
        try:
            if status_str == "in_progress":
                step.mark_started()
            elif status_str == "completed":
                step.mark_completed(result)
            elif status_str == "failed":
                step.mark_failed(error or "步骤执行失败")
            elif status_str == "skipped":
                step.mark_skipped(result or error)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"无效的状态: {status_str}",
                }, ensure_ascii=False)
            
            return json.dumps({
                "success": True,
                "result": f"步骤 {step_number} 已更新为 {status_str}",
                "step": {
                    "step_number": step.step_number,
                    "description": step.description,
                    "status": step.status.value,
                    "result": step.result,
                    "error": step.error,
                },
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"更新步骤状态失败: {str(e)}",
            }, ensure_ascii=False)


class MoveToNextStepTool(Tool):
    """移动到下一步工具"""
    
    def __init__(self, work_dir: Path, get_plan_callback: Callable[[], Optional[TaskPlan]]):
        """
        初始化工具
        
        Args:
            work_dir: 工作目录路径
            get_plan_callback: 获取当前任务计划的回调函数
        """
        self.get_plan_callback = get_plan_callback
        super().__init__(work_dir)
    
    def _get_description(self) -> str:
        """获取工具描述"""
        return """移动到任务计划的下一步。当你完成当前步骤并准备执行下一个步骤时，调用此工具。这会更新计划中的当前步骤索引。
        
使用场景：
- 完成某个步骤后，准备执行下一个步骤时调用
- 如果当前步骤失败但你想继续执行后续步骤，也可以调用此工具移动到下一步
"""
    
    def _get_parameters(self) -> Dict[str, Any]:
        """获取工具参数定义"""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具"""
        plan = self.get_plan_callback()
        if not plan:
            return json.dumps({
                "success": False,
                "error": "当前没有任务计划",
            }, ensure_ascii=False)
        
        try:
            old_step = plan.current_step
            plan.move_to_next_step()
            new_step = plan.get_current_step()
            
            if new_step:
                return json.dumps({
                    "success": True,
                    "result": f"已移动到步骤 {new_step.step_number}",
                    "current_step": {
                        "step_number": new_step.step_number,
                        "description": new_step.description,
                        "status": new_step.status.value,
                    },
                }, ensure_ascii=False)
            else:
                return json.dumps({
                    "success": True,
                    "result": "已到达计划末尾，没有更多步骤",
                    "progress": plan.get_progress(),
                }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"移动到下一步失败: {str(e)}",
            }, ensure_ascii=False)


class GetPlanStatusTool(Tool):
    """获取计划状态工具"""
    
    def __init__(self, work_dir: Path, get_plan_callback: Callable[[], Optional[TaskPlan]]):
        """
        初始化工具
        
        Args:
            work_dir: 工作目录路径
            get_plan_callback: 获取当前任务计划的回调函数
        """
        self.get_plan_callback = get_plan_callback
        super().__init__(work_dir)
    
    def _get_description(self) -> str:
        """获取工具描述"""
        return """获取当前任务计划的详细状态，包括所有步骤的状态、进度信息等。当你需要了解任务计划的当前进度时，可以调用此工具。
        
使用场景：
- 需要查看任务计划的整体进度时
- 需要了解某个步骤的状态时
- 需要确认是否所有步骤都已完成时
"""
    
    def _get_parameters(self) -> Dict[str, Any]:
        """获取工具参数定义"""
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        """执行工具"""
        plan = self.get_plan_callback()
        if not plan:
            return json.dumps({
                "success": False,
                "error": "当前没有任务计划",
            }, ensure_ascii=False)
        
        try:
            return json.dumps({
                "success": True,
                "result": plan.to_dict(),
                "formatted_plan": plan.format_plan(),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"获取计划状态失败: {str(e)}",
            }, ensure_ascii=False)
