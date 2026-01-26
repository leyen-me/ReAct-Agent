# -*- coding: utf-8 -*-
"""ReAct Agent 主逻辑"""

import json
import logging
import re
from typing import List, Dict, Any, Optional, Callable, Tuple

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk

from config import config
from prompts import get_system_prompt_by_cn, get_system_prompt_by_en
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
    EditFileByLineTool,
    EditFileByPositionTool,
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
    SummarizeContextTool,
)
from tool_executor import create_tool_executor

logger = logging.getLogger(__name__)


class MessageManager:
    """消息管理器（支持多段上下文）"""

    def __init__(self, system_prompt: str, max_context_tokens: int):
        """
        初始化消息管理器

        Args:
            system_prompt: 系统提示词
            max_context_tokens: 最大上下文 token 数
        """
        self.max_context_tokens = max_context_tokens
        # 每个段最多使用 80% 的上下文
        self.segment_max_tokens = int(max_context_tokens * 0.8)
        # 系统提示词模板（不包含上下文信息）
        self.base_system_prompt = system_prompt
        # 消息段列表：每个段是一个消息列表
        # segments = [messages1, messages2, messages3, ...]
        # 每个段最多使用 80% 的上下文
        self.segments: List[List[Dict[str, str]]] = []
        # 当前段的索引
        self.current_segment_index: int = -1
        # 当前段的消息列表
        self.messages: List[Dict[str, str]] = []
        # 当前实际使用的 token 数（从 API 响应获取）
        self.current_tokens: int = 0
        # 估算的 token 数（用于实时显示，在流式过程中更新）
        self.estimated_tokens: int = 0
        # 上下文总结（用于新段）
        self.context_summaries: List[str] = []
        # 初始化第一个段
        self._create_new_segment()

    def _create_new_segment(self) -> None:
        """创建新的消息段"""
        # 创建新段，包含系统提示词（此时 current_tokens 为 0，所以使用率会是 0%）
        new_segment = [
            {"role": "system", "content": self._get_system_prompt_with_context()}
        ]
        self.segments.append(new_segment)
        self.current_segment_index = len(self.segments) - 1
        self.messages = self.segments[self.current_segment_index]
        # 重置 token 计数（新段开始时为 0）
        self.current_tokens = 0
        self.estimated_tokens = 0
        
        # 添加上下文使用情况的系统消息（新段开始时为 0%）
        self._update_context_usage_message()
        
        logger.info(
            f"创建新消息段 - 段索引: {self.current_segment_index}, "
            f"总段数: {len(self.segments)}, "
            f"历史总结数: {len(self.context_summaries)}"
        )

    def _get_system_prompt_with_context(self) -> str:
        """
        获取系统提示词（包含历史总结，但不包含上下文使用情况）

        Returns:
            系统提示词
        """
        # 如果有历史总结，添加到系统提示词中
        if self.context_summaries:
            context_info = "\n━━━━━━━━━━━━━━\n【历史上下文总结】\n━━━━━━━━━━━━━━\n"
            for i, summary in enumerate(self.context_summaries, 1):
                context_info += f"\n段 {i} 总结：\n{summary}\n"
            # 重要：如果有历史总结，说明有未完成的任务，应该自动继续执行
            context_info += "\n重要提示：\n"
            context_info += "- 如果历史总结中包含未完成的任务或下一步计划，你必须自动继续执行，不要等待用户输入\n"
            context_info += "- 新段创建后，你应该立即根据历史总结中的\"下一步计划\"继续执行任务\n"
            context_info += "- 只有在所有任务都完成后，或者遇到需要用户决策的问题时，才应该询问用户\n"
            return self.base_system_prompt + context_info
        
        return self.base_system_prompt
    
    def _get_context_usage_message(self) -> str:
        """
        生成极简化的上下文使用情况系统消息（极限压缩 token）

        Returns:
            极简化的上下文使用情况消息
        """
        usage_percent = self.get_token_usage_percent()
        current_tokens = self.current_tokens
        remaining_tokens = self.get_remaining_tokens()
        
        # 极简化格式：只保留核心数字信息
        # 格式：上下文: {已用}/{最大} ({使用率}%) 剩余:{剩余} 段:{段数}
        message = f"上下文: {current_tokens}/{self.segment_max_tokens} ({usage_percent:.1f}%) 剩余:{remaining_tokens} 段:{len(self.segments)}"
        
        return message

    def _update_context_usage_message(self) -> None:
        """
        更新或添加上下文使用情况的系统消息（极简化格式）
        如果最后一条系统消息是上下文使用情况消息，则更新它；否则添加新的
        """
        context_message = self._get_context_usage_message()
        
        # 检查最后一条消息是否是上下文使用情况消息（极简化格式：以"上下文:"开头）
        if self.messages and self.messages[-1].get("role") == "system":
            last_content = self.messages[-1].get("content", "")
            # 检测极简化格式：以"上下文:"或"Context:"开头
            if last_content.startswith("上下文:") or last_content.startswith("Context:"):
                # 更新最后一条消息
                self.messages[-1]["content"] = context_message
                logger.debug("已更新上下文使用情况系统消息")
                return
        
        # 如果没有找到，添加新的系统消息
        self.add_system_message(context_message)
        logger.debug("已添加上下文使用情况系统消息")

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

        # 在每轮对话后更新或添加上下文使用情况的系统消息
        # 这样模型能及时看到最新的使用情况
        self._update_context_usage_message()
        
        # 检查是否需要创建新段（使用率达到 80%）
        if self.get_token_usage_percent() >= 80.0:
            logger.warning(
                f"当前段使用率已达到 {self.get_token_usage_percent():.2f}%，"
                f"需要总结并创建新段"
            )
            # 注意：这里不立即创建新段，而是让模型主动总结
            # 模型会在回复中总结，然后我们检测到总结后创建新段

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
        """
        管理上下文，当超过段限制时删除旧消息（保留系统消息）
        注意：现在使用分段管理，不再需要删除旧消息
        """
        # 如果当前段超过限制，删除旧消息（保留系统消息）
        removed_count = 0
        while (
            self.current_tokens > self.segment_max_tokens
            and len(self.messages) > 1
        ):
            # 保留系统消息，删除第一个非系统消息
            removed_message = self.messages.pop(1)
            removed_count += 1
            logger.debug(
                f"当前段已满，删除旧消息 - "
                f"当前使用: {self.current_tokens}/{self.segment_max_tokens}, "
                f"消息角色: {removed_message.get('role', 'unknown')}"
            )

        if removed_count > 0:
            logger.info(
                f"上下文管理完成 - 删除了 {removed_count} 条旧消息, "
                f"剩余消息数: {len(self.messages)}"
            )

    def add_system_message(self, content: str) -> None:
        """添加系统消息"""
        self.messages.append({"role": "system", "content": f"{content}"})
        logger.debug(f"已添加系统消息 - 长度: {len(content)}")

    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": f"{content}"})
        logger.debug(f"已添加用户消息 - 长度: {len(content)}")

    def add_assistant_content(self, content: str) -> None:
        """添加助手内容"""
        self.messages.append({"role": "assistant", "content": f"{content}"})
        logger.debug(f"已添加助手回复 - 长度: {len(content)}")
    
    def add_assistant_reasoning(self, content: str) -> None:
        """添加助手思考内容（不会加载到上下文，但会保留在记录中）"""
        self.messages.append({
            "role": "assistant", 
            "content": f"{content}",
            "_is_reasoning": True  # 内部标记，表示这是思考内容
        })
        logger.debug(f"已添加助手思考内容 - 长度: {len(content)}")

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
            
            # 移除内部标记字段（如 _is_reasoning），这些字段不应该发送给 API
            if "_is_reasoning" in cleaned_msg:
                del cleaned_msg["_is_reasoning"]
            
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
        """
        获取当前段的消息（已验证和清理）
        注意：只返回当前段的消息，不包含历史段
        思考内容会被过滤掉，不会加载到上下文
        """
        # 更新系统提示词以包含最新的上下文信息
        if self.messages and self.messages[0].get("role") == "system":
            self.messages[0]["content"] = self._get_system_prompt_with_context()
        
        # 过滤掉思考内容（标记为 _is_reasoning 的消息）
        messages = [
            msg for msg in self.messages.copy() 
            if not msg.get("_is_reasoning", False)
        ]
        return self._validate_and_clean_messages(messages)
    
    def get_all_segments(self) -> List[List[Dict[str, str]]]:
        """
        获取所有段的消息（用于调试或导出）

        Returns:
            所有段的消息列表
        """
        return self.segments.copy()
    
    def get_all_messages(self) -> List[Dict[str, str]]:
        """
        获取所有段的消息合并为一个列表（用于导出和保存历史记录）
        
        注意：这个方法会合并所有段的消息，包括历史总结信息。
        每个段之间会插入一个标记消息，表示段的分隔。

        Returns:
            所有消息的合并列表
        """
        all_messages = []
        for i, segment in enumerate(self.segments):
            # 添加段分隔标记（除了第一段）
            if i > 0:
                all_messages.append({
                    "role": "system",
                    "content": f"[段 {i + 1} 开始 - 上下文已总结并创建新段]"
                })
            # 添加该段的所有消息
            all_messages.extend(segment.copy())
        return all_messages
    
    def load_messages(self, messages: List[Dict[str, str]]) -> None:
        """
        从消息列表加载并恢复多段结构（用于加载历史记录）
        
        这个方法会尝试识别段分隔标记，将消息恢复到多个段中。
        如果没有段分隔标记，则将所有消息放入第一个段。

        Args:
            messages: 消息列表
        """
        # 清空现有段
        self.segments = []
        self.context_summaries = []
        
        # 查找段分隔标记
        segment_boundaries = []
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                content = msg.get("content", "")
                if "[段" in content and "开始" in content:
                    segment_boundaries.append(i)
        
        # 如果没有段分隔标记，将所有消息放入第一个段
        if not segment_boundaries:
            # 创建第一个段
            new_segment = []
            for msg in messages:
                # 跳过系统消息中的上下文使用情况（会在创建新段时自动添加）
                if msg.get("role") == "system":
                    content = msg.get("content", "")
                    # 如果包含基础系统提示词，保留；否则跳过（可能是上下文信息）
                    if "Microsoft" in content or "微软" in content:
                        # 提取基础系统提示词（去除上下文信息部分）
                        base_content = content.split("━━━━━━━━━━━━━━")[0].strip()
                        if base_content:
                            new_segment.append({"role": "system", "content": base_content})
                else:
                    new_segment.append(msg.copy())
            
            if new_segment:
                self.segments.append(new_segment)
                self.current_segment_index = 0
                self.messages = self.segments[0]
        else:
            # 根据段分隔标记分割消息
            start_idx = 0
            for boundary in segment_boundaries:
                # 添加当前段的消息（不包括分隔标记）
                segment_messages = messages[start_idx:boundary]
                if segment_messages:
                    # 处理第一个段：需要包含系统提示词
                    if len(self.segments) == 0:
                        # 查找系统消息
                        system_msg = None
                        other_messages = []
                        for msg in segment_messages:
                            if msg.get("role") == "system":
                                content = msg.get("content", "")
                                if "Microsoft" in content or "微软" in content:
                                    system_msg = msg
                            else:
                                other_messages.append(msg)
                        
                        if system_msg:
                            new_segment = [system_msg] + other_messages
                        else:
                            new_segment = segment_messages
                    else:
                        new_segment = segment_messages
                    
                    self.segments.append(new_segment)
                
                start_idx = boundary + 1  # 跳过分隔标记
            
            # 添加最后一段
            if start_idx < len(messages):
                last_segment = messages[start_idx:]
                if last_segment:
                    self.segments.append(last_segment)
            
            # 设置当前段为最后一段
            if self.segments:
                self.current_segment_index = len(self.segments) - 1
                self.messages = self.segments[self.current_segment_index]
        
        # 重置 token 计数（加载历史记录时无法准确知道 token 使用情况）
        self.current_tokens = 0
        self.estimated_tokens = 0
        
        logger.info(
            f"已加载消息历史 - 总段数: {len(self.segments)}, "
            f"当前段索引: {self.current_segment_index}"
        )

    def get_token_usage_percent(self) -> float:
        """
        获取当前段 token 使用百分比

        Returns:
            使用百分比（0-100）
        """
        if self.segment_max_tokens == 0:
            return 0.0
        return (self.current_tokens / self.segment_max_tokens) * 100

    def get_remaining_tokens(self) -> int:
        """
        获取当前段剩余可用 token 数

        Returns:
            剩余 token 数
        """
        return max(0, self.segment_max_tokens - self.current_tokens)
    
    def should_create_new_segment(self) -> bool:
        """
        判断是否应该创建新段

        Returns:
            如果使用率达到 80% 或以上，返回 True
        """
        return self.get_token_usage_percent() >= 80.0
    
    def create_new_segment_with_summary(self, summary: str) -> None:
        """
        使用总结创建新段

        Args:
            summary: 当前段的总结内容
        """
        if summary:
            self.context_summaries.append(summary)
            logger.info(f"已保存段 {self.current_segment_index + 1} 的总结")
        
        # 创建新段
        self._create_new_segment()
        logger.info(
            f"已创建新段 - 当前段索引: {self.current_segment_index}, "
            f"历史总结数: {len(self.context_summaries)}"
        )


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
        self.chat_count = 0
        self.should_stop = False  # 中断标志（需要在创建工具执行器之前初始化）
        self.tools = self._create_tools()
        # 传递 should_stop 检查函数给工具执行器
        # 使用 lambda 确保每次调用时都获取最新的 should_stop 值
        self.tool_executor = create_tool_executor(self.tools, lambda: self.should_stop)
        logger.debug(f"工具执行器已创建，should_stop 检查函数: {self.tool_executor.should_stop_check is not None}")
        self.message_manager = MessageManager(
            self._get_system_prompt(), config.max_context_tokens
        )

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
            EditFileByLineTool(config.work_dir),
            EditFileByPositionTool(config.work_dir),
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
            # 总结上下文工具，需要回调函数来创建新段
            SummarizeContextTool(
                config.work_dir,
                on_summarize_callback=self._handle_context_summary
            ),
        ]
        logger.debug(f"工具列表创建完成 - 工具数量: {len(tools)}")
        logger.debug(f"工具名称: {[tool.name for tool in tools]}")
        return tools
    
    def _handle_context_summary(self, summary: str) -> None:
        """
        处理上下文总结回调
        
        Args:
            summary: 总结内容
        """
        logger.info(f"收到上下文总结，长度: {len(summary)}")
        # 创建新段
        self.message_manager.create_new_segment_with_summary(summary)
        logger.info("已创建新对话段")
        
        # 在新段中添加一条系统消息，指示模型继续执行任务
        # 这样模型就知道应该继续执行，而不是等待用户输入
        continue_message = (
            "上下文已总结并创建新段。请根据历史总结中的\"下一步计划\"自动继续执行任务，"
            "不要等待用户输入。只有在所有任务都完成后，或遇到需要用户决策的问题时，才应该询问用户。"
        )
        self.message_manager.messages.append(
            {"role": "system", "content": continue_message}
        )
        logger.info("已添加继续执行提示消息")

    def _get_system_prompt(self) -> str:
        """生成系统提示词"""
        tools_name_and_description = self._get_tools_name_and_description()
        return get_system_prompt_by_cn(config, tools_name_and_description)

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
        logger.info("收到停止对话请求，设置 should_stop = True")
        self.should_stop = True
        logger.debug(f"should_stop 已设置为: {self.should_stop}")

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
                        temperature=0.3,
                        top_p=1,
                        frequency_penalty=0,
                        presence_penalty=0,
                        tools=tools,
                        max_tokens=4096,
                        tool_choice="auto",
                        stream_options={"include_usage": True, "continuous_usage_stats": True},
                        extra_body={"reasoning_effort": "high"}
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

        usage_percent = self.message_manager.get_token_usage_percent()
        logger.info(
            f"Token 使用量更新 - "
            f"prompt: {prompt_tokens}, "
            f"completion: {completion_tokens}, "
            f"total: {total_tokens}, "
            f"使用率: {usage_percent:.2f}%"
        )

        # 如果使用率达到 80%，记录警告（模型应该主动总结）
        if usage_percent >= 80.0:
            logger.warning(
                f"当前段使用率已达到 {usage_percent:.2f}%，"
                f"模型应该在下次回复中主动总结上下文"
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
            # 检查是否应该停止（在执行每个工具之前）
            if self.should_stop:
                logger.info("工具执行被用户中断，停止执行剩余工具")
                return
            
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
                
                # 执行后再次检查是否应该停止（不执行后续工具）
                if self.should_stop:
                    logger.info("工具执行后被用户中断，停止执行剩余工具")
                    return

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
                        # 如果是总结上下文工具，输出提示信息
                        if tool_name == "summarize_context":
                            logger.info("上下文总结工具执行成功，已创建新对话段")
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
                self.message_manager.add_assistant_reasoning(reasoning_content)
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
            self.message_manager.add_assistant_reasoning(reasoning_content)
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
        if reasoning_content.strip():
            self.message_manager.add_assistant_reasoning(reasoning_content)
        if content.strip():
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
