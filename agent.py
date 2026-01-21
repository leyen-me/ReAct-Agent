# -*- coding: utf-8 -*-
"""ReAct Agent 主逻辑"""

import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Tuple

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk

from config import config
from tools import (
    Tool,
    ReadFileTool,
    WriteFileTool,
    DeleteFileTool,
    CreateFileTool,
    RenameFileTool,
    ListFilesTool,
    TreeFilesTool,
    EditFileTool,
    CreateFolderTool,
    DeleteFolderTool,
    MoveFileTool,
    CopyFileTool,
    ReadCodeBlockTool,
    RunCommandTool,
    SearchInFilesTool,
    FindFilesTool,
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitBranchTool,
    GitLogTool,
    UpdateStepStatusTool,
    MoveToNextStepTool,
    GetPlanStatusTool,
)
from tool_executor import create_tool_executor
from task_planner import TaskPlanner, TaskPlan, PlanStep, StepStatus

logger = logging.getLogger(__name__)


class MessageManager:
    """消息管理器"""

    def __init__(self, system_prompt: str, max_context_tokens: int):
        """
        初始化消息管理器

        Args:
            system_prompt: 系统提示词
            max_context_tokens: 最大上下文 token 数
        """
        self.max_context_tokens = max_context_tokens
        self.messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        # 当前实际使用的 token 数（从 API 响应获取）
        self.current_tokens: int = 0
        # 估算的 token 数（用于实时显示，在流式过程中更新）
        self.estimated_tokens: int = 0

    def update_token_usage(self, prompt_tokens: int) -> None:
        """
        更新 token 使用量（从 API 响应获取）

        Args:
            prompt_tokens: API 返回的 prompt_tokens
        """
        self.current_tokens = prompt_tokens
        self.estimated_tokens = prompt_tokens  # 同步更新估算值
        self._manage_context()

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数量（简单估算：中文约 1.5 字符/token，英文约 4 字符/token）

        Args:
            text: 要估算的文本

        Returns:
            估算的 token 数
        """
        if not text:
            return 0

        # 简单估算：统计中文字符和英文字符
        chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_chars = len(text) - chinese_chars

        # 中文字符：约 1.5 字符/token
        # 其他字符（英文、数字、标点等）：约 4 字符/token
        estimated = int(chinese_chars / 1.5 + other_chars / 4)
        return max(1, estimated)  # 至少返回 1

    def update_estimated_tokens(self, completion_content: str = "") -> None:
        """
        更新估算的 token 使用量（用于实时显示）

        Args:
            completion_content: 当前已生成的 completion 内容
        """
        # 估算 prompt tokens（基于消息历史）
        prompt_text = ""
        for msg in self.messages:
            if msg.get("role") == "system":
                prompt_text += msg.get("content", "")
            elif msg.get("role") == "user":
                prompt_text += msg.get("content", "")
            elif msg.get("role") == "assistant":
                # 如果是工具调用，估算工具调用的 token
                if "tool_calls" in msg:
                    for tc in msg.get("tool_calls", []):
                        if "function" in tc:
                            func = tc["function"]
                            prompt_text += func.get("name", "") + func.get(
                                "arguments", ""
                            )
                else:
                    # 如果是普通回复，不计算到 prompt 中（因为这是 completion）
                    pass
            elif msg.get("role") == "tool":
                prompt_text += msg.get("content", "")

        # 估算 completion tokens（基于已生成的内容）
        completion_tokens = self.estimate_tokens(completion_content)

        # 总估算 = prompt tokens + completion tokens
        # 如果已经有实际的 current_tokens（来自上次 API 响应），使用它作为基础
        if self.current_tokens > 0:
            # 基于上次的实际值，加上新增的 completion tokens
            # 减去上次的 completion tokens（如果有的话）
            self.estimated_tokens = self.current_tokens + completion_tokens
        else:
            # 如果还没有实际值，完全基于估算
            prompt_tokens = self.estimate_tokens(prompt_text)
            self.estimated_tokens = prompt_tokens + completion_tokens

    def get_estimated_token_usage_percent(self) -> float:
        """
        获取估算的 token 使用百分比（用于实时显示）

        Returns:
            使用百分比（0-100）
        """
        return (self.estimated_tokens / self.max_context_tokens) * 100

    def get_estimated_remaining_tokens(self) -> int:
        """
        获取估算的剩余可用 token 数（用于实时显示）

        Returns:
            剩余 token 数
        """
        return max(0, self.max_context_tokens - self.estimated_tokens)

    def _manage_context(self) -> None:
        """管理上下文，当超过限制时删除旧消息（保留系统消息）"""
        # 如果超过限制，删除最旧的非系统消息
        while self.current_tokens > self.max_context_tokens and len(self.messages) > 1:
            # 保留系统消息，删除第一个非系统消息
            removed_message = self.messages.pop(1)
            logger.debug(
                f"上下文已满，删除旧消息，当前使用: {self.current_tokens}/{self.max_context_tokens}"
            )
            # 注意：删除消息后，下次 API 调用时会重新计算 token 数
            # 这里我们暂时保持 current_tokens 不变，等待下次 API 响应更新

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": f"{content}"})

    def add_assistant_content(self, content: str) -> None:
        """添加助手内容"""
        self.messages.append({"role": "assistant", "content": f"{content}"})

    def add_assistant_tool_call_result(self, tool_call_id: str, content: str) -> None:
        """添加助手工具调用结果"""
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": f"{content}"}
        )

    def add_assistant_tool_call(
        self, tool_call_id: str, name: str, arguments: str = ""
    ) -> None:
        """添加助手工具调用"""
        self.messages.append(
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {
                            "name": name,
                            "arguments": arguments,
                        },
                    }
                ],
            }
        )

    def get_messages(self) -> List[Dict[str, str]]:
        """获取所有消息"""
        return self.messages.copy()

    def get_token_usage_percent(self) -> float:
        """
        获取当前 token 使用百分比

        Returns:
            使用百分比（0-100）
        """
        return (self.current_tokens / self.max_context_tokens) * 100

    def get_remaining_tokens(self) -> int:
        """
        获取剩余可用 token 数

        Returns:
            剩余 token 数
        """
        return max(0, self.max_context_tokens - self.current_tokens)


class ReActAgent:
    """ReAct Agent"""

    def __init__(self):
        """初始化 Agent"""
        # 禁用 OpenAI 客户端的 HTTP 日志输出
        import httpx
        import logging

        # 禁用 httpx 的日志
        httpx_logger = logging.getLogger("httpx")
        httpx_logger.setLevel(logging.WARNING)

        # 禁用 httpcore 的日志（httpx 的底层库）
        httpcore_logger = logging.getLogger("httpcore")
        httpcore_logger.setLevel(logging.WARNING)

        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self.tools = self._create_tools()
        self.tool_executor = create_tool_executor(self.tools)
        self.message_manager = MessageManager(
            self._get_system_prompt(), config.max_context_tokens
        )
        # 初始化任务规划器
        available_tool_names = [tool.name for tool in self.tools]
        self.task_planner = TaskPlanner(self.client, available_tool_names)
        self.current_plan: Optional[TaskPlan] = None  # 当前任务计划
        self.enable_planning: bool = config.enable_task_planning  # 是否启用规划功能
        self.chat_count = 0
        self.should_stop = False  # 中断标志

    def _create_tools(self) -> List[Tool]:
        """创建工具列表"""

        # 创建任务计划工具的回调函数
        def get_plan() -> Optional[TaskPlan]:
            return self.current_plan

        tools = [
            ReadFileTool(config.work_dir),
            ReadCodeBlockTool(config.work_dir),
            WriteFileTool(config.work_dir),
            DeleteFileTool(config.work_dir),
            CreateFileTool(config.work_dir),
            RenameFileTool(config.work_dir),
            ListFilesTool(config.work_dir),
            TreeFilesTool(config.work_dir),
            CreateFolderTool(config.work_dir),
            EditFileTool(config.work_dir),
            RunCommandTool(config.work_dir, config.command_timeout),
            SearchInFilesTool(config.work_dir, config.max_search_results),
            FindFilesTool(config.work_dir, config.max_find_files),
            DeleteFolderTool(config.work_dir),
            MoveFileTool(config.work_dir),
            CopyFileTool(config.work_dir),
            GitStatusTool(config.work_dir),
            GitDiffTool(config.work_dir),
            GitCommitTool(config.work_dir),
            GitBranchTool(config.work_dir),
            GitLogTool(config.work_dir),
            # 任务计划管理工具
            # UpdateStepStatusTool(config.work_dir, get_plan),
            # MoveToNextStepTool(config.work_dir, get_plan),
            # GetPlanStatusTool(config.work_dir, get_plan),
        ]
        return tools

    def _get_system_prompt_by_en(self) -> str:
        """Generate system prompt"""
        return f"""
You are a professional task-execution AI Agent.

━━━━━━━━━━━━━━
【Core Responsibilities】
━━━━━━━━━━━━━━
1. Accurately understand the user's true goal, not just the surface-level question
2. Follow the execution plan if one is provided, or decompose complex tasks into executable steps
3. Complete tasks within the constraints of the current environment
4. If a task fails, analyze the cause and attempt corrective solutions
5. Stop only after confirming the task is completed

━━━━━━━━━━━━━━
【Execution Principles】
━━━━━━━━━━━━━━
- Prioritize execution over explanation
- If an execution plan is provided, follow it step by step
- Think through the overall plan first, then execute step by step
- Evaluate each step by whether it moves closer to the goal
- When uncertain, attempt the Minimum Viable Action (MVP)
- Do not fabricate non-existent files, commands, or results
- Report progress as you complete each step of the plan
- Keep plans concise and avoid over-decomposition (simple tasks should be 1–3 steps)

━━━━━━━━━━━━━━
【Task Plan Management】
━━━━━━━━━━━━━━
When a task plan is provided, you are responsible for managing its execution and progress:

1. **Before starting a step**: Use the `update_step_status` tool to mark the step as "in_progress"
2. **After completing a step**: Use the `update_step_status` tool to mark the step as "completed" and provide a brief result summary
3. **If a step fails**: Use the `update_step_status` tool to mark the step as "failed" and provide error information
4. **To move to next step**: Use the `move_to_next_step` tool when you're ready to proceed to the next step
5. **To check plan status**: Use the `get_plan_status` tool to view the current plan progress and all step statuses

IMPORTANT: You must actively manage the task plan progress. Do not rely on automatic updates - you control when steps are marked as started, completed, failed, or skipped.
IMPORTANT: Do not update status for every minor action. Only update when a full plan step is actually completed.

━━━━━━━━━━━━━━
【Environment Information】
━━━━━━━━━━━━━━
Operating System: {config.operating_system}
Working Directory: {config.work_dir}
Current Time (Beijing Time): {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
User Language Preference: {config.user_language_preference}

You must reason and act strictly based on the above real environment.

━━━━━━━━━━━━━━
【Output Requirements】
━━━━━━━━━━━━━━
- Output only content that is valuable to the user
- Clearly state "Task completed" after the task is finished
- If the task cannot be completed, clearly explain the reason and suggest next steps

━━━━━━━━━━━━━━
【Prohibited Actions】
━━━━━━━━━━━━━━
- Do not assume the existence of unspecified tools or files
- Do not claim task completion without verification
- Do not output irrelevant or verbose explanatory content
"""

    def _get_system_prompt_by_cn(self) -> str:
        """生成系统提示词（微软 PM / Spec 风格 Agent）"""
        return f"""
    你是一名微软的全栈开发实习生，正在使用 {config.operating_system}电脑, 正在使用 Visual Studio Code 打开了一个的本地工作目录 {config.work_dir}。准备完成 PM 提供的产品需求。

    ━━━━━━━━━━━━━━
    【初始状态规则（必须遵守）】
    ━━━━━━━━━━━━━━
    - 如果尚未收到明确、可执行的产品需求或工作项（Work Item）：
    - 明确回复：“你好，我刚刚在摸鱼，现在有一些空闲时间，请告诉我你需要我做什么？”
    - 不进行任务拆分
    - 不调用任何工具
    - 不输出多余内容

    ━━━━━━━━━━━━━━
    【可用工具】
    ━━━━━━━━━━━━━━
    {self._get_tools_name_and_description()}

    ━━━━━━━━━━━━━━
    【总体目标】
    ━━━━━━━━━━━━━━
    - 准确理解当前有效的产品需求
    - 在真实环境与约束下完成实现
    - 在需求不明确或存在风险时，主动暴露问题
    - 仅输出对需求方 PM 有价值的结果

    ━━━━━━━━━━━━━━
    【执行流程（严格阶段化）】
    ━━━━━━━━━━━━━━

    【阶段 1：需求理解、澄清、补全默认实现（Understand）】
    - 判断当前输入属于：
    - 新产品需求
    - 对现有需求的补充 / 修改
    - 对实现进度或结果的询问
    - 在需求存在歧义，明确指出不确定点，提出必要的澄清问题
    - 可以调用一些可读性工具，来辅助理解需求
    - 你的目标不是“等待完美需求”，而是：在需求不完整时，先基于代码和常识给出一个【合理的默认实现】，同时明确哪些地方是【你的工程假设】
    - 当需求表述模糊时，允许你基于工程经验自行补全默认方案

    ━━━━━━━━━━━━━━
    【阶段 2：任务规划（Plan）】
    - 在以下情况进入该阶段：
    - 首次收到需求
    - 需求发生实质性变更
    - 当前计划无法满足最新需求

    - 输出内容：
    - 简要的需求理解摘要
    - 基于需求的任务拆分（markdown 任务列表）
    - 为防止遗忘，你可以创建一个 tasks 目录，将任务列表以 markdown 文件的格式保存到 tasks 目录下

    - 任务拆分规则：
    - 从功能层面拆分，而非代码细节
    - 拆分到“单个任务可以在一次工具调用或一次明确操作中完成”为止
    - 禁止为拆分而拆分

    - 任务状态标记：
    - ⏳ 待执行
    - ✅ 已完成
    - 🟡 已跳过（因需求调整）
    - ⛔ 已失效（需求被推翻）

    ━━━━━━━━━━━━━━
    【阶段 3：任务执行（Execute）】
    ━━━━━━━━━━━━━━
    - 严格按照“⏳ 待执行”顺序执行
    - 每次只执行一个最小任务
    - 仅在当前任务确实需要时调用工具
    - 工具调用必须明确指定工具名称
    - 禁止在思考或规划阶段调用工具

    ━━━━━━━━━━━━━━
    【阶段 4：验证与进度同步（Verify & Sync）】
    ━━━━━━━━━━━━━━
    - 每完成一个任务：
    - 更新 tasks 目录下的 markdown 文件，标记任务状态
    - 同步对需求方有价值的进度或结果
    - 如果发现：
    - 实现与需求不一致
    - 需求本身存在问题
    - 当前方案存在明显风险
    - 必须及时指出并给出建议

    - 如果 PM 在执行过程中提出新决策：
    - 立即暂停当前任务
    - 回到【阶段 1：需求理解、澄清、补全默认实现】

    ━━━━━━━━━━━━━━
    【阶段 5：完成条件（Definition of Done）】
    ━━━━━━━━━━━━━━
    - 仅在以下条件全部满足时，才认为需求完成：
    - 当前有效需求已全部实现
    - 所有相关任务状态为“✅ 已完成”或“🟡 已跳过（合理）”

    - 完成后：
    - 输出结果摘要
    - 明确说明：“任务已完成”

    ━━━━━━━━━━━━━━
    【环境约束】
    ━━━━━━━━━━━━━━
    - 操作系统：{config.operating_system}
    - 工作目录：{config.work_dir}
    - 当前时间（北京时间）：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    - PM 语言偏好：{config.user_language_preference}

    你必须基于以上真实环境进行推理与行动。

    ━━━━━━━━━━━━━━
    【输出规范】
    ━━━━━━━━━━━━━━
    - 只输出与当前阶段相关的内容
    - 回答问题时优先给结论，其次给必要上下文
    - 避免情绪化或非工程化表述
    - 不输出冗余解释或规则复述

    ━━━━━━━━━━━━━━
    【禁止事项】
    ━━━━━━━━━━━━━━
    - 不要编造产品需求或决策
    - 不要忽略最新的产品决策
    - 不要在需求已失效时继续执行旧任务
    - 不要在未验证前声称“任务已完成”

    ━━━━━━━━━━━━━━
    【工程质量检查】
    ━━━━━━━━━━━━━━
    - 前端任务：lint / build / test
    - 后端任务：单元测试 / 集成测试
    - 其他任务：使用与任务类型匹配的验证方式
    
    ━━━━━━━━━━━━━━
    【版本控制与提交规范（Git Discipline）】
    ━━━━━━━━━━━━━━
    - 项目使用 Git 进行版本控制
    - 每完成一个“重要步骤（Milestone）”，必须进行一次提交（commit）

    【什么是“重要步骤”】
    以下任意情况，视为一个重要步骤：
    - 完成一个独立的功能点
    - 完成一次对需求有明确价值的代码改动
    - 修复一个明确的 Bug
    - 重构但不改变外部行为
    - 通过一个关键验证（build / test / lint）

    【Commit 时机规则】
    - 在以下时刻必须 commit：
    - 当前步骤的代码已可独立工作
    - 不依赖后续步骤即可通过验证
    - 禁止以下行为：
    - 未完成的半成品 commit
    - 多个不相关改动混在一次 commit
    - 为了凑数而频繁 commit

    【Commit 前检查】
    - 确认代码可运行或通过相应验证
    - 确认改动范围与当前步骤一致
    - 确认未引入与当前任务无关的修改

    【Commit Message 规范（必须遵守）】
    - 使用简洁、工程化的中文描述
    - 推荐格式：
    - feat: 新增 xxx 功能
    - fix: 修复 xxx 问题
    - refactor: 重构 xxx
    - test: 添加/更新 xxx 测试
    - chore: 更新 xxx 工具或配置

    【执行约束】
    - Commit 只能在【阶段 3：任务执行（Execute）】或【阶段 4：验证与进度同步（Verify & Sync）】中进行
    - 每次 commit 后：
    - 简要说明本次提交完成了什么
    - 更新对应任务的状态
    """



    def _get_system_prompt(self) -> str:
        """生成系统提示词"""
        return self._get_system_prompt_by_cn()

    def _get_tools(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        return [{"type": "function", "function": tool.to_dict()} for tool in self.tools]
    
    def _get_tools_name_and_description(self) -> str:
        """获取工具名称和描述"""
        return "\n".join([f"- {tool.name}: {tool.description}" for tool in self.tools])
    
    def _detect_fake_tool_call_in_reasoning(self, reasoning_content: str) -> bool:
        """
        检测思考内容中是否有虚假的工具调用
        
        检测逻辑：如果思考内容末尾是 JSON 对象，很可能是虚假的工具调用
        
        Args:
            reasoning_content: 思考内容
            
        Returns:
            是否检测到虚假工具调用
        """
        if not reasoning_content:
            return False
        
        # 去除末尾空白
        content = reasoning_content.strip()
        if not content:
            return False
        
        # 查找最后一个 JSON 对象（从末尾开始）
        # 找到最后一个 '}' 的位置
        last_brace_pos = content.rfind('}')
        if last_brace_pos == -1:
            return False
        
        # 从最后一个 '}' 向前查找匹配的 '{'
        brace_count = 1
        json_start = -1
        for i in range(last_brace_pos - 1, -1, -1):
            if content[i] == '}':
                brace_count += 1
            elif content[i] == '{':
                brace_count -= 1
                if brace_count == 0:
                    json_start = i
                    break
        
        # 如果找到了匹配的 '{'，尝试解析 JSON
        if json_start != -1:
            json_str = content[json_start:last_brace_pos + 1]
            # 检查 JSON 后面是否只有空白或换行
            after_json = content[last_brace_pos + 1:].strip()
            if not after_json or after_json in ['\n', '\r\n']:
                try:
                    parsed_json = json.loads(json_str)
                    # 如果成功解析为字典，说明末尾是 JSON 对象
                    if isinstance(parsed_json, dict):
                        return True
                except:
                    pass
        
        return False

    def stop_chat(self) -> None:
        """停止当前对话"""
        self.should_stop = True

    def set_planning_enabled(self, enabled: bool) -> None:
        """设置是否启用规划功能"""
        self.enable_planning = enabled

    def _should_create_plan(
        self,
        task_message: str,
        plan_status_callback: Optional[Callable[[str], None]] = None,
    ) -> Tuple[bool, str]:
        """
        判断是否应该创建计划（使用 LLM 智能判断）

        Args:
            task_message: 任务消息
            plan_status_callback: 可选的规划状态回调函数，用于更新 header 显示

        Returns:
            (是否需要规划, 判断原因)
        """
        if not self.enable_planning:
            return False, "规划功能已禁用"

        # 如果已经有计划在执行，不创建新计划
        if self.current_plan and self.current_plan.get_progress()["completed"] < len(
            self.current_plan.steps
        ):
            return False, "已有计划正在执行中"

        # 清理消息，去除首尾空白
        message = task_message.strip()

        # 空消息不需要规划
        if not message:
            return False, "消息为空"

        # 使用 LLM 智能判断是否需要规划（完全交给模型判断，不预设规则）
        try:
            if plan_status_callback:
                plan_status_callback("🔍 判断是否需要规划...")

            # 构建标准的判断提示词（参考 OpenAI/Anthropic 最佳实践）
            system_prompt = """You are a task analysis assistant. Your role is to determine whether a user's request requires detailed task planning before execution.

Task planning is needed when:
- The request requires using tools (file operations, command execution, Git operations, etc.)
- The request involves multiple steps or complex workflows
- The request needs to be broken down into smaller actionable steps

Task planning is NOT needed when:
- The request is a simple greeting or expression of gratitude
- The request is a straightforward knowledge question that can be answered directly
- The request is a simple informational query
- The request can reasonably be completed in 1–3 actions, even if it uses tools

Respond with only "yes" or "no" followed by a brief reason in parentheses."""

            user_prompt = f"""Analyze the following user request and determine if it requires detailed task planning:

User request: "{message}"

Respond with: "yes (reason)" or "no (reason)"."""

            # 使用流式输出（使用规划模型）
            stream_response = self.client.chat.completions.create(
                model=config.planning_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Very low temperature for deterministic classification
                stream=True,
                extra_body={"thinking": {"type": "disabled"}},
            )

            result = ""
            try:
                for chunk in stream_response:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            result += delta.content
                            if plan_status_callback:
                                plan_status_callback(f"🔍 判断中: {result[:30]}...")
            finally:
                try:
                    stream_response.close()
                except:
                    pass

            result = result.strip()
            result_lower = result.lower()

            # 解析结果：提取 yes/no 和原因
            needs_planning = any(
                result_lower.startswith(prefix) for prefix in ["yes", "y"]
            )

            # 提取原因（如果有）
            reason = "LLM判断"
            if "(" in result and ")" in result:
                try:
                    reason = result.split("(")[1].split(")")[0].strip()
                except:
                    pass

            logger.debug(
                f"规划判断: '{message}' -> {needs_planning} (原因: {reason}, LLM回答: {result})"
            )
            return needs_planning, reason

        except Exception as e:
            logger.warning(f"规划判断失败: {e}，默认不规划")
            if plan_status_callback:
                plan_status_callback(f"⚠️ 判断失败")
            return False, f"判断失败: {str(e)}"

    def chat(
        self,
        task_message: str,
        output_callback: Optional[Callable[[str, bool], None]] = None,
        plan_status_callback: Optional[Callable[[str], None]] = None,
        status_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        处理用户任务

        Args:
            task_message: 用户任务消息
            output_callback: 可选的输出回调函数，接受 (text, end_newline) 参数
                            如果提供，将使用回调而不是 print
            plan_status_callback: 可选的规划状态回调函数，接受 (status_text) 参数
                                 用于更新 header 中的规划状态显示
            status_callback: 可选的状态更新回调函数，用于实时更新UI状态（如token使用量）
        """
        # 重置中断标志
        self.should_stop = False

        # 定义输出函数
        def output(text: str, end_newline: bool = True):
            if output_callback:
                output_callback(text, end_newline)
            else:
                print(text, end="\n" if end_newline else "", flush=True)

        # 定义规划状态更新函数
        def update_plan_status(status: str):
            if plan_status_callback:
                plan_status_callback(status)

        # 任务规划阶段 - 显示判断结果
        needs_planning, _reason = self._should_create_plan(
            task_message, update_plan_status
        )

        if needs_planning:
            update_plan_status("📋 分析任务中...")

            try:
                self.current_plan = self.task_planner.create_plan(
                    task_message, update_plan_status
                )

                # 更新规划状态为进度显示
                progress = self.current_plan.get_progress()
                update_plan_status(
                    f"📋 计划完成 ({len(self.current_plan.steps)} 步) | 进度: {progress['completed']}/{progress['total']}"
                )

                # 将完整的计划信息添加到消息中，让模型知道计划并可以管理它
                plan_info = f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                plan_info += (
                    f"📋 任务执行计划（共 {len(self.current_plan.steps)} 步）\n"
                )
                plan_info += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                plan_info += f"任务描述：{self.current_plan.task_description}\n\n"
                plan_info += f"当前进度：{progress['completed']}/{progress['total']} 已完成 ({progress['progress_percent']:.1f}%)\n"
                plan_info += f"待执行：{progress['pending']} | 执行中：{progress['in_progress']} | 失败：{progress['failed']}\n\n"
                plan_info += f"执行步骤：\n"
                for step in self.current_plan.steps:
                    status_icon = {
                        StepStatus.PENDING: "⏳",
                        StepStatus.IN_PROGRESS: "🔄",
                        StepStatus.COMPLETED: "✅",
                        StepStatus.FAILED: "❌",
                        StepStatus.SKIPPED: "⏭️",
                    }.get(step.status, "❓")
                    plan_info += (
                        f"{status_icon} 步骤 {step.step_number}: {step.description}"
                    )
                    if step.expected_tools:
                        plan_info += f" [预期工具: {', '.join(step.expected_tools)}]"
                    plan_info += f"\n"
                    if step.status == StepStatus.COMPLETED and step.result:
                        plan_info += f"   ✓ 结果: {step.result[:100]}{'...' if len(step.result) > 100 else ''}\n"
                    elif step.status == StepStatus.FAILED and step.error:
                        plan_info += f"   ✗ 错误: {step.error}\n"
                plan_info += f"\n重要提示：你需要使用任务计划管理工具（update_step_status, move_to_next_step, get_plan_status）来主动管理计划的执行进度。\n"
                plan_info += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                task_message = f"{task_message}{plan_info}"

            except Exception as e:
                logger.error(f"规划失败: {e}")
                update_plan_status(f"⚠️ 规划失败: {str(e)[:30]}")
                self.current_plan = None
        else:
            logger.debug(f"直接执行任务: {task_message}")
            # 清除规划状态
            update_plan_status("")

        self.message_manager.add_user_message(task_message)
        # 重置 reasoning content 追踪（每次新的对话轮次）
        if hasattr(self, "_current_reasoning"):
            delattr(self, "_current_reasoning")
        while True:
            # 检查是否需要中断（在主循环开始时）
            if self.should_stop:
                logger.info("对话在主循环被用户中断")
                # 添加系统消息说明用户中断了对话
                self.message_manager.messages.append(
                    {"role": "system", "content": "[对话已被用户中断]"}
                )
                output("\n\n[对话已被用户中断]", end_newline=True)
                break
            self.chat_count += 1

            # 如果有任务计划，在每次循环开始时将当前计划状态传递给大模型
            if self.current_plan:
                progress = self.current_plan.get_progress()
                current_step = self.current_plan.get_current_step()
                plan_status_info = f"\n[任务计划状态更新]\n"
                plan_status_info += f"进度: {progress['completed']}/{progress['total']} 已完成 ({progress['progress_percent']:.1f}%)\n"
                plan_status_info += f"待执行: {progress['pending']} | 执行中: {progress['in_progress']} | 失败: {progress['failed']}\n"
                if current_step:
                    plan_status_info += f"当前步骤: {current_step.step_number} - {current_step.description} (状态: {current_step.status.value})\n"
                plan_status_info += f"提示: 使用任务计划管理工具（update_step_status, move_to_next_step, get_plan_status）来管理计划进度。\n"
                # 将计划状态作为系统消息添加到消息列表中（只在当前循环中使用）
                # 注意：这里不直接修改message_manager.messages，而是在API调用时临时添加
                messages_with_plan = self.message_manager.get_messages() + [
                    {"role": "system", "content": plan_status_info}
                ]
            else:
                messages_with_plan = self.message_manager.get_messages()

            logger.debug(f"=== Chat Round {self.chat_count} ===")
            logger.debug(
                f"Messages: {json.dumps(messages_with_plan, indent=2, ensure_ascii=False)}"
            )

            # 调用 API（带重试机制）
            max_retries = 3
            retry_count = 0

            while retry_count < max_retries:
                try:
                    stream_response: Stream[ChatCompletionChunk] = (
                        self.client.chat.completions.create(
                            model=config.execution_model,  # 使用执行模型
                            messages=messages_with_plan,  # 使用包含计划状态的消息
                            stream=True,
                            temperature=0.7,
                            top_p=0.8,
                            max_tokens=65535,
                            tools=self._get_tools(),
                            tool_choice="auto",
                            extra_body={"thinking": {"type": "disabled"}},
                        )
                    )
                    break  # 成功则跳出重试循环
                except Exception as e:
                    retry_count += 1
                    logger.error(f"API 调用失败: {e}")
                    raise

            else:
                # 重试次数用尽
                logger.error("API 调用失败: 已达到最大重试次数")
                error_msg = "\n=== 错误信息 ===\nAPI 调用失败: 已达到最大重试次数\n=== 错误信息结束 ===\n"
                output(error_msg, end_newline=True)
                return  # 优雅退出，不抛出异常

            # 处理流式响应
            reasoning_content = "Thinking:\n"
            content = ""
            last_tool_call_id = None
            tool_call_acc = {}
            usage = None

            start_reasoning_content = False
            start_content = False
            start_tool_call = False

            # 初始化 reasoning content 追踪
            self._current_reasoning = ""

            # 定义输出函数（已在方法开始处定义，这里不需要重复定义）

            try:
                for chunk in stream_response:
                    # 检查是否需要中断
                    if self.should_stop:
                        logger.info("流式响应被中断，正在关闭流...")
                        stream_response.close()  # 关闭流，停止后端继续生成
                        break

                    # 获取 usage 信息（通常在最后一个 chunk 中）
                    if hasattr(chunk, "usage") and chunk.usage is not None:
                        usage = chunk.usage

                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta

                        if (
                            hasattr(delta, "reasoning_content")
                            and delta.reasoning_content
                        ):
                            if not start_reasoning_content:
                                output(
                                    f"\n{'='*config.log_separator_length} 模型思考 {'='*config.log_separator_length}\n"
                                )
                                start_reasoning_content = True
                            _reasoning_content = delta.reasoning_content
                            reasoning_content += delta.reasoning_content
                            output(_reasoning_content, end_newline=False)
                            # 实时更新估算的 token（reasoning content 也会消耗 tokens）
                            # 这里我们简单地将 reasoning content 也计入 completion
                            # 注意：reasoning 和 content 是分开的，但都计入 completion tokens
                            if not hasattr(self, "_current_reasoning"):
                                self._current_reasoning = ""
                            self._current_reasoning += _reasoning_content
                            # 估算时考虑 reasoning 和 content
                            total_completion = (
                                self._current_reasoning
                                if hasattr(self, "_current_reasoning")
                                else ""
                            ) + content
                            self.message_manager.update_estimated_tokens(
                                total_completion
                            )
                            # 通知UI更新状态（实时更新token显示）
                            if status_callback:
                                status_callback()

                        if hasattr(delta, "content") and delta.content:
                            if not start_content:
                                output(
                                    f"\n{'='*config.log_separator_length} 最终回复 {'='*config.log_separator_length}\n"
                                )
                                start_content = True
                            chunk_content = delta.content
                            content += chunk_content
                            output(chunk_content, end_newline=False)
                            # 实时更新估算的 token（基于已生成的内容）
                            self.message_manager.update_estimated_tokens(content)
                            # 通知UI更新状态（实时更新token显示）
                            if status_callback:
                                status_callback()

                        if hasattr(delta, "tool_calls") and delta.tool_calls:
                            if not start_tool_call:
                                output(
                                    f"\n{'='*config.log_separator_length} 工具调用 {'='*config.log_separator_length}\n"
                                )
                                start_tool_call = True
                            for tc in delta.tool_calls:
                                tc_id = tc.id or last_tool_call_id

                                if tc_id is None:
                                    # 连第一个 id 都没有，直接跳过（极少见）
                                    continue

                                last_tool_call_id = tc_id

                                if tc_id not in tool_call_acc:
                                    tool_call_acc[tc_id] = {
                                        "id": tc_id,
                                        "name": "",
                                        "arguments": "",
                                    }

                                # 拼 name（虽然一般只来一次，但规范允许拆）
                                if tc.function:
                                    if tc.function.name:
                                        tool_call_acc[tc_id]["name"] += tc.function.name
                                        output(tc.function.name, end_newline=False)
                                    if tc.function.arguments:
                                        tool_call_acc[tc_id][
                                            "arguments"
                                        ] += tc.function.arguments
                                        output(tc.function.arguments, end_newline=False)

                                    # 实时更新估算的 token（工具调用也会消耗 tokens）
                                    # 构建工具调用的完整文本用于估算
                                    tool_call_text = ""
                                    for acc_tc_id, acc_tc_data in tool_call_acc.items():
                                        tool_call_text += acc_tc_data.get(
                                            "name", ""
                                        ) + acc_tc_data.get("arguments", "")
                                    # 估算时考虑 reasoning、content 和 tool_calls
                                    total_completion = (
                                        (
                                            self._current_reasoning
                                            if hasattr(self, "_current_reasoning")
                                            else ""
                                        )
                                        + content
                                        + tool_call_text
                                    )
                                    self.message_manager.update_estimated_tokens(
                                        total_completion
                                    )
                                    # 通知UI更新状态（实时更新token显示）
                                    if status_callback:
                                        status_callback()
            except Exception as e:
                # 如果在处理流时发生异常（包括关闭流），记录日志
                logger.debug(f"流处理异常: {e}")
                # 如果是用户中断，不需要抛出异常
                if not self.should_stop:
                    raise
            finally:
                # 确保流被关闭
                try:
                    stream_response.close()
                except Exception:
                    pass

            # 如果用户中断了对话，将中断信息添加到上下文
            if self.should_stop:
                # 如果有部分内容，先保存
                if content.strip():
                    self.message_manager.add_assistant_content(reasoning_content)
                    self.message_manager.add_assistant_content(content)
                # 添加系统消息说明用户中断了对话
                self.message_manager.messages.append(
                    {
                        "role": "system",
                        "content": "[用户在此处中断了对话，未完成的任务已暂停]",
                    }
                )
                logger.info("已将用户中断信息添加到上下文")
                break

            # 更新 token 使用量（从 API 响应获取）
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                if prompt_tokens is not None:
                    self.message_manager.update_token_usage(prompt_tokens)
                    completion_tokens = getattr(usage, "completion_tokens", 0)
                    total_tokens = getattr(usage, "total_tokens", 0)
                    logger.debug(
                        f"\nToken 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                    )
                    # 清除临时变量
                    if hasattr(self, "_current_reasoning"):
                        delattr(self, "_current_reasoning")
                    # 通知UI更新状态（更新为实际值）
                    if status_callback:
                        status_callback()
                else:
                    logger.warning("\nAPI 响应中未找到 prompt_tokens")
            else:
                logger.warning("\n流式响应中未找到 usage 信息")
                # 即使没有 usage，也清除临时变量
                if hasattr(self, "_current_reasoning"):
                    delattr(self, "_current_reasoning")

            if tool_call_acc:
                # 如果有任务计划，更新UI显示（但不自动更新计划状态，由大模型自己管理）
                if self.current_plan:
                    progress = self.current_plan.get_progress()
                    current_step = self.current_plan.get_current_step()
                    if current_step:
                        update_plan_status(
                            f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%) | 步骤 {current_step.step_number}"
                        )
                    else:
                        update_plan_status(
                            f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%)"
                        )

                for tc_id, tc_data in tool_call_acc.items():
                    # logger.info(f"=== Tool Call ===")
                    # logger.debug(f"name: {tc_data['name']}")
                    # logger.debug(f"arguments: {tc_data['arguments']}")
                    self.message_manager.add_assistant_tool_call(
                        tc_id, tc_data["name"], tc_data["arguments"]
                    )
                    tool_call_result = self.tool_executor.execute(
                        tc_data["name"], tc_data["arguments"]
                    )
                    result_content = None
                    # 处理标准化的返回格式
                    if isinstance(tool_call_result, dict):
                        result_content = json.dumps(
                            tool_call_result, ensure_ascii=False, indent=2
                        )
                        # 检查工具执行是否成功
                        is_success = tool_call_result.get("success", False)
                        tool_result = tool_call_result.get("result", "")
                        tool_error = tool_call_result.get("error")
                    else:
                        # 兼容旧的返回格式
                        result_content = tool_call_result
                        is_success = True  # 假设成功
                        tool_result = tool_call_result
                        tool_error = None

                    # 检查是否是任务计划管理工具，如果是则更新UI显示
                    if self.current_plan and tc_data["name"] in [
                        "update_step_status",
                        "move_to_next_step",
                        "get_plan_status",
                    ]:
                        # 解析工具结果以更新UI
                        try:
                            if isinstance(
                                tool_call_result, dict
                            ) and tool_call_result.get("success"):
                                progress = self.current_plan.get_progress()
                                current_step = self.current_plan.get_current_step()
                                if current_step:
                                    update_plan_status(
                                        f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%) | 步骤 {current_step.step_number}"
                                    )
                                else:
                                    update_plan_status(
                                        f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%)"
                                    )
                        except:
                            pass

                    self.message_manager.add_assistant_tool_call_result(
                        tc_data["id"], result_content
                    )

                continue
            else:
                # 最终回复阶段
                # 检测是否有虚假的工具调用（在思考中假装调用工具）
                if self._detect_fake_tool_call_in_reasoning(reasoning_content):
                    logger.warning("检测到思考内容中有虚假的工具调用，但未实际调用工具")
                    # 保存当前的思考内容和回复内容
                    if reasoning_content.strip():
                        self.message_manager.add_assistant_content(reasoning_content)
                    if content.strip():
                        self.message_manager.add_assistant_content(content)
                    # 添加用户消息，提示继续执行
                    fake_call_message = "sorry, I'm not able to call the tool right now, please try again later..."
                    self.message_manager.add_user_message(fake_call_message)
                    output(f"\n⚠️ 检测到思考中有工具调用意图，但未实际调用。已添加提示消息，继续执行...\n", end_newline=True)
                    # 继续循环
                    continue
                
                # logger.info(f"=== Final Answer ===")
                # logger.info(content)

                # 如果有任务计划，更新UI显示最终进度（但不自动更新计划状态）
                if self.current_plan:
                    final_progress = self.current_plan.get_progress()
                    if final_progress["total"] > 0:
                        # 更新 header 中的规划状态
                        status_text = f"✅ 完成: {final_progress['completed']}/{final_progress['total']} ({final_progress['progress_percent']:.0f}%)"
                        if final_progress["failed"] > 0:
                            status_text += f" ⚠️{final_progress['failed']}"
                        update_plan_status(status_text)

                if reasoning_content.strip():
                    self.message_manager.add_assistant_content(reasoning_content)
                if content.strip():
                    self.message_manager.add_assistant_content(content)
                break
