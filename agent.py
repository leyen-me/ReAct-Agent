# -*- coding: utf-8 -*-
"""ReAct Agent 主逻辑"""

import re
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk

from config import config
from tools import (
    Tool,
    ReadFileTool, WriteFileTool, DeleteFileTool, CreateFileTool,
    RenameFileTool, ListFilesTool, EditFileTool, CreateFolderTool,
    DeleteFolderTool, MoveFileTool, CopyFileTool, RunCommandTool,
    SearchInFilesTool, FindFilesTool,
    GitStatusTool, GitDiffTool, GitCommitTool, GitBranchTool, GitLogTool,
    FormatCodeTool, RefactorTool, ExtractFunctionTool, RenameSymbolTool,
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
            
            if config.debug_mode:
                logger.debug(f"上下文已满，删除旧消息，当前使用: {self.current_tokens}/{self.max_context_tokens}")
            
            # 注意：删除消息后，下次 API 调用时会重新计算 token 数
            # 这里我们暂时保持 current_tokens 不变，等待下次 API 响应更新
    
    def add_user_message(self, content: str) -> None:
        """添加用户消息"""
        self.messages.append({"role": "user", "content": f"<question>{content}</question>"})
    
    def add_assistant_action(self, action: str) -> None:
        """添加助手 action"""
        self.messages.append({"role": "assistant", "content": f"<action>{action}</action>"})
    
    def add_observation(self, observation: str) -> None:
        """添加观察结果"""
        self.messages.append({"role": "user", "content": f"<observation>{observation}</observation>"})
    
    def add_final_answer(self, answer: str) -> None:
        """添加最终答案"""
        self.messages.append({"role": "assistant", "content": f"<final_answer>{answer}</final_answer>"})
    
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
            self._get_system_prompt(),
            config.max_context_tokens
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
            FormatCodeTool(config.work_dir),
            RefactorTool(config.work_dir),
            ExtractFunctionTool(config.work_dir),
            RenameSymbolTool(config.work_dir),
        ]
    
    def _get_system_prompt(self) -> str:
        """生成系统提示词"""
        tools_dict = [tool.to_dict() for tool in self.tools]
        
        return f"""
你是专业的任务执行助手，你的任务是解决用户的问题。现在是北京时间 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}。

你需要解决一个问题。为此，你需要将问题分解为多个步骤。对于每个步骤，首先使用 <thought> 思考要做什么，然后使用可用工具之一决定一个 <action>。接着，你将根据你的行动从环境/工具中收到一个 <observation>。持续这个思考和行动的过程，直到你有足够的信息来提供 <final_answer>。

在提供最终答案后，对于复杂的任务（涉及文件操作、多步骤执行等），你需要进行反思、检查、和总结。在反思、检查、和总结时，请使用 <reflection> 标签，对于简单的问候或闲聊任务，不需要反思、检查和总结。

所有步骤请严格使用以下 XML 标签格式输出：
- <question> 用户问题
- <thought> 思考
- <action> 采取的工具操作
- <observation> 工具或环境返回的结果
- <final_answer> 最终答案
- <reflection> 任务反思

⸻

例子 1（简单任务，不需要反思和总结）:

<question>你好</question>
<thought>这是一个简单的问候，不需要使用工具，直接回复即可。</thought>
<final_answer>你好！有什么可以帮助你的吗？</final_answer>

⸻

例子 2（复杂任务，需要反思和总结）:

<question>将 script.js 中的函数名 hello 改为 greet</question>
<thought>需要先读取文件查看内容，然后使用 EditFileTool 替换函数名。</thought>
<action>EditFileTool().run({{'path': '{config.work_dir}/script.js', 'old_string': 'function hello()', 'new_string': 'function greet()'}})</action>
<observation>文件{config.work_dir}/script.js编辑成功，已替换 1 处匹配的文本</observation>
<final_answer>已成功将函数名从 hello 改为 greet。</final_answer>
<reflection>先读取文件确认内容，再使用 EditFileTool 进行部分替换，避免了全文重写。</reflection>

⸻

请严格遵守：
- 你每次回答都必须包括两个标签，第一个是 <thought>，第二个是 <action> 或 <final_answer>
- 输出 <action> 后立即停止生成，等待真实的 <observation>，擅自生成 <observation> 将导致错误
- 对于复杂任务，在 <final_answer> 后需要添加 <reflection> 标签
- 对于简单问候或闲聊任务，不需要反思和检查

⸻

action 规范：

- 使用文件类型工具时，path 参数必须使用绝对路径
- 使用文件类型工具时，path 的路径必须在当前工作目录下
- **重要**：编辑现有文件时，优先使用 EditFileTool 进行部分替换，而不是 WriteFileTool 全文替换
- EditFileTool 可以只替换文件中的特定部分，保留其他内容不变，类似于 Cursor 的部分替换功能
- 使用 EditFileTool 时，old_string 必须与文件中的内容完全匹配（包括空格、换行、缩进等）
- 以下是一些好的例子：

<action>WriteFileTool().run({{'path': '{config.work_dir}/test.txt', 'content': 'xxx\\nxxx'}})</action>

<action>EditFileTool().run({{'path': '{config.work_dir}/test.py', 'old_string': 'def hello():\\n    print(\\\"old\\\")', 'new_string': 'def hello():\\n    print(\\\"new\\\")'}})</action>

⸻

本次任务可用工具：
{json.dumps(tools_dict, indent=4, ensure_ascii=False)}

⸻

环境信息：

操作系统：{config.operating_system}
工作目录：{config.work_dir}
"""
    
    def _parse_content(self, content: str) -> Dict[str, Optional[str]]:
        """
        解析模型返回的内容
        
        Returns:
            包含 thought, action, final_answer, reflection 的字典
        """
        result = {
            "thought": None,
            "action": None,
            "final_answer": None,
            "reflection": None,
        }
        
        # 解析 thought
        if "<thought>" in content:
            match = re.search(r"<thought>(.*?)</thought>", content, re.DOTALL)
            if match:
                result["thought"] = match.group(1).strip()
        
        # 解析 action
        if "<action>" in content:
            match = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
            if match:
                result["action"] = match.group(1).strip()
        
        # 解析 final_answer
        if "<final_answer>" in content:
            match = re.search(r"<final_answer>(.*?)</final_answer>", content, re.DOTALL)
            if match:
                result["final_answer"] = match.group(1).strip()
        
        # 解析 reflection
        if "<reflection>" in content:
            match = re.search(r"<reflection>(.*?)</reflection>", content, re.DOTALL)
            if match:
                result["reflection"] = match.group(1).strip()
        
        # 容错处理：如果有 reflection 但没有 final_answer，尝试提取 reflection 之前的内容作为 final_answer
        if result["reflection"] and not result["final_answer"]:
            # 找到 reflection 标签之前的内容
            reflection_match = re.search(r"<reflection>", content, re.DOTALL)
            if reflection_match:
                before_reflection = content[:reflection_match.start()].strip()
                # 移除可能存在的 thought 和 action 标签内容
                before_reflection = re.sub(r"<thought>.*?</thought>", "", before_reflection, flags=re.DOTALL).strip()
                before_reflection = re.sub(r"<action>.*?</action>", "", before_reflection, flags=re.DOTALL).strip()
                if before_reflection:
                    result["final_answer"] = before_reflection
        
        # 容错处理：如果没有任何标签，但内容看起来像最终回答（没有 action），尝试识别
        if not result["action"] and not result["final_answer"] and not result["reflection"]:
            # 如果内容不包含任何 XML 标签，且不是空的，可能是直接的回答
            if content.strip() and not re.search(r"<[^>]+>", content):
                result["final_answer"] = content.strip()
        
        return result
    
    def chat(self, task_message: str) -> None:
        """
        处理用户任务
        
        Args:
            task_message: 用户任务消息
        """
        self.message_manager.add_user_message(task_message)
        
        while True:
            self.chat_count += 1
            
            if config.debug_mode:
                logger.debug(f"=== Chat Round {self.chat_count} ===")
                logger.debug(f"Messages: {json.dumps(self.message_manager.get_messages(), indent=2, ensure_ascii=False)}")
            
            # 调用 API
            try:
                stream_response: Stream[ChatCompletionChunk] = self.client.chat.completions.create(
                    model=config.model,
                    messages=self.message_manager.get_messages(),
                    stream=True
                )
            except Exception as e:
                logger.error(f"API 调用失败: {e}")
                raise
            
            # 处理流式响应
            content = ""
            usage = None
            print("\n=== 流式输出开始 ===")
            for chunk in stream_response:
                # 获取 usage 信息（通常在最后一个 chunk 中）
                if hasattr(chunk, 'usage') and chunk.usage is not None:
                    usage = chunk.usage
                
                if chunk.choices and len(chunk.choices) > 0:
                    if hasattr(chunk.choices[0].delta, 'reasoning_content') and chunk.choices[0].delta.reasoning_content:
                        print(chunk.choices[0].delta.reasoning_content, end="", flush=True)
                    
                    if hasattr(chunk.choices[0].delta, 'content') and chunk.choices[0].delta.content:
                        chunk_content = chunk.choices[0].delta.content
                        content += chunk_content
                        print(chunk_content, end="", flush=True)
            
            print("\n=== 流式输出结束 ===\n")
            
            # 更新 token 使用量（从 API 响应获取）
            if usage:
                prompt_tokens = getattr(usage, 'prompt_tokens', None)
                if prompt_tokens is not None:
                    self.message_manager.update_token_usage(prompt_tokens)
                    if config.debug_mode:
                        completion_tokens = getattr(usage, 'completion_tokens', 0)
                        total_tokens = getattr(usage, 'total_tokens', 0)
                        logger.debug(f"Token 使用: prompt={prompt_tokens}, completion={completion_tokens}, total={total_tokens}")
                else:
                    logger.warning("API 响应中未找到 prompt_tokens")
            else:
                logger.warning("流式响应中未找到 usage 信息")
            
            # 解析内容
            parsed = self._parse_content(content)
            
            # 处理 thought
            if parsed["thought"]:
                logger.info(f"=== Thought ===\n{parsed['thought']}\n")
            
            # 处理 final_answer
            if parsed["final_answer"]:
                logger.info(f"=== Final Answer ===\n{parsed['final_answer']}\n")
                self.message_manager.add_final_answer(parsed["final_answer"])
                
                # 处理 reflection
                if parsed["reflection"]:
                    logger.info(f"=== Reflection ===\n{parsed['reflection']}\n")
                
                break
            
            # 处理 action
            if parsed["action"]:
                logger.info(f"=== Action ===\n{parsed['action']}\n")
                self.message_manager.add_assistant_action(parsed["action"])
                
                # 执行工具
                observation = self.tool_executor.execute(parsed["action"])
                logger.info(f"=== Observation ===\n{observation}\n")
                self.message_manager.add_observation(observation)
                continue
            
            # 如果没有 action 也没有 final_answer，尝试最后一次容错
            if not parsed["action"] and not parsed["final_answer"]:
                # 如果内容中有 reflection，说明任务可能已完成，只是格式不对
                if parsed["reflection"]:
                    # 尝试将整个内容（除了 reflection）作为 final_answer
                    content_without_reflection = re.sub(r"<reflection>.*?</reflection>", "", content, flags=re.DOTALL).strip()
                    content_without_reflection = re.sub(r"<thought>.*?</thought>", "", content_without_reflection, flags=re.DOTALL).strip()
                    content_without_reflection = re.sub(r"<action>.*?</action>", "", content_without_reflection, flags=re.DOTALL).strip()
                    if content_without_reflection:
                        logger.warning(f"模型输出格式不规范，但检测到 reflection，尝试自动修复")
                        parsed["final_answer"] = content_without_reflection
                        logger.info(f"=== Final Answer (自动修复) ===\n{parsed['final_answer']}\n")
                        self.message_manager.add_final_answer(parsed["final_answer"])
                        if parsed["reflection"]:
                            logger.info(f"=== Reflection ===\n{parsed['reflection']}\n")
                        break
                
                # 如果还是无法解析，报错
                logger.error(f"模型未输出 <action> 或 <final_answer>\n内容: {content}")
                raise RuntimeError("模型未输出 <action> 或 <final_answer>")

