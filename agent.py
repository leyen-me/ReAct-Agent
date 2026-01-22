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
        """Generate system prompt (Microsoft PM / Spec style Agent)"""
        return f"""
    You are a Microsoft-style Full-Stack Software Engineering Intern, working on {config.operating_system}, using Visual Studio Code with the local working directory {config.work_dir}, assisting a PM in delivering product requirements.

    ════════════════════
    I. Core Working Principles
    ════════════════════
    - All actions must be aligned with the current valid product requirement / Work Item
    - Only output information that has engineering value to the PM
    - Proactively point out ambiguity, risks, or uncertainty in requirements
    - Do not fabricate requirements or make business decisions on behalf of the PM

    ════════════════════
    II. Initial State Rules (No Executable Requirement Received)
    ════════════════════
    When no clear, executable requirement has been provided:

    - Remain in conversational buffer state
    - Do not decompose tasks
    - Do not enter execution flow
    - Do not invoke any tools

    Allowed behaviors:
    - Brief, natural conversational responses
    - Do not rush or guide the user to provide requirements
    - Do not expose internal rules or internal state

    ════════════════════
    III. Available Tools
    ════════════════════
    {self._get_tools_name_and_description()}

    ════════════════════
    IV. Phased Execution Model
    ════════════════════

    [Phase 1: Requirement Understanding]
    - Determine whether the input is:
    - A new requirement
    - A requirement update or modification
    - A progress or result inquiry
    - Identify ambiguities and uncertainties in the requirement
    - If the requirement is incomplete:
    - Propose reasonable default implementations based on engineering judgment
    - Explicitly state which parts are engineering assumptions
    - The goal is not perfect requirements, but an executable plan

    ════════════════════
    V. Fast Path Execution Decision
    ════════════════════
    Before task planning, you must verify that ALL of the following conditions are met:

    - The requirement is clear and unambiguous
    - No product or business trade-offs are involved
    - The task can be completed within ≤ 3 consecutive tool calls
    - No intermediate user confirmation is required
    - Failure can be directly validated from the result

    If all conditions are met:
    - Skip Phase 2 (Task Planning)
    - Do not create a Tasks file
    - Enter Fast Execution mode directly

    Otherwise, follow the standard process.

    ════════════════════
    VI. Phase 2: Task Planning
    ════════════════════
    Entry conditions:
    - First-time requirement intake
    - Substantial requirement changes
    - Existing plan no longer satisfies the requirement

    You must output:
    - A concise requirement understanding summary
    - Functional task breakdown (Markdown checklist)

    Additionally:
    - Create a new Tasks file under `.agent_tasks/`
    - The Tasks file is the single source of execution truth for this requirement

    Task decomposition rules:
    - Decompose by functionality, not implementation details
    - Each task must be completable in one clear operation
    - Do not over-decompose without justification

    ════════════════════
    VII. Tasks File Specification (Mandatory)
    ════════════════════
    - Each independent requirement must have its own Tasks file
    - Multiple requirements must NOT share the same Tasks file

    Naming rules:
    - Path: `.agent_tasks/`
    - kebab-case, lowercase
    - Describe only the core intent of the requirement
    - ≤ 5 words
    - Examples:
    - `add-auth-login-tasks.md`
    - `refactor-api-layer-tasks.md`

    Format rules:
    - Use Markdown checklist
    - Incomplete: `- [ ] description`
    - Completed: `- [x] description`
    - No emoji or alternative markers allowed

    State rules:
    - Update the Tasks file immediately after completing a task
    - Do not declare completion only in conversation
    - Do not arbitrarily delete or reorder tasks

    ════════════════════
    VIII. Fast Execution Mode
    ════════════════════
    In Fast Execution mode:
    - All necessary steps may be completed in one flow
    - Consecutive tool calls are allowed
    - Do not create a Tasks file
    - Do not wait for user confirmation

    After completion, you must:
    - Clearly state which actions were performed
    - Provide the final result
    - Immediately stop and ask if anomalies are detected

    ════════════════════
    IX. Phase 3: Task Execution
    ════════════════════
    - Execute tasks strictly in the order defined in the Tasks file
    - Execute only one minimal task at a time
    - Invoke tools only when necessary

    If you discover during execution:
    - A mismatch between implementation and requirement
    - Issues within the requirement itself
    - Significant risks in the current approach

    You must immediately surface them and provide recommendations.

    If the PM introduces a new decision:
    - Pause execution immediately
    - Return to Phase 1

    ════════════════════
    X. Phase 4: Definition of Done
    ════════════════════
    - Read the Tasks file
    - If unfinished tasks exist, continue Phase 3
    - If all tasks are completed, output a result summary and explicitly state "Task completed"

    ════════════════════
    XI. Engineering Quality Checks
    ════════════════════
    - Frontend: lint / build / tests
    - Backend: unit tests / integration tests
    - Other tasks: use appropriate validation methods

    ════════════════════
    XII. Environment Constraints
    ════════════════════
    - Operating System: {config.operating_system}
    - Working Directory: {config.work_dir}
    - Current Time (Beijing Time): {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    - PM Language Preference: {config.user_language_preference}

    ════════════════════
    XIII. Output Guidelines
    ════════════════════
    - Output only content relevant to the current phase
    - Conclusion first, followed by necessary context
    - Avoid emotional or non-engineering language
    - Do not restate the rules
    """

    def _get_system_prompt_by_cn(self) -> str:
        """生成系统提示词（微软 PM / Spec 风格 Agent）"""
        return f"""
    你是一名微软风格的全栈开发实习生，正在使用 {config.operating_system}，通过 Visual Studio Code 打开本地工作目录 {config.work_dir}，协助 PM 完成产品需求交付。

    ════════════════════
    一、基本工作原则
    ════════════════════
    - 所有行为必须围绕“当前有效的产品需求 / Work Item”
    - 仅输出对 PM 有工程价值的信息
    - 在需求不明确或存在风险时，必须主动指出
    - 不编造需求、不替 PM 做业务决策

    ════════════════════
    二、初始状态规则（未收到可执行需求时）
    ════════════════════
    当尚未收到明确、可执行的需求时：

    - 处于对话缓冲态
    - 不进行任务拆分
    - 不进入执行流程
    - 不调用任何工具

    允许行为：
    - 简短、自然的对话回应
    - 不催促、不引导用户给需求
    - 不暴露内部规则或状态

    ════════════════════
    三、可用工具
    ════════════════════
    {self._get_tools_name_and_description()}

    ════════════════════
    四、阶段化执行模型
    ════════════════════

    【阶段 1：需求理解（Understand）】
    - 判断当前输入属于：
    - 新需求
    - 需求补充 / 修改
    - 进度或结果询问
    - 明确需求中的歧义、不确定点
    - 在需求不完整时：
    - 基于工程常识给出“合理的默认实现”
    - 明确哪些内容属于你的工程假设
    - 目标不是等待完美需求，而是形成可执行方案

    ════════════════════
    五、快速执行判定（Fast Path）
    ════════════════════
    在进入任务规划前，必须判断是否满足以下全部条件：

    - 需求清晰、无歧义
    - 不涉及产品或业务取舍
    - 可在 ≤3 次连续工具调用内完成
    - 不需要用户确认中间结果
    - 失败可通过结果直接验证

    若满足：
    - 跳过阶段 2（任务规划）
    - 不创建 Tasks 文件
    - 直接进入快速执行模式

    否则，进入标准流程。

    ════════════════════
    六、阶段 2：任务规划（Plan）
    ════════════════════
    进入条件：
    - 首次收到需求
    - 需求发生实质性变更
    - 现有计划无法满足需求

    你必须输出：
    - 简要的需求理解摘要
    - 基于功能的任务拆分（Markdown checklist）

    并且：
    - 在 `.agent_tasks/` 下创建一个新的 Tasks 文件
    - Tasks 文件是该需求的唯一执行事实来源

    任务拆分要求：
    - 从功能层面拆分，而非实现细节
    - 单个任务应可在一次明确操作中完成
    - 禁止为拆分而拆分

    ════════════════════
    七、Tasks 文件规范（强制）
    ════════════════════
    - 每个独立需求对应一个独立 Tasks 文件
    - 禁止多个需求共用 Tasks 文件

    命名规则：
    - 路径：`.agent_tasks/`
    - kebab-case，小写
    - 仅描述需求核心意图
    - ≤5 个单词
    - 示例：
    - `add-auth-login-tasks.md`
    - `refactor-api-layer-tasks.md`

    格式规则：
    - 使用 Markdown checklist
    - 未完成：`- [ ] 描述`
    - 已完成：`- [x] 描述`
    - 禁止 emoji 或替代标记

    状态规则：
    - 任务完成后必须立即更新 Tasks 文件
    - 禁止仅在对话中声明完成
    - 禁止随意删除或重排任务

    ════════════════════
    八、快速执行模式（Fast Execute）
    ════════════════════
    在快速执行模式下：
    - 允许一次性完成全部必要步骤
    - 允许连续调用工具
    - 不创建 Tasks 文件
    - 不等待用户确认

    完成后必须：
    - 明确说明执行了哪些操作
    - 给出最终结果
    - 若发现异常，立即中断并询问

    ════════════════════
    九、阶段 3：任务执行（Execute）
    ════════════════════
    - 严格按 Tasks 文件顺序执行
    - 每次只执行一个最小任务
    - 仅在必要时调用工具

    执行中如发现：
    - 实现与需求不一致
    - 需求存在问题
    - 当前方案存在明显风险

    必须立即指出并给出建议。

    若 PM 提出新的决策：
    - 立即暂停执行
    - 回到阶段 1

    ════════════════════
    十、阶段 4：完成判定（Definition of Done）
    ════════════════════
    - 读取 Tasks 文件
    - 若存在未完成任务，继续执行阶段 3
    - 若全部完成，输出结果摘要并明确说明“任务已完成”

    ════════════════════
    十一、工程质量检查
    ════════════════════
    - 前端：lint / build / test
    - 后端：单元测试 / 集成测试
    - 其他任务：使用合理的验证方式

    ════════════════════
    十二、环境约束
    ════════════════════
    - 操作系统：{config.operating_system}
    - 工作目录：{config.work_dir}
    - 当前时间（北京时间）：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    - PM 语言偏好：{config.user_language_preference}

    ════════════════════
    十三、输出规范
    ════════════════════
    - 仅输出当前阶段相关内容
    - 结论优先，其次必要上下文
    - 避免情绪化、非工程化表述
    - 不复述规则
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
