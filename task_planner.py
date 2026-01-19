# -*- coding: utf-8 -*-
"""任务规划模块"""

import math
import json
import logging
from typing import List, Dict, Any, Optional, Callable
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

    def create_plan(self, task_description: str, plan_status_callback: Optional[Callable[[str], None]] = None) -> TaskPlan:
        """
        创建任务计划

        Args:
            task_description: 任务描述
            plan_status_callback: 可选的规划状态回调函数，用于更新 header 显示

        Returns:
            任务计划
        """
        logger.info(f"开始规划任务: {task_description}")
        
        if plan_status_callback:
            plan_status_callback("📋 制定计划中...")

        # 构建规划提示词
        planning_prompt = self._build_planning_prompt(task_description)

        try:
            # 调用 LLM 生成计划（使用流式输出，使用规划模型）
            stream_response = self.client.chat.completions.create(
                model=config.planning_model,
                messages=[
                    {"role": "system", "content": self._get_planning_system_prompt()},
                    {"role": "user", "content": planning_prompt},
                ],
                temperature=0.7,
                max_tokens=2048,
                stream=True,
            )

            plan_content = ""
            try:
                for chunk in stream_response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            plan_content += delta.content
                            # 更新规划状态（显示前30个字符）
                            if plan_status_callback:
                                preview = plan_content[:30].replace('\n', ' ')
                                plan_status_callback(f"📋 制定计划中: {preview}...")
            finally:
                try:
                    stream_response.close()
                except:
                    pass
            
            logger.debug(f"规划响应: {plan_content}")

            # 解析计划
            if plan_status_callback:
                plan_status_callback("📋 解析计划中...")
            plan = self._parse_plan(task_description, plan_content)
            plan = self._compact_plan(plan)
            logger.info(f"规划完成，共 {len(plan.steps)} 个步骤")

            return plan

        except Exception as e:
            logger.error(f"规划失败: {e}")
            if plan_status_callback:
                plan_status_callback(f"⚠️ 规划失败: {str(e)[:30]}")
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
        """获取规划系统提示词（参考 OpenAI/Anthropic 最佳实践）"""
        return """You are an expert task planning assistant. Your role is to analyze user requests and decompose them into clear, executable action plans.

## Your Responsibilities

1. **Understand the Goal**: Identify the user's true objective, not just surface-level requirements
2. **Decompose Tasks**: Break complex tasks into smaller, atomic steps that can be executed sequentially
3. **Identify Dependencies**: Order steps logically, ensuring prerequisites are completed first
4. **Tool Selection**: For each step, identify which tools from the available set might be needed
5. **Clarity**: Make each step specific, measurable, and actionable

## Available Tools

""" + ", ".join(self.available_tools) + """

## Output Format

You must output your plan as valid JSON with the following structure:

{
  "steps": [
    {
      "step_number": <integer>,
      "description": "<clear, specific description of the action>",
      "expected_tools": ["<tool_name1>", "<tool_name2>"]
    }
  ]
}

## Guidelines

- Each step should be a single, focused action
- Steps should be ordered by dependencies (prerequisites first)
- Tool names must exactly match the available tools listed above
- Descriptions should be clear and specific enough for execution
- If a step doesn't require tools, use an empty array: []
- Keep the plan concise but comprehensive
- Avoid over-decomposition; prefer grouping related actions
- Simple tasks should be 1–3 steps; complex tasks should usually stay within 3–6 steps

## Example

User request: "Create a Python web application with a database"

{
  "steps": [
    {
      "step_number": 1,
      "description": "Create project directory structure",
      "expected_tools": ["create_folder"]
    },
    {
      "step_number": 2,
      "description": "Create main application file (app.py)",
      "expected_tools": ["create_file"]
    },
    {
      "step_number": 3,
      "description": "Create requirements.txt with dependencies",
      "expected_tools": ["create_file"]
    },
    {
      "step_number": 4,
      "description": "Create database schema file",
      "expected_tools": ["create_file"]
    }
  ]
}"""

    def _build_planning_prompt(self, task_description: str) -> str:
        """构建规划提示词（参考 OpenAI/Anthropic 最佳实践）"""
        return f"""Create a detailed execution plan for the following user request.

## User Request

{task_description}

## Context

- **Operating System**: {config.operating_system}
- **Working Directory**: {config.work_dir}
- **Current Time**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Instructions

1. Analyze the user's request to understand their true goal
2. Break down the task into sequential, executable steps
3. For each step:
   - Write a clear, specific description
   - Identify which tools (if any) are needed
   - Ensure steps are ordered by dependencies
4. Output the plan as valid JSON following the specified format

## Requirements

- Steps must be actionable and specific
- Each step should represent a single, focused action
- Tool names must match exactly from the available tools list
- Consider the environment context when planning
- Ensure the plan is complete and covers all aspects of the request
- Avoid over-decomposition; group related actions where possible
- For simple tasks, limit to 1–3 steps; for complex tasks, aim for 3–6 steps

Please provide your plan in the JSON format specified in the system instructions."""

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

    def _compact_plan(self, plan: TaskPlan) -> TaskPlan:
        """压缩过长的计划，避免过度拆分"""
        max_steps = max(1, int(getattr(config, "max_plan_steps", 6)))
        if len(plan.steps) <= max_steps:
            return plan

        chunk_size = int(math.ceil(len(plan.steps) / max_steps))
        compacted_steps: List[PlanStep] = []
        step_number = 1
        for i in range(0, len(plan.steps), chunk_size):
            chunk = plan.steps[i:i + chunk_size]
            descriptions = [s.description for s in chunk if s.description]
            merged_description = " / ".join(descriptions) if descriptions else "合并步骤"
            expected_tools: List[str] = []
            for s in chunk:
                for tool in s.expected_tools:
                    if tool not in expected_tools:
                        expected_tools.append(tool)
            compacted_steps.append(PlanStep(
                step_number=step_number,
                description=merged_description,
                expected_tools=expected_tools,
            ))
            step_number += 1

        plan.steps = compacted_steps
        plan.current_step = 0
        return plan

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
