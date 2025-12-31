# -*- coding: utf-8 -*-
"""ReAct Agent 主逻辑"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any

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

    def _get_system_prompt(self) -> str:
        """生成系统提示词"""
        return f"""
你是专业的任务执行助手，你的任务是解决用户的问题。

⸻

环境信息（请注意）：

- 操作系统：{config.operating_system}
- 工作目录：{config.work_dir}
- 北京时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- 用户语言偏好：{config.user_language_preference}
"""

    def _get_tools(self) -> List[Dict[str, Any]]:
        """获取工具列表"""
        return [{"type": "function", "function": tool.to_dict()} for tool in self.tools]

    def chat(self, task_message: str) -> None:
        """
        处理用户任务

        Args:
            task_message: 用户任务消息
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
                print("\n=== 错误信息 ===")
                print("API 调用失败: 已达到最大重试次数")
                print("=== 错误信息结束 ===\n")
                return  # 优雅退出，不抛出异常

            # 处理流式响应
            content = ""
            last_tool_call_id = None
            tool_call_acc = {}
            usage = None

            print("\n=== 流式输出开始 ===")
            for chunk in stream_response:

                # 获取 usage 信息（通常在最后一个 chunk 中）
                if hasattr(chunk, "usage") and chunk.usage is not None:
                    usage = chunk.usage

                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta

                    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                        print(delta.reasoning_content, end="", flush=True)

                    if hasattr(delta, "content") and delta.content:
                        chunk_content = delta.content
                        content += chunk_content
                        print(chunk_content, end="", flush=True)

                    if hasattr(delta, "tool_calls") and delta.tool_calls:
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
                                if tc.function.arguments:
                                    tool_call_acc[tc_id][
                                        "arguments"
                                    ] += tc.function.arguments

            print("\n=== 流式输出结束 ===\n")

            # 更新 token 使用量（从 API 响应获取）
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                if prompt_tokens is not None:
                    self.message_manager.update_token_usage(prompt_tokens)
                    completion_tokens = getattr(usage, "completion_tokens", 0)
                    total_tokens = getattr(usage, "total_tokens", 0)
                    logger.debug(
                        f"Token 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}"
                    )
                else:
                    logger.warning("API 响应中未找到 prompt_tokens")
            else:
                logger.warning("流式响应中未找到 usage 信息")

            if tool_call_acc:
                for tc_id, tc_data in tool_call_acc.items():
                    logger.info(f"执行工具 {tc_data['name']}，参数: {tc_data['arguments']}")
                    self.message_manager.add_assistant_tool_call(
                        tc_id, tc_data["name"], tc_data["arguments"]
                    )
                    tool_call_result = self.tool_executor.execute(
                        tc_data["name"], tc_data["arguments"]
                    )
                    logger.info(f"工具调用结果: {tool_call_result}")
                    self.message_manager.add_assistant_tool_call_result(
                        tc_data["id"], tool_call_result
                    )
                continue
            else:
                logger.info(f"=== Final Answer ===\n{content}\n")
                self.message_manager.add_assistant_content(content)
                break
