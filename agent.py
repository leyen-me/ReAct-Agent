# -*- coding: utf-8 -*-
"""ReAct Agent 主逻辑"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable

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
    RunCommandTool,
    SearchInFilesTool,
    FindFilesTool,
    GitStatusTool,
    GitDiffTool,
    GitCommitTool,
    GitBranchTool,
    GitLogTool,
    AddTodoTool,
    ListTodosTool,
    UpdateTodoStatusTool,
    DeleteTodoTool,
    GetTodoStatsTool,
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

    def update_token_usage(self, prompt_tokens: int) -> None:
        """
        更新 token 使用量（从 API 响应获取）

        Args:
            prompt_tokens: API 返回的 prompt_tokens
        """
        self.current_tokens = prompt_tokens
        self._manage_context()

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
        self.chat_count = 0

    def _create_tools(self) -> List[Tool]:
        """创建工具列表"""
        return [
            ReadFileTool(config.work_dir),
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
            AddTodoTool(config.work_dir),
            ListTodosTool(config.work_dir),
            UpdateTodoStatusTool(config.work_dir),
            DeleteTodoTool(config.work_dir),
            GetTodoStatsTool(config.work_dir),
        ]
        
    def _get_system_prompt_by_en(self) -> str:
        """Generate system prompt"""
        return f"""
You are a professional task-execution AI Agent.

━━━━━━━━━━━━━━
【Core Responsibilities】
━━━━━━━━━━━━━━
1. Accurately understand the user's true goal, not just the surface-level question
2. Decompose complex tasks into executable steps
3. Complete tasks within the constraints of the current environment
4. If a task fails, analyze the cause and attempt corrective solutions
5. Stop only after confirming the task is completed

━━━━━━━━━━━━━━
【Execution Principles】
━━━━━━━━━━━━━━
- Prioritize execution over explanation
- Think through the overall plan first, then execute step by step
- Evaluate each step by whether it moves closer to the goal
- When uncertain, attempt the Minimum Viable Action (MVP)
- Do not fabricate non-existent files, commands, or results

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
        """生成系统提示词"""
        return f"""
你是一个专业的任务执行型 AI Agent。

━━━━━━━━━━━━━━
【核心职责】
━━━━━━━━━━━━━━
1. 准确理解用户的目标，而不仅是表面问题
2. 将复杂任务拆解为可执行的步骤
3. 在当前环境约束下完成任务
4. 如果任务失败，分析原因并尝试修正方案
5. 在确认任务完成后才停止

━━━━━━━━━━━━━━
【执行原则】
━━━━━━━━━━━━━━
- 优先执行，而不是解释
- 先思考整体方案，再逐步执行
- 每一步都以“是否更接近目标”为判断标准
- 不确定时，做最小可行尝试（MVP）
- 不编造不存在的文件、命令或结果

━━━━━━━━━━━━━━
【环境信息】
━━━━━━━━━━━━━━
操作系统：{config.operating_system}
工作目录：{config.work_dir}
当前时间（北京时间）：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
用户语言偏好：{config.user_language_preference}

你必须基于以上真实环境进行推理与行动。

━━━━━━━━━━━━━━
【输出要求】
━━━━━━━━━━━━━━
- 只输出对用户有价值的内容
- 任务完成后，明确说明“任务已完成”
- 如无法完成，明确说明原因与下一步建议

━━━━━━━━━━━━━━
【禁止事项】
━━━━━━━━━━━━━━
- 不要假设环境中存在未说明的工具或文件
- 不要在未验证前声称任务已完成
- 不要输出无关的解释性废话
"""

    def _get_system_prompt(self) -> str:
        """生成系统提示词"""
        return self._get_system_prompt_by_en()

    def _get_tools(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        return [{"type": "function", "function": tool.to_dict()} for tool in self.tools]

    def chat(self, task_message: str, output_callback: Optional[Callable[[str, bool], None]] = None) -> None:
        """
        处理用户任务

        Args:
            task_message: 用户任务消息
            output_callback: 可选的输出回调函数，接受 (text, end_newline) 参数
                            如果提供，将使用回调而不是 print
        """
        self.message_manager.add_user_message(task_message)
        while True:
            self.chat_count += 1

            logger.debug(f"=== Chat Round {self.chat_count} ===")
            logger.debug(
                f"Messages: {json.dumps(self.message_manager.get_messages(), indent=2, ensure_ascii=False)}"
            )

            # 调用 API（带重试机制）
            max_retries = 3
            retry_count = 0

            while retry_count < max_retries:
                try:
                    stream_response: Stream[ChatCompletionChunk] = (
                        self.client.chat.completions.create(
                            model=config.model,
                            messages=self.message_manager.get_messages(),
                            stream=True,
                            temperature=1,
                            top_p=1,
                            max_tokens=4096,
                            tools=self._get_tools(),
                            tool_choice="auto",
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
                if output_callback:
                    output_callback(error_msg, end_newline=True)
                else:
                    print(error_msg)
                return  # 优雅退出，不抛出异常

            # 处理流式响应
            content = ""
            last_tool_call_id = None
            tool_call_acc = {}
            usage = None
            
            start_reasoning_content = False
            start_content = False
            start_tool_call = False
            
            # 定义输出函数
            def output(text: str, end_newline: bool = True):
                if output_callback:
                    output_callback(text, end_newline)
                else:
                    print(text, end="\n" if end_newline else "", flush=True)

            for chunk in stream_response:
                
                # 获取 usage 信息（通常在最后一个 chunk 中）
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    usage = chunk.usage

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta

                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        if not start_reasoning_content:
                            output(f"\n{'='*config.log_separator_length} 模型思考 {'='*config.log_separator_length}\n")
                            start_reasoning_content = True
                        output(delta.reasoning_content, end_newline=False)

                    if hasattr(delta, "content") and delta.content:
                        if not start_content:
                            output(f"\n{'='*config.log_separator_length} 最终回复 {'='*config.log_separator_length}\n")
                            start_content = True
                        chunk_content = delta.content
                        content += chunk_content
                        output(chunk_content, end_newline=False)

                    if hasattr(delta, "tool_calls") and delta.tool_calls:
                        if not start_tool_call:
                            output(f"\n{'='*config.log_separator_length} 工具调用 {'='*config.log_separator_length}\n")
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
                else:
                    logger.warning("\nAPI 响应中未找到 prompt_tokens")
            else:
                logger.warning("\n流式响应中未找到 usage 信息")

            if tool_call_acc:
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
                        result_content = json.dumps(tool_call_result, ensure_ascii=False, indent=2)
                    else:
                        # 兼容旧的返回格式
                        result_content = tool_call_result
                    
                    self.message_manager.add_assistant_tool_call_result(
                        tc_data["id"], result_content
                    )
                continue
            else:
                # logger.info(f"=== Final Answer ===")
                # logger.info(content)
                self.message_manager.add_assistant_content(content)
                break
