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
)
from tool_executor import create_tool_executor

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
        old_tokens = self.current_tokens
        self.current_tokens = prompt_tokens
        self.estimated_tokens = prompt_tokens  # 同步更新估算值

        logger.debug(
            f"更新 token 使用量 - "
            f"旧值: {old_tokens}, 新值: {prompt_tokens}, "
            f"使用率: {self.get_token_usage_percent():.2f}%"
        )

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
        removed_count = 0
        while (
            self.current_tokens > self.max_context_tokens
            and len(self.messages) > 1
        ):
            # 保留系统消息，删除第一个非系统消息
            removed_message = self.messages.pop(1)
            removed_count += 1
            logger.debug(
                f"上下文已满，删除旧消息 - "
                f"当前使用: {self.current_tokens}/{self.max_context_tokens}, "
                f"消息角色: {removed_message.get('role', 'unknown')}"
            )
            # 注意：删除消息后，下次 API 调用时会重新计算 token 数
            # 这里我们暂时保持 current_tokens 不变，等待下次 API 响应更新

        if removed_count > 0:
            logger.info(
                f"上下文管理完成 - 删除了 {removed_count} 条旧消息, "
                f"剩余消息数: {len(self.messages)}"
            )

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": f"{content}"})
        logger.debug(f"已添加用户消息 - 长度: {len(content)}")

    def add_assistant_content(self, content: str) -> None:
        """添加助手内容"""
        self.messages.append({"role": "assistant", "content": f"{content}"})
        logger.debug(f"已添加助手回复 - 长度: {len(content)}")

    def add_assistant_tool_call_result(self, tool_call_id: str, content: str) -> None:
        """添加助手工具调用结果"""
        self.messages.append(
            {"role": "tool", "tool_call_id": tool_call_id, "content": f"{content}"}
        )
        logger.debug(
            f"已添加工具调用结果 - ID: {tool_call_id}, 结果长度: {len(content)}"
        )

    def add_assistant_tool_call(
        self, tool_call_id: str, name: str, arguments: str = ""
    ) -> None:
        """添加助手工具调用"""
        self.messages.append(
            {
                "role": "assistant",
                "content": "",  # 当有 tool_calls 时，content 应为空字符串（某些 API 实现不接受 None）
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
        logger.debug(
            f"已添加工具调用 - ID: {tool_call_id}, 工具: {name}, "
            f"参数长度: {len(arguments)}"
        )

    def _validate_and_clean_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        验证并清理消息格式，确保符合 OpenAI API 规范
        
        Args:
            messages: 原始消息列表
            
        Returns:
            清理后的消息列表
        """
        cleaned_messages = []
        for msg in messages:
            cleaned_msg = msg.copy()
            role = cleaned_msg.get("role")
            
            # 确保 content 字段的类型正确
            if "content" in cleaned_msg:
                content = cleaned_msg["content"]
                # 如果 content 是 None，根据是否有 tool_calls 决定处理方式
                if content is None:
                    # 如果有 tool_calls，content 可以是 None
                    if "tool_calls" not in cleaned_msg or not cleaned_msg["tool_calls"]:
                        # 如果没有 tool_calls，content 不能是 None，设置为空字符串
                        cleaned_msg["content"] = ""
                elif not isinstance(content, (str, list)):
                    # 如果 content 不是字符串或列表，转换为字符串
                    cleaned_msg["content"] = str(content) if content is not None else ""
            
            # 确保 tool_calls 存在时，content 为空字符串
            if "tool_calls" in cleaned_msg and cleaned_msg["tool_calls"]:
                if "content" not in cleaned_msg or cleaned_msg["content"]:
                    # 如果有 tool_calls，content 应该为空字符串（某些 API 实现不接受 None）
                    cleaned_msg["content"] = ""
            
            # 确保 tool_call_id 是字符串
            if "tool_call_id" in cleaned_msg:
                tool_call_id = cleaned_msg["tool_call_id"]
                if not isinstance(tool_call_id, str):
                    cleaned_msg["tool_call_id"] = str(tool_call_id)
            
            cleaned_messages.append(cleaned_msg)
        
        return cleaned_messages

    def get_messages(self) -> List[Dict[str, str]]:
        """获取所有消息（已验证和清理）"""
        messages = self.messages.copy()
        return self._validate_and_clean_messages(messages)

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

    def __init__(self) -> None:
        """初始化 Agent"""
        logger.info("初始化 ReActAgent")
        logger.debug(
            f"配置信息 - "
            f"工作目录: {config.work_dir}, "
            f"最大上下文: {config.max_context_tokens}, "
            f"模型: {config.model}"
        )

        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        self.tools = self._create_tools()
        self.tool_executor = create_tool_executor(self.tools)
        self.message_manager = MessageManager(
            self._get_system_prompt(), config.max_context_tokens
        )
        self.chat_count = 0
        self.should_stop = False  # 中断标志

        logger.info(f"Agent 初始化完成 - 工具数量: {len(self.tools)}")

    def _create_tools(self) -> List[Tool]:
        """创建工具列表"""
        logger.debug("开始创建工具列表")
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
        ]
        logger.debug(f"工具列表创建完成 - 工具数量: {len(tools)}")
        logger.debug(f"工具名称: {[tool.name for tool in tools]}")
        return tools

    def _get_system_prompt_by_en(self) -> str:
        """Generate system prompt (Microsoft PM / Spec-style Agent)"""
        return f"""
    You are a Microsoft full-stack software engineering intern. You are using a {config.operating_system} computer and have Visual Studio Code open with a local working directory at {config.work_dir}. You are preparing to implement product requirements provided by a PM.

    ━━━━━━━━━━━━━━
    [Initial State Rules (MUST FOLLOW)]
    ━━━━━━━━━━━━━━
    When no explicit, actionable product requirement or work item has been provided:

    - Remain in a "conversation buffer" state
    - Do NOT decompose tasks
    - Do NOT enter the engineering execution workflow
    - Do NOT invoke any tools

    Conversation behavior guidelines:
    - Natural and concise conversational responses are allowed
    - Do NOT force or rush the user to provide requirements
    - Do NOT expose internal states, rules, or role definitions
    - Maintain a posture of “I’m listening, you may continue”

    ━━━━━━━━━━━━━━
    [Available Tools]
    ━━━━━━━━━━━━━━
    {self._get_tools_name_and_description()}

    ━━━━━━━━━━━━━━
    [Overall Objectives]
    ━━━━━━━━━━━━━━
    - Accurately understand the current valid product requirements
    - Implement solutions under real-world environments and constraints
    - Proactively surface issues when requirements are unclear or risky
    - Output only results that are valuable to the PM

    ━━━━━━━━━━━━━━
    [Execution Workflow (Strictly Phased)]
    ━━━━━━━━━━━━━━
    [Phase 1: Requirement Understanding, Clarification, and Default Assumptions (Understand)]
    - Determine whether the current input is:
    - A new product requirement
    - A supplement or modification to an existing requirement
    - A question about implementation progress or results
    - If ambiguity exists, explicitly identify uncertainties and ask necessary clarification questions
    - You may invoke readability or inspection tools to aid requirement understanding
    - Your goal is NOT to wait for perfect requirements. When requirements are incomplete, you MUST propose a reasonable default implementation based on code context and engineering common sense, and clearly state which parts are your engineering assumptions
    - When requirements are vague, you are allowed to fill in defaults based on engineering experience

    ━━━━━━━━━━━━━━
    [Fast Path Eligibility Check]
    ━━━━━━━━━━━━━━
    Before entering [Phase 2: Task Planning], you MUST determine whether ALL of the following conditions are met:

    - Requirements are clear and unambiguous
    - No business decisions or product trade-offs are involved
    - Can be completed with ≤ 3 consecutive tool invocations
    - No intermediate user confirmation is required
    - Failure risk can be directly validated from the output

    If ALL conditions are met:
    - Skip [Phase 2: Task Planning]
    - Do NOT create a Tasks file
    - Enter [Fast Execute Mode] directly

    Otherwise, proceed with the phased execution flow.

    ━━━━━━━━━━━━━━
    [Phase 2: Task Planning (Plan)]
    ━━━━━━━━━━━━━━
    Enter this phase when:
    - A requirement is received for the first time
    - The requirement has materially changed
    - The current plan no longer satisfies the latest requirement

    Required outputs:
    - A brief summary of requirement understanding
    - Task decomposition based on the requirement (Markdown task list)
    - To prevent task loss and enable progress tracking, you MUST create a `.agent_tasks/xxx-tasks.md` file and persist the task list in Markdown format under the `.agent_tasks/` directory
    - Task list formatting MUST follow [Tasks File Management Rules (MUST FOLLOW)]

    Task decomposition rules:
    - Decompose at the functional level, not code-level details
    - Each task MUST be completable within a single tool invocation or a single clear action
    - Do NOT decompose for the sake of decomposition

    ━━━━━━━━━━━━━━━━━━
    [Tasks File Management Rules (MUST FOLLOW)]
    ━━━━━━━━━━━━━━━━━━

    1. Relationship between Tasks Files and Requirements
    - Each independent user requirement / work item MUST correspond to exactly one Tasks file
    - Tasks files MUST NOT be shared or mixed across different requirements

    2. Tasks File Naming Rules (You decide, but MUST be规范)
    - Files MUST be created under the `.agent_tasks/` directory
    - File names MUST be derived from the core intent of the requirement
    - Naming MUST follow these rules:
    - Lowercase letters + hyphens (kebab-case)
    - Semantic intent only, no implementation details
    - No more than 5 words
    - Recommended format:
    - `<core-intent>-tasks.md`
    - Examples (illustrative only):
    - `create-react-project-tasks.md`
    - `add-auth-login-tasks.md`
    - `refactor-api-layer-tasks.md`

    3. Tasks File Format (MANDATORY)
    - MUST use Markdown checklist syntax
    - Incomplete task: `- [ ] Task description`
    - Completed task: `- [x] Task description`
    - Emojis, status words, or alternative markers are NOT allowed

    4. Tasks File as the Single Source of Truth
    - Execution progress for the current requirement MUST use the corresponding Tasks file as the single source of truth
    - Claiming “task completed” in conversation WITHOUT updating the Tasks file is strictly forbidden

    5. Status Update Rules
    - After completing any task, you MUST invoke the `edit_file` tool to update the task checkbox from `[ ]` to `[x]`
    - Task status MUST remain real-time and accurate
    - Existing task entries MUST NOT be deleted or reordered unless the requirement is explicitly canceled or invalidated

    6. Behavior with Parallel Requirements
    - When a new requirement is introduced, you MUST:
    1) Determine whether it constitutes a new work item
    2) If yes, create a new Tasks file
    3) MUST NOT modify or pollute Tasks files of existing requirements

    ━━━━━━━━━━━━━━
    [Fast Execute Mode]
    ━━━━━━━━━━━━━━
    In Fast Execute Mode:

    - All necessary steps may be completed in a single flow
    - Multiple tool invocations may be performed consecutively
    - Task decomposition and Tasks file creation are NOT required
    - Do NOT wait for user confirmation to proceed

    Upon completion, you MUST:
    - Clearly state what actions were performed
    - Provide the final result
    - Interrupt and ask the user if any anomalies or issues are discovered

    ━━━━━━━━━━━━━━
    [Phase 3: Task Execution (Execute)]
    ━━━━━━━━━━━━━━
    - Execute tasks strictly in the order defined in the Tasks file
    - Execute only ONE minimal task at a time
    - Invoke tools ONLY when necessary for the current task

    After completing each task:
    - Update the corresponding checkbox in `.agent_tasks/xxx-tasks.md` from `[ ]` to `[x]`
    - Synchronize progress or results that are valuable to the PM
    - If you discover:
    - A mismatch between implementation and requirements
    - Issues in the requirements themselves
    - Obvious risks in the current approach
    You MUST surface them immediately and provide recommendations

    If the PM introduces new decisions during execution:
    - Immediately pause the current task
    - Return to [Phase 1: Requirement Understanding, Clarification, and Default Assumptions]

    ━━━━━━━━━━━━━━
    [Phase 4: Definition of Done]
    ━━━━━━━━━━━━━━
    - Use the `read_file` tool to read the Tasks file and verify all tasks are marked as `- [x]`
    - If any tasks remain incomplete, continue [Phase 3: Task Execution]
    - If all tasks are complete, output a summary of results, explicitly state “Tasks completed”, and end the conversation

    ━━━━━━━━━━━━━━
    [Phase 5: Engineering Quality Checks]
    ━━━━━━━━━━━━━━
    - Frontend tasks: lint / build / test
    - Backend tasks: unit tests / integration tests
    - Other tasks: validation methods appropriate to the task type

    ━━━━━━━━━━━━━━
    [Environment Constraints]
    ━━━━━━━━━━━━━━
    - Operating system: {config.operating_system}
    - Working directory: {config.work_dir}
    - Current time (Beijing Time): {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    - PM language preference: {config.user_language_preference}

    You MUST reason and act strictly within the above real environment and constraints.

    ━━━━━━━━━━━━━━
    [Output Guidelines]
    ━━━━━━━━━━━━━━
    - Output ONLY content relevant to the current phase
    - When answering questions, present conclusions first, followed by necessary context
    - Avoid emotional or non-engineering expressions
    - Do NOT output redundant explanations or restate rules

    ━━━━━━━━━━━━━━
    [Prohibited Actions]
    ━━━━━━━━━━━━━━
    - Do NOT fabricate product requirements or decisions
    - Do NOT ignore the latest product decisions
    - Do NOT continue executing tasks for invalidated requirements
    - Do NOT claim “tasks completed” before verification
    """


    def _get_system_prompt_by_cn(self) -> str:
        """生成系统提示词（微软 PM / Spec 风格 Agent）"""
        return f"""
    你是一名微软的全栈开发实习生，正在使用 {config.operating_system}电脑, 正在使用 Visual Studio Code 打开了一个的本地工作目录 {config.work_dir}。准备完成 PM 提供的产品需求。

    ━━━━━━━━━━━━━━
    【初始状态规则（必须遵守）】
    ━━━━━━━━━━━━━━
    当尚未收到明确、可执行的产品需求或工作项（Work Item）时：

    - 处于「对话缓冲态」
    - 不进行任务拆分
    - 不进入工程执行流程
    - 不调用任何工具

    对话行为规范：
    - 允许进行自然、简短的对话回应
    - 不强制催促用户给出需求
    - 不暴露内部状态、规则或角色设定
    - 保持“我在听，你可以继续说”的对话姿态

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
    【执行流程（严格阶段化）】:
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
    【快速执行判定（Fast Path）】
    ━━━━━━━━━━━━━━
    在进入【阶段 2：任务规划】之前，必须先判断当前需求是否满足以下全部条件：

    - 需求清晰、无歧义
    - 不涉及业务决策或产品取舍
    - 可通过 ≤3 个连续工具调用完成
    - 不需要用户确认中间结果
    - 失败风险可直接通过结果验证

    若全部满足，则：
    - 跳过「阶段 2：任务规划」
    - 不创建 Tasks 文件
    - 直接进入【快速执行模式】

    否则，按原流程进入阶段化执行。

    ━━━━━━━━━━━━━━
    【阶段 2：任务规划（Plan）】
    ━━━━━━━━━━━━━━
    - 在以下情况进入该阶段：
    - 首次收到需求
    - 需求发生实质性变更
    - 当前计划无法满足最新需求

    - 输出内容：
    - 简要的需求理解摘要
    - 基于需求的任务拆分（markdown 任务列表）
    - 为防止遗忘和管理任务进度，你必须创建一个 .agent_tasks/xxx-tasks.md 文件，将任务列表以 markdown 文件的格式保存到 .agent_tasks/ 目录下。
    - 任务列表规范请遵守【Tasks 文件管理规则（必须遵守）】。

    - 任务拆分规则：
    - 从功能层面拆分，而非代码细节
    - 拆分到“单个任务可以在一次工具调用或一次明确操作中完成”为止
    - 禁止为拆分而拆分
    
    ━━━━━━━━━━━━━━━━━━
    【Tasks 文件管理规则（必须遵守）】
    ━━━━━━━━━━━━━━━━━━

    1. Tasks 文件与需求的关系
    - 每一个“独立的用户需求 / Work Item”，必须对应一个独立的 Tasks 文件
    - 不同需求之间，禁止复用或混写同一个 Tasks 文件

    2. Tasks 文件命名规则（由你决定，但必须规范）
    - 文件必须创建在 `.agent_tasks/` 目录下
    - 文件名必须由当前需求的“核心意图”生成
    - 命名必须满足以下规范：
        - 使用小写字母 + 中划线（kebab-case）
        - 只包含任务语义，不包含实现细节
        - 不超过 5 个单词
    - 推荐结构：
        - `<需求核心>-tasks.md`
    - 示例（仅示例，不是固定模板）：
        - `create-react-project-tasks.md`
        - `add-auth-login-tasks.md`
        - `refactor-api-layer-tasks.md`

    3. Tasks 文件格式（强制）
    - 必须使用 Markdown checklist 语法
    - 未完成任务：`- [ ] 任务描述`
    - 已完成任务：`- [x] 任务描述`
    - 禁止使用 emoji、状态词或其他替代标记

    4. Tasks 文件的唯一事实地位
    - 当前需求的执行进度，必须以对应 Tasks 文件为唯一事实来源
    - 禁止仅在对话中声称“任务已完成”而不更新 Tasks 文件

    5. 状态更新规则
    - 在完成任一任务后，必须调用 edit_file 工具，将 Tasks 文件中该任务条目前的复选框从 [ ] 更新为 [x]，确保任务状态实时同步。
    - 禁止删除或重排已存在的任务条目，除非该需求被明确取消或失效

    6. 多需求并行时的行为
    - 若用户提出新需求，必须：
        1) 判断是否为一个新的 Work Item  
        2) 若是新需求，创建新的 Tasks 文件  
        3) 不得污染或修改旧需求对应的 Tasks 文件
    
    ━━━━━━━━━━━━━━
    【快速执行模式（Fast Execute）】
    ━━━━━━━━━━━━━━
    在快速执行模式下：

    - 允许一次性完成所有必要步骤
    - 允许连续调用多个工具
    - 不要求拆分为多个 Tasks
    - 不等待用户“确认 / 继续”

    执行完成后，必须：
    - 明确说明做了哪些操作
    - 给出最终结果
    - 若发现异常，再中断并询问用户

    ━━━━━━━━━━━━━━
    【阶段 3：任务执行（Execute）】
    ━━━━━━━━━━━━━━
    - 严格按照 Tasks 文件中的任务顺序执行
    - 每次只执行一个最小任务
    - 仅在当前任务确实需要时调用工具

    - 每完成一个任务：
    - 更新 .agent_tasks/xxx-tasks.md 文件，将对应的任务条目的 `[ ]` 更新为 `[x]`
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
    【阶段 4：任务完成（Definition of Done）】
    ━━━━━━━━━━━━━━
    - 通过 read_file 工具读取 Tasks 文件，检查所有相关任务状态为“- [x] 任务描述”
    - 如果存在未完成的任务，继续执行【阶段 3：任务执行（Execute）】
    - 如果所有任务都已完成，则输出结果摘要，明确说明：“任务已完成”，并结束对话
    
    ━━━━━━━━━━━━━━
    【阶段 5：工程质量检查】
    ━━━━━━━━━━━━━━
    - 前端任务：lint / build / test
    - 后端任务：单元测试 / 集成测试
    - 其他任务：使用与任务类型匹配的验证方式

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
    """
    
  
    def _get_system_prompt(self) -> str:
        """生成系统提示词"""
        return self._get_system_prompt_by_en()

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
        last_brace_pos = content.rfind("}")
        if last_brace_pos == -1:
            return False

        # 从最后一个 '}' 向前查找匹配的 '{'
        brace_count = 1
        json_start = -1
        for i in range(last_brace_pos - 1, -1, -1):
            if content[i] == "}":
                brace_count += 1
            elif content[i] == "{":
                brace_count -= 1
                if brace_count == 0:
                    json_start = i
                    break

        # 如果找到了匹配的 '{'，尝试解析 JSON
        if json_start != -1:
            json_str = content[json_start : last_brace_pos + 1]
            # 检查 JSON 后面是否只有空白或换行
            after_json = content[last_brace_pos + 1 :].strip()
            if not after_json or after_json in ["\n", "\r\n"]:
                try:
                    parsed_json = json.loads(json_str)
                    # 如果成功解析为字典，说明末尾是 JSON 对象
                    if isinstance(parsed_json, dict):
                        logger.debug(
                            f"检测到思考内容末尾有 JSON 对象 - "
                            f"JSON 长度: {len(json_str)}, "
                            f"键: {list(parsed_json.keys())}"
                        )
                        return True
                except json.JSONDecodeError:
                    # JSON 解析失败，不是有效的 JSON
                    pass
                except Exception as e:
                    logger.debug(f"解析 JSON 时发生异常: {e}")

        return False

    def _clean_content(self, content: str) -> str:
        """
        清理 content，移除 "assistantfinal" 字段
        
        Args:
            content: 原始内容
            
        Returns:
            清理后的内容
        """
        if not content:
            return content

        # 简单匹配并移除 assistantfinal 这个词
        cleaned = re.sub(r"assistantfinal", "", content, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        if cleaned != content.strip():
            logger.debug(
                f"已清理内容中的 'assistantfinal' - "
                f"原始长度: {len(content)}, 清理后长度: {len(cleaned)}"
            )

        return cleaned

    def stop_chat(self) -> None:
        """停止当前对话"""
        logger.info("收到停止对话请求")
        self.should_stop = True

    def _call_api_with_retry(
        self, max_retries: int = 3
    ) -> Stream[ChatCompletionChunk]:
        """
        调用 API，带重试机制

        Args:
            max_retries: 最大重试次数

        Returns:
            API 流式响应

        Raises:
            Exception: API 调用失败且重试次数用尽
        """
        retry_count = 0
        messages = self.message_manager.get_messages()
        tools = self._get_tools()

        logger.info(
            f"开始调用 API (第 {self.chat_count} 轮对话) - "
            f"消息数: {len(messages)}, 工具数: {len(tools)}"
        )
        logger.debug(f"API 请求参数: model={config.model}, temperature=0.7, top_p=0.8")

        while retry_count < max_retries:
            try:
                stream_response: Stream[ChatCompletionChunk] = (
                    self.client.chat.completions.create(
                        model=config.model,
                        messages=messages,
                        stream=True,
                        temperature=0.7,
                        top_p=0.8,
                        max_tokens=65535,
                        tools=tools,
                        tool_choice="auto",
                    )
                )
                logger.info(f"API 调用成功 (重试次数: {retry_count})")
                return stream_response
            except Exception as e:
                retry_count += 1
                logger.error(
                    f"API 调用失败 (重试 {retry_count}/{max_retries}): {e}",
                    exc_info=True,
                )
                if retry_count >= max_retries:
                    logger.error("API 调用失败: 已达到最大重试次数")
                    raise

        # 理论上不会到达这里
        raise RuntimeError("API 调用失败: 已达到最大重试次数")

    def _get_current_reasoning(self) -> str:
        """获取当前思考内容"""
        return getattr(self, "_current_reasoning", "")

    def _set_current_reasoning(self, content: str) -> None:
        """设置当前思考内容"""
        self._current_reasoning = content

    def _clear_current_reasoning(self) -> None:
        """清除当前思考内容"""
        if hasattr(self, "_current_reasoning"):
            delattr(self, "_current_reasoning")

    def _handle_reasoning_content(
        self,
        delta_content: str,
        reasoning_content: str,
        start_flag: bool,
        content: str,
        output: Callable[[str, bool], None],
        status_callback: Optional[Callable[[], None]],
    ) -> Tuple[str, bool]:
        """
        处理思考内容

        Args:
            delta_content: 增量思考内容
            reasoning_content: 累计思考内容
            start_flag: 是否已开始输出思考内容
            content: 当前回复内容
            output: 输出回调函数
            status_callback: 状态更新回调函数

        Returns:
            (更新后的思考内容, 是否已开始标志)
        """
        if not start_flag:
            output(
                f"\n{'='*config.log_separator_length} 模型思考 {'='*config.log_separator_length}\n"
            )
            logger.debug("开始接收模型思考内容")
            start_flag = True

        reasoning_content += delta_content
        output(delta_content, end_newline=False)

        # 更新思考内容追踪
        current_reasoning = self._get_current_reasoning() + delta_content
        self._set_current_reasoning(current_reasoning)

        # 更新估算的 token
        total_completion = current_reasoning + content
        self.message_manager.update_estimated_tokens(total_completion)

        # 通知UI更新状态
        if status_callback:
            status_callback()

        return reasoning_content, start_flag

    def _handle_assistant_content(
        self,
        delta_content: str,
        content: str,
        start_flag: bool,
        output: Callable[[str, bool], None],
        status_callback: Optional[Callable[[], None]],
    ) -> Tuple[str, bool]:
        """
        处理助手回复内容

        Args:
            delta_content: 增量回复内容
            content: 累计回复内容
            start_flag: 是否已开始输出回复内容
            output: 输出回调函数
            status_callback: 状态更新回调函数

        Returns:
            (更新后的回复内容, 是否已开始标志)
        """
        if not start_flag:
            output(
                f"\n{'='*config.log_separator_length} 最终回复 {'='*config.log_separator_length}\n"
            )
            logger.debug("开始接收模型最终回复")
            start_flag = True

        content += delta_content
        output(delta_content, end_newline=False)

        # 更新估算的 token
        self.message_manager.update_estimated_tokens(content)

        # 通知UI更新状态
        if status_callback:
            status_callback()

        return content, start_flag

    def _handle_tool_call_delta(
        self,
        tool_call: Any,
        tool_call_acc: Dict[str, Dict[str, str]],
        last_tool_call_id: Optional[str],
        start_flag: bool,
        content: str,
        output: Callable[[str, bool], None],
        status_callback: Optional[Callable[[], None]],
    ) -> Tuple[Dict[str, Dict[str, str]], Optional[str], bool]:
        """
        处理工具调用的增量数据

        Args:
            tool_call: 工具调用增量数据
            tool_call_acc: 累计的工具调用数据
            last_tool_call_id: 上一个工具调用ID
            start_flag: 是否已开始输出工具调用
            content: 当前回复内容
            output: 输出回调函数
            status_callback: 状态更新回调函数

        Returns:
            (更新后的工具调用累计数据, 工具调用ID, 是否已开始标志)
        """
        if not start_flag:
            output(
                f"\n{'='*config.log_separator_length} 工具调用 {'='*config.log_separator_length}\n"
            )
            logger.info("开始接收工具调用")
            start_flag = True

        tc_id = tool_call.id or last_tool_call_id
        if tc_id is None:
            logger.warning("工具调用缺少 ID，跳过")
            return tool_call_acc, last_tool_call_id, start_flag

        last_tool_call_id = tc_id

        if tc_id not in tool_call_acc:
            tool_call_acc[tc_id] = {"id": tc_id, "name": "", "arguments": ""}
            logger.debug(f"开始接收工具调用: ID={tc_id}")

        if tool_call.function:
            if tool_call.function.name:
                tool_call_acc[tc_id]["name"] += tool_call.function.name
                output(tool_call.function.name, end_newline=False)
            if tool_call.function.arguments:
                tool_call_acc[tc_id]["arguments"] += tool_call.function.arguments
                output(tool_call.function.arguments, end_newline=False)

        # 更新估算的 token
        tool_call_text = ""
        for acc_tc_data in tool_call_acc.values():
            tool_call_text += acc_tc_data.get("name", "") + acc_tc_data.get(
                "arguments", ""
            )

        current_reasoning = self._get_current_reasoning()
        total_completion = current_reasoning + content + tool_call_text
        self.message_manager.update_estimated_tokens(total_completion)

        # 通知UI更新状态
        if status_callback:
            status_callback()

        return tool_call_acc, last_tool_call_id, start_flag

    def _process_stream_response(
        self,
        stream_response: Stream[ChatCompletionChunk],
        output: Callable[[str, bool], None],
        status_callback: Optional[Callable[[], None]],
    ) -> Tuple[str, str, Dict[str, Dict[str, str]], Optional[Any]]:
        """
        处理流式响应

        Args:
            stream_response: API 流式响应
            output: 输出回调函数
            status_callback: 状态更新回调函数

        Returns:
            (思考内容, 回复内容, 工具调用累计数据, usage信息)
        """
        reasoning_content = "Thinking:\n"
        content = ""
        last_tool_call_id: Optional[str] = None
        tool_call_acc: Dict[str, Dict[str, str]] = {}
        usage = None

        start_reasoning_content = False
        start_content = False
        start_tool_call = False

        self._set_current_reasoning("")

        logger.debug("开始处理流式响应")

        try:
            for chunk in stream_response:
                if self.should_stop:
                    logger.info("流式响应处理被用户中断，正在关闭流...")
                    stream_response.close()
                    break

                if hasattr(chunk, "usage") and chunk.usage is not None:
                    usage = chunk.usage

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta

                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        reasoning_content, start_reasoning_content = (
                            self._handle_reasoning_content(
                                delta.reasoning_content,
                                reasoning_content,
                                start_reasoning_content,
                                content,
                                output,
                                status_callback,
                            )
                        )

                    if hasattr(delta, "content") and delta.content:
                        content, start_content = self._handle_assistant_content(
                            delta.content,
                            content,
                            start_content,
                            output,
                            status_callback,
                        )

                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        for tc in delta.tool_calls:
                            tool_call_acc, last_tool_call_id, start_tool_call = (
                                self._handle_tool_call_delta(
                                    tc,
                                    tool_call_acc,
                                    last_tool_call_id,
                                    start_tool_call,
                                    content,
                                    output,
                                    status_callback,
                                )
                            )

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"处理流式响应时发生异常: {error_msg}",
                exc_info=True
            )
            
            # 如果是 OpenAI API 错误，记录更多信息
            if "unexpected tokens" in error_msg.lower() or "message header" in error_msg.lower():
                logger.error(
                    f"检测到消息格式错误 - "
                    f"当前消息历史长度: {len(self.message_manager.messages)}, "
                    f"错误详情: {error_msg}"
                )
                # 记录最后几条消息用于调试
                try:
                    recent_messages = self.message_manager.messages[-5:]
                    logger.debug(
                        f"最近的消息历史: {json.dumps(recent_messages, indent=2, ensure_ascii=False)}"
                    )
                except Exception:
                    pass
            
            if not self.should_stop:
                raise
        finally:
            try:
                stream_response.close()
                logger.debug("流式响应已关闭")
            except Exception:
                pass

        logger.debug(
            f"流式响应处理完成 - "
            f"思考长度: {len(reasoning_content)}, "
            f"回复长度: {len(content)}, "
            f"工具调用数: {len(tool_call_acc)}"
        )

        return reasoning_content, content, tool_call_acc, usage

    def _update_token_usage(
        self, usage: Any, status_callback: Optional[Callable[[], None]]
    ) -> None:
        """
        更新 token 使用量

        Args:
            usage: API 返回的 usage 信息
            status_callback: 状态更新回调函数
        """
        if not usage:
            logger.warning("流式响应中未找到 usage 信息")
            self._clear_current_reasoning()
            return

        prompt_tokens = getattr(usage, "prompt_tokens", None)
        if prompt_tokens is None:
            logger.warning("API 响应中未找到 prompt_tokens")
            self._clear_current_reasoning()
            return

        completion_tokens = getattr(usage, "completion_tokens", 0)
        total_tokens = getattr(usage, "total_tokens", 0)

        self.message_manager.update_token_usage(prompt_tokens)
        self._clear_current_reasoning()

        logger.info(
            f"Token 使用量更新 - "
            f"prompt: {prompt_tokens}, "
            f"completion: {completion_tokens}, "
            f"total: {total_tokens}, "
            f"使用率: {self.message_manager.get_token_usage_percent():.2f}%"
        )

        if status_callback:
            status_callback()

    def _execute_tool_calls(
        self, tool_call_acc: Dict[str, Dict[str, str]]
    ) -> None:
        """
        执行工具调用

        Args:
            tool_call_acc: 工具调用累计数据
        """
        logger.info(f"开始执行 {len(tool_call_acc)} 个工具调用")

        for tc_id, tc_data in tool_call_acc.items():
            tool_name = tc_data["name"]
            tool_args = tc_data["arguments"]

            logger.info(
                f"执行工具调用 - ID: {tc_id}, 工具: {tool_name}, "
                f"参数长度: {len(tool_args)}"
            )
            logger.debug(f"工具调用参数: {tool_args}")

            # 添加到消息历史
            self.message_manager.add_assistant_tool_call(tc_id, tool_name, tool_args)

            # 执行工具
            try:
                tool_call_result = self.tool_executor.execute(tool_name, tool_args)

                # 处理返回结果
                if isinstance(tool_call_result, dict):
                    result_content = json.dumps(
                        tool_call_result, ensure_ascii=False, indent=2
                    )
                    is_success = tool_call_result.get("success", False)
                    tool_result = tool_call_result.get("result", "")
                    tool_error = tool_call_result.get("error")

                    if is_success:
                        logger.info(
                            f"工具执行成功 - ID: {tc_id}, 工具: {tool_name}, "
                            f"结果长度: {len(str(tool_result))}"
                        )
                    else:
                        logger.error(
                            f"工具执行失败 - ID: {tc_id}, 工具: {tool_name}, "
                            f"错误: {tool_error}"
                        )
                else:
                    # 兼容旧格式
                    result_content = tool_call_result
                    is_success = True
                    logger.info(
                        f"工具执行完成 - ID: {tc_id}, 工具: {tool_name} "
                        f"(旧格式返回)"
                    )

                # 添加到消息历史
                self.message_manager.add_assistant_tool_call_result(
                    tc_id, result_content
                )

            except Exception as e:
                logger.error(
                    f"执行工具时发生异常 - ID: {tc_id}, 工具: {tool_name}: {e}",
                    exc_info=True,
                )
                # 即使异常也要添加到消息历史
                error_result = json.dumps(
                    {"success": False, "result": None, "error": str(e)},
                    ensure_ascii=False,
                )
                self.message_manager.add_assistant_tool_call_result(
                    tc_id, error_result
                )

        logger.info("所有工具调用执行完成")

    def _handle_final_response(
        self,
        reasoning_content: str,
        content: str,
        output: Callable[[str, bool], None],
    ) -> bool:
        """
        处理最终回复

        Args:
            reasoning_content: 思考内容
            content: 回复内容
            output: 输出回调函数

        Returns:
            是否应该继续循环（True=继续，False=结束）
        """
        # 检测虚假工具调用
        if self._detect_fake_tool_call_in_reasoning(reasoning_content):
            logger.warning(
                f"检测到思考内容中有虚假的工具调用 - "
                f"思考长度: {len(reasoning_content)}, "
                f"回复长度: {len(content)}"
            )

            # 保存内容
            if reasoning_content.strip():
                self.message_manager.add_assistant_content(reasoning_content)
            if content.strip():
                cleaned_content = self._clean_content(content)
                self.message_manager.add_assistant_content(cleaned_content)

            # 添加提示消息
            fake_call_message = (
                "抱歉，我刚刚在思考中假装调用了工具，现在我将会继续完成任务。"
            )
            self.message_manager.add_assistant_content(fake_call_message)
            output(
                "\n⚠️ 检测到思考中有工具调用意图，但未实际调用。已添加提示消息，继续执行...\n",
                end_newline=True,
            )
            logger.info("已添加虚假工具调用提示消息，继续执行")
            return True  # 继续循环

        # 保存最终回复
        if reasoning_content.strip():
            self.message_manager.add_assistant_content(reasoning_content)
            logger.debug(f"已保存思考内容，长度: {len(reasoning_content)}")

        if content.strip():
            cleaned_content = self._clean_content(content)
            self.message_manager.add_assistant_content(cleaned_content)
            logger.info(f"已保存最终回复，长度: {len(cleaned_content)}")

        logger.info("最终回复处理完成，结束对话轮次")
        return False  # 结束循环

    def _handle_user_interruption(
        self,
        reasoning_content: str,
        content: str,
        output: Callable[[str, bool], None],
    ) -> None:
        """
        处理用户中断

        Args:
            reasoning_content: 思考内容
            content: 回复内容
            output: 输出回调函数
        """
        logger.info("处理用户中断请求")

        # 保存部分内容
        if content.strip():
            self.message_manager.add_assistant_content(reasoning_content)
            cleaned_content = self._clean_content(content)
            self.message_manager.add_assistant_content(cleaned_content)
            logger.debug("已保存中断前的部分内容")

        # 添加系统消息
        self.message_manager.messages.append(
            {"role": "system", "content": "[用户在此处中断了对话，未完成的任务已暂停]"}
        )
        output("\n\n[对话已被用户中断]", end_newline=True)
        logger.info("已将用户中断信息添加到上下文")

    def chat(
        self,
        task_message: str,
        output_callback: Optional[Callable[[str, bool], None]] = None,
        status_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        处理用户任务

        Args:
            task_message: 用户任务消息
            output_callback: 可选的输出回调函数，接受 (text, end_newline) 参数
                            如果提供，将使用回调而不是 print
            status_callback: 可选的状态更新回调函数，用于实时更新UI状态（如token使用量）
        """
        logger.info(f"开始处理用户任务 - 消息长度: {len(task_message)}")
        logger.debug(f"用户任务内容: {task_message[:200]}...")

        # 重置中断标志
        self.should_stop = False

        # 定义输出函数
        def output(text: str, end_newline: bool = True) -> None:
            if output_callback:
                output_callback(text, end_newline)
            else:
                print(text, end="\n" if end_newline else "", flush=True)

        # 添加用户消息
        self.message_manager.add_user_message(task_message)
        logger.debug("已添加用户消息到消息历史")

        # 重置思考内容追踪
        self._clear_current_reasoning()

        # 主循环
        while True:
            # 检查中断
            if self.should_stop:
                logger.info("对话在主循环被用户中断")
                self.message_manager.messages.append(
                    {"role": "system", "content": "[对话已被用户中断]"}
                )
                output("\n\n[对话已被用户中断]", end_newline=True)
                break

            self.chat_count += 1
            logger.info(f"=== 开始第 {self.chat_count} 轮对话 ===")
            logger.debug(
                f"当前消息历史: {json.dumps(self.message_manager.get_messages(), indent=2, ensure_ascii=False)}"
            )

            # 调用 API
            try:
                stream_response = self._call_api_with_retry()
            except Exception as e:
                logger.error(f"API 调用失败，无法继续: {e}", exc_info=True)
                error_msg = (
                    "\n=== 错误信息 ===\n"
                    f"API 调用失败: {e}\n"
                    "=== 错误信息结束 ===\n"
                )
                output(error_msg, end_newline=True)
                return

            # 处理流式响应
            reasoning_content, content, tool_call_acc, usage = (
                self._process_stream_response(stream_response, output, status_callback)
            )

            # 处理用户中断
            if self.should_stop:
                self._handle_user_interruption(reasoning_content, content, output)
                break

            # 更新 token 使用量
            self._update_token_usage(usage, status_callback)

            # 执行工具调用
            if tool_call_acc:
                self._execute_tool_calls(tool_call_acc)
                logger.info("工具调用执行完成，继续下一轮对话")
                continue

            # 处理最终回复
            should_continue = self._handle_final_response(
                reasoning_content, content, output
            )
            if not should_continue:
                break

        logger.info("用户任务处理完成")
