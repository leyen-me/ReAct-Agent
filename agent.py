# -*- coding: utf-8 -*-
"""ReAct Agent 主逻辑"""

import json
import logging
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
        # 初始化任务规划器
        available_tool_names = [tool.name for tool in self.tools]
        self.task_planner = TaskPlanner(self.client, available_tool_names)
        self.current_plan: Optional[TaskPlan] = None  # 当前任务计划
        self.enable_planning: bool = config.enable_task_planning  # 是否启用规划功能
        self.chat_count = 0
        self.should_stop = False  # 中断标志

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
        ]
        
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
2. 如果提供了执行计划，请按照计划逐步执行；否则将复杂任务拆解为可执行的步骤
3. 在当前环境约束下完成任务
4. 如果任务失败，分析原因并尝试修正方案
5. 在确认任务完成后才停止

━━━━━━━━━━━━━━
【执行原则】
━━━━━━━━━━━━━━
- 优先执行，而不是解释
- 如果提供了执行计划，请严格按照计划执行
- 先思考整体方案，再逐步执行
- 每一步都以"是否更接近目标"为判断标准
- 不确定时，做最小可行尝试（MVP）
- 不编造不存在的文件、命令或结果
- 完成每个步骤后报告进度

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

    def stop_chat(self) -> None:
        """停止当前对话"""
        self.should_stop = True
    
    def set_planning_enabled(self, enabled: bool) -> None:
        """设置是否启用规划功能"""
        self.enable_planning = enabled
    
    def _should_create_plan(self, task_message: str, plan_status_callback: Optional[Callable[[str], None]] = None) -> Tuple[bool, str]:
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
        if self.current_plan and self.current_plan.get_progress()["completed"] < len(self.current_plan.steps):
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

Respond with only "yes" or "no" followed by a brief reason in parentheses."""

            user_prompt = f"""Analyze the following user request and determine if it requires detailed task planning:

User request: "{message}"

Respond with: "yes (reason)" or "no (reason)"."""

            # 使用流式输出
            stream_response = self.client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,  # Very low temperature for deterministic classification
                max_tokens=50,  # Allow space for brief reason
                stream=True,
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
            needs_planning = any(result_lower.startswith(prefix) for prefix in ["yes", "y"])
            
            # 提取原因（如果有）
            reason = "LLM判断"
            if "(" in result and ")" in result:
                try:
                    reason = result.split("(")[1].split(")")[0].strip()
                except:
                    pass
            
            logger.debug(f"规划判断: '{message}' -> {needs_planning} (原因: {reason}, LLM回答: {result})")
            return needs_planning, reason
            
        except Exception as e:
            logger.warning(f"规划判断失败: {e}，默认不规划")
            if plan_status_callback:
                plan_status_callback(f"⚠️ 判断失败")
            return False, f"判断失败: {str(e)}"
    
    def chat(self, task_message: str, output_callback: Optional[Callable[[str, bool], None]] = None, plan_status_callback: Optional[Callable[[str], None]] = None) -> None:
        """
        处理用户任务

        Args:
            task_message: 用户任务消息
            output_callback: 可选的输出回调函数，接受 (text, end_newline) 参数
                            如果提供，将使用回调而不是 print
            plan_status_callback: 可选的规划状态回调函数，接受 (status_text) 参数
                                 用于更新 header 中的规划状态显示
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
        needs_planning, _reason = self._should_create_plan(task_message, update_plan_status)
        
        if needs_planning:
            update_plan_status("📋 分析任务中...")
            
            try:
                self.current_plan = self.task_planner.create_plan(task_message, update_plan_status)
                
                # 更新规划状态为进度显示
                progress = self.current_plan.get_progress()
                update_plan_status(f"📋 计划完成 ({len(self.current_plan.steps)} 步) | 进度: {progress['completed']}/{progress['total']}")
                
                # 将计划添加到消息中，让模型知道计划
                plan_summary = f"\n执行计划（共 {len(self.current_plan.steps)} 步）：\n"
                for step in self.current_plan.steps:
                    plan_summary += f"{step.step_number}. {step.description}\n"
                task_message = f"{task_message}\n\n{plan_summary}"
                
            except Exception as e:
                logger.error(f"规划失败: {e}")
                update_plan_status(f"⚠️ 规划失败: {str(e)[:30]}")
                self.current_plan = None
        else:
            logger.debug(f"直接执行任务: {task_message}")
            # 清除规划状态
            update_plan_status("")
        
        self.message_manager.add_user_message(task_message)
        while True:
            # 检查是否需要中断（在主循环开始时）
            if self.should_stop:
                logger.info("对话在主循环被用户中断")
                # 添加系统消息说明用户中断了对话
                self.message_manager.messages.append({
                    "role": "system",
                    "content": "[用户在对话开始前中断了任务]"
                })
                output("\n\n[对话已被用户中断]", end_newline=True)
                break
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
                output(error_msg, end_newline=True)
                return  # 优雅退出，不抛出异常

            # 处理流式响应
            content = ""
            last_tool_call_id = None
            tool_call_acc = {}
            usage = None
            
            start_reasoning_content = False
            start_content = False
            start_tool_call = False
            
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
                    self.message_manager.add_assistant_content(content)
                # 添加系统消息说明用户中断了对话
                self.message_manager.messages.append({
                    "role": "system",
                    "content": "[用户在此处中断了对话，未完成的任务已暂停]"
                })
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
                else:
                    logger.warning("\nAPI 响应中未找到 prompt_tokens")
            else:
                logger.warning("\n流式响应中未找到 usage 信息")

            if tool_call_acc:
                # 更新当前步骤状态（如果有计划）
                current_step = None
                if self.current_plan:
                    current_step = self.current_plan.get_current_step()
                    if current_step and current_step.status == StepStatus.PENDING:
                        current_step.mark_started()
                        progress = self.current_plan.get_progress()
                        # 更新 header 中的规划状态
                        update_plan_status(f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%) | 步骤 {current_step.step_number}")
                
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
                    
                    # 更新步骤状态
                    if self.current_plan and current_step:
                        if is_success:
                            # 截断过长的结果
                            result_summary = str(tool_result)[:200] + "..." if len(str(tool_result)) > 200 else str(tool_result)
                            current_step.mark_completed(result_summary)
                            # 更新 header 中的规划状态
                            progress = self.current_plan.get_progress()
                            update_plan_status(f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%)")
                        else:
                            current_step.mark_failed(tool_error or "工具执行失败")
                            # 移动到下一步（即使失败也继续）
                            self.current_plan.move_to_next_step()
                            # 更新 header 中的规划状态
                            progress = self.current_plan.get_progress()
                            update_plan_status(f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%) ⚠️")
                    
                    self.message_manager.add_assistant_tool_call_result(
                        tc_data["id"], result_content
                    )
                
                # 如果当前步骤完成，移动到下一步
                if self.current_plan and current_step and current_step.status == StepStatus.COMPLETED:
                    self.current_plan.move_to_next_step()
                    # 更新 header 中的规划状态
                    progress = self.current_plan.get_progress()
                    update_plan_status(f"📋 执行中: {progress['completed']}/{progress['total']} ({progress['progress_percent']:.0f}%)")
                
                continue
            else:
                # 最终回复阶段
                # logger.info(f"=== Final Answer ===")
                # logger.info(content)
                
                # 如果任务完成，更新计划状态
                if self.current_plan:
                    # 标记所有剩余步骤为完成（如果任务已完成）
                    progress = self.current_plan.get_progress()
                    if progress["pending"] > 0:
                        # 如果还有待执行的步骤，标记为跳过（可能计划过于详细）
                        for step in self.current_plan.steps:
                            if step.status == StepStatus.PENDING:
                                step.mark_skipped("任务已完成，步骤自动跳过")
                    
                    # 显示最终进度
                    final_progress = self.current_plan.get_progress()
                    if final_progress["total"] > 0:
                        # 更新 header 中的规划状态
                        status_text = f"✅ 完成: {final_progress['completed']}/{final_progress['total']} ({final_progress['progress_percent']:.0f}%)"
                        if final_progress["failed"] > 0:
                            status_text += f" ⚠️{final_progress['failed']}"
                        update_plan_status(status_text)
                
                self.message_manager.add_assistant_content(content)
                break
