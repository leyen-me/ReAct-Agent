# -*- coding: utf-8 -*-
"""任务规划模块"""

import json
import logging
from typing import List, Dict, Any, Optional
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

from openai import OpenAI
from config import config

logger = logging.getLogger(__name__)


class StepStatus(Enum):
    """步骤状态"""
    PENDING = "pending"  # 待执行
    IN_PROGRESS = "in_progress"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    SKIPPED = "skipped"  # 已跳过


@dataclass
class PlanStep:
    """计划步骤"""
    step_number: int  # 步骤编号
    description: str  # 步骤描述
    expected_tools: List[str] = field(default_factory=list)  # 预期使用的工具
    status: StepStatus = StepStatus.PENDING  # 步骤状态
    result: Optional[str] = None  # 执行结果
    error: Optional[str] = None  # 错误信息
    start_time: Optional[datetime] = None  # 开始时间
    end_time: Optional[datetime] = None  # 结束时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "step_number": self.step_number,
            "description": self.description,
            "expected_tools": self.expected_tools,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }

    def mark_started(self):
        """标记为开始执行"""
        self.status = StepStatus.IN_PROGRESS
        self.start_time = datetime.now()

    def mark_completed(self, result: Optional[str] = None):
        """标记为完成"""
        self.status = StepStatus.COMPLETED
        self.result = result
        self.end_time = datetime.now()

    def mark_failed(self, error: str):
        """标记为失败"""
        self.status = StepStatus.FAILED
        self.error = error
        self.end_time = datetime.now()

    def mark_skipped(self, reason: Optional[str] = None):
        """标记为跳过"""
        self.status = StepStatus.SKIPPED
        self.result = reason
        self.end_time = datetime.now()


@dataclass
class TaskPlan:
    """任务计划"""
    task_description: str  # 任务描述
    steps: List[PlanStep] = field(default_factory=list)  # 计划步骤
    created_at: datetime = field(default_factory=datetime.now)  # 创建时间
    current_step: int = 0  # 当前执行的步骤索引

    def get_progress(self) -> Dict[str, Any]:
        """获取进度信息"""
        total = len(self.steps)
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        failed = sum(1 for s in self.steps if s.status == StepStatus.FAILED)
        in_progress = sum(1 for s in self.steps if s.status == StepStatus.IN_PROGRESS)
        pending = sum(1 for s in self.steps if s.status == StepStatus.PENDING)

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": pending,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
        }

    def get_current_step(self) -> Optional[PlanStep]:
        """获取当前步骤"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None

    def move_to_next_step(self):
        """移动到下一步"""
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "task_description": self.task_description,
            "steps": [step.to_dict() for step in self.steps],
            "created_at": self.created_at.isoformat(),
            "current_step": self.current_step,
            "progress": self.get_progress(),
        }

    def format_plan(self) -> str:
        """格式化计划为字符串"""
        lines = [
            f"📋 任务计划: {self.task_description}",
            f"创建时间: {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "执行步骤:",
        ]
        
        progress = self.get_progress()
        lines.append(f"进度: {progress['completed']}/{progress['total']} 已完成 ({progress['progress_percent']:.1f}%)")
        lines.append("")
        
        for step in self.steps:
            status_icon = {
                StepStatus.PENDING: "⏳",
                StepStatus.IN_PROGRESS: "🔄",
                StepStatus.COMPLETED: "✅",
                StepStatus.FAILED: "❌",
                StepStatus.SKIPPED: "⏭️",
            }.get(step.status, "❓")
            
            line = f"{status_icon} 步骤 {step.step_number}: {step.description}"
            if step.expected_tools:
                line += f" [工具: {', '.join(step.expected_tools)}]"
            lines.append(line)
            
            if step.status == StepStatus.COMPLETED and step.result:
                lines.append(f"   ✓ 结果: {step.result[:100]}..." if len(step.result) > 100 else f"   ✓ 结果: {step.result}")
            elif step.status == StepStatus.FAILED and step.error:
                lines.append(f"   ✗ 错误: {step.error}")
        
        return "\n".join(lines)


class TaskPlanner:
    """任务规划器"""

    def __init__(self, client: OpenAI, available_tools: List[str]):
        """
        初始化任务规划器

        Args:
            client: OpenAI 客户端
            available_tools: 可用工具列表
        """
        self.client = client
        self.available_tools = available_tools

    def create_plan(self, task_description: str) -> TaskPlan:
        """
        创建任务计划

        Args:
            task_description: 任务描述

        Returns:
            任务计划
        """
        logger.info(f"开始规划任务: {task_description}")

        # 构建规划提示词
        planning_prompt = self._build_planning_prompt(task_description)

        try:
            # 调用 LLM 生成计划
            response = self.client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": self._get_planning_system_prompt()},
                    {"role": "user", "content": planning_prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
            )

            plan_content = response.choices[0].message.content
            logger.debug(f"规划响应: {plan_content}")

            # 解析计划
            plan = self._parse_plan(task_description, plan_content)
            logger.info(f"规划完成，共 {len(plan.steps)} 个步骤")

            return plan

        except Exception as e:
            logger.error(f"规划失败: {e}")
            # 如果规划失败，创建一个简单的单步计划
            return TaskPlan(
                task_description=task_description,
                steps=[
                    PlanStep(
                        step_number=1,
                        description=task_description,
                        expected_tools=[],
                    )
                ],
            )

    def _get_planning_system_prompt(self) -> str:
        """获取规划系统提示词"""
        return """You are a task planning expert. Your job is to analyze user tasks and break them down into clear, executable steps.

When creating a plan:
1. Understand the user's true goal
2. Break down complex tasks into smaller, actionable steps
3. Identify which tools might be needed for each step
4. Order steps logically (dependencies first)
5. Make steps specific and measurable

Available tools: """ + ", ".join(self.available_tools) + """

Output your plan in JSON format:
{
  "steps": [
    {
      "step_number": 1,
      "description": "Clear description of what to do",
      "expected_tools": ["tool_name1", "tool_name2"]
    },
    ...
  ]
}

Be concise but specific. Each step should be actionable."""

    def _build_planning_prompt(self, task_description: str) -> str:
        """构建规划提示词"""
        return f"""Please create a detailed execution plan for the following task:

Task: {task_description}

Environment:
- Operating System: {config.operating_system}
- Working Directory: {config.work_dir}
- Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please break down this task into clear, executable steps. For each step, specify:
1. What needs to be done
2. Which tools might be needed

Output the plan in JSON format as specified."""

    def _parse_plan(self, task_description: str, plan_content: str) -> TaskPlan:
        """解析计划内容"""
        try:
            # 尝试提取 JSON（可能包含 markdown 代码块）
            json_start = plan_content.find("{")
            json_end = plan_content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = plan_content[json_start:json_end]
                plan_data = json.loads(json_str)
                
                steps = []
                for step_data in plan_data.get("steps", []):
                    step = PlanStep(
                        step_number=step_data.get("step_number", len(steps) + 1),
                        description=step_data.get("description", ""),
                        expected_tools=step_data.get("expected_tools", []),
                    )
                    steps.append(step)
                
                return TaskPlan(
                    task_description=task_description,
                    steps=steps,
                )
        except json.JSONDecodeError as e:
            logger.warning(f"解析 JSON 失败: {e}，尝试文本解析")
        
        # 如果 JSON 解析失败，尝试文本解析
        return self._parse_plan_from_text(task_description, plan_content)

    def _parse_plan_from_text(self, task_description: str, plan_content: str) -> TaskPlan:
        """从文本解析计划（备用方法）"""
        steps = []
        lines = plan_content.split("\n")
        
        step_number = 1
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 查找步骤模式：数字开头或列表项
            if line[0].isdigit() or line.startswith("-") or line.startswith("*"):
                # 提取描述
                description = line
                # 移除编号或列表标记
                if description[0].isdigit():
                    parts = description.split(".", 1)
                    if len(parts) > 1:
                        description = parts[1].strip()
                elif description.startswith("-") or description.startswith("*"):
                    description = description[1:].strip()
                
                if description:
                    step = PlanStep(
                        step_number=step_number,
                        description=description,
                        expected_tools=[],
                    )
                    steps.append(step)
                    step_number += 1
        
        # 如果没有找到步骤，创建一个默认步骤
        if not steps:
            steps.append(PlanStep(
                step_number=1,
                description=task_description,
                expected_tools=[],
            ))
        
        return TaskPlan(
            task_description=task_description,
            steps=steps,
        )
