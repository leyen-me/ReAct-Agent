import os
import json
import uuid
import subprocess
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI


# ===================== 日志 =====================

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DIR = Path(__file__).resolve().parent
_LOG_FILE = _LOG_DIR / "agent.log"

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    handlers=[
        # logging.StreamHandler(), // 将日志输出到控制台
        logging.FileHandler(_LOG_FILE, encoding="utf-8", mode="a"),
    ],
)
logger = logging.getLogger("Agent")


# ===================== 配置 =====================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("必须设置环境变量 OPENAI_API_KEY")

OPENAI_BASE_URL = "https://api.lkeap.cloud.tencent.com/coding/v3"
OPENAI_MODEL = "minimax-m2.5"
BASE_DIR = Path.cwd().resolve()


# ================= PATH SECURITY =================


def safe_resolve_path(user_path: str) -> Path:

    abs_path = (BASE_DIR / user_path).resolve()

    try:
        abs_path.relative_to(BASE_DIR)
    except ValueError:
        raise PermissionError("Path outside workspace")

    return abs_path


# ================= TOOL BASE =================


class BaseTool:

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def run(self, parameters: Dict[str, Any]) -> str:
        raise NotImplementedError

    def success(self, data):
        return json.dumps(
            {"success": True, "data": data, "error": None},
            ensure_ascii=False,
        )

    def fail(self, msg):
        return json.dumps(
            {"success": False, "data": None, "error": msg},
            ensure_ascii=False,
        )

    def to_dict(self):

        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ================= FILE NAVIGATION =================


class ListFilesTool(BaseTool):

    name = "list_files"
    description = "List files in directory"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "depth": {"type": "integer"},
        },
    }

    def run(self, parameters):

        path = parameters.get("path", ".")
        depth = parameters.get("depth", 3)

        try:

            root = safe_resolve_path(path)

            results = []

            for p in root.rglob("*"):

                rel = p.relative_to(BASE_DIR)

                if len(rel.parts) > depth:
                    continue

                results.append(
                    {
                        "path": str(rel),
                        "type": "directory" if p.is_dir() else "file",
                    }
                )

            return self.success(results)

        except Exception as e:
            return self.fail(str(e))


# ================= METADATA =================


class GetFileMetadataTool(BaseTool):

    name = "get_file_metadata"
    description = "Get metadata of file"

    parameters = {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    }

    def run(self, parameters):

        try:

            path = safe_resolve_path(parameters["path"])

            stat = path.stat()

            line_count = 0

            if path.is_file():

                with open(path, encoding="utf-8", errors="ignore") as f:
                    line_count = sum(1 for _ in f)

            return self.success(
                {
                    "path": str(path),
                    "size_bytes": stat.st_size,
                    "line_count": line_count,
                }
            )

        except Exception as e:
            return self.fail(str(e))


# ================= SEARCH =================


class SearchCodeTool(BaseTool):

    name = "search_code"
    description = "Search keyword in codebase"

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    }

    def run(self, parameters):

        query = parameters["query"]
        max_results = parameters.get("max_results", 20)

        results = []

        try:

            for file in BASE_DIR.rglob("*"):

                if not file.is_file():
                    continue

                try:

                    with open(file, encoding="utf-8", errors="ignore") as f:

                        for i, line in enumerate(f):

                            if query in line:

                                results.append(
                                    {
                                        "file": str(file.relative_to(BASE_DIR)),
                                        "line": i + 1,
                                        "snippet": line.strip(),
                                    }
                                )

                                if len(results) >= max_results:
                                    return self.success(results)

                except Exception:
                    continue

            return self.success(results)

        except Exception as e:
            return self.fail(str(e))


# ================= FILE READ =================


class ReadFileLinesTool(BaseTool):

    name = "read_file_lines"
    description = "Read lines from file"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
        },
        "required": ["path"],
    }

    def run(self, parameters):

        try:

            path = safe_resolve_path(parameters["path"])
            start = parameters.get("start_line", 1)
            end = parameters.get("end_line")

            with open(path, encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()

            total = len(lines)

            end = end or total

            content = "".join(lines[start - 1 : end])

            return self.success(
                {
                    "content": content,
                    "start_line": start,
                    "end_line": end,
                    "total_lines": total,
                }
            )

        except Exception as e:
            return self.fail(str(e))


# ================= FILE WRITE =================


class WriteFileTool(BaseTool):

    name = "write_file"
    description = "Overwrite file"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    }

    def run(self, parameters):

        try:

            path = safe_resolve_path(parameters["path"])

            path.write_text(parameters["content"], encoding="utf-8")

            return self.success("written")

        except Exception as e:
            return self.fail(str(e))


# ================= PATCH =================


class ApplyPatchTool(BaseTool):

    name = "apply_patch"
    description = "Apply unified diff patch"

    parameters = {
        "type": "object",
        "properties": {"patch": {"type": "string"}},
        "required": ["patch"],
    }

    def run(self, parameters):

        try:

            patch = parameters["patch"]

            p = subprocess.run(
                ["patch", "-p0"],
                input=patch,
                text=True,
                capture_output=True,
            )

            return self.success(
                {
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                    "exit_code": p.returncode,
                }
            )

        except Exception as e:
            return self.fail(str(e))


# ================= COMMAND =================


class RunCommandTool(BaseTool):

    name = "run_command"
    description = "Execute shell command"

    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "timeout": {"type": "integer"},
        },
        "required": ["command"],
    }

    def run(self, parameters):

        command = parameters["command"]
        timeout = parameters.get("timeout", 30)

        deny = ["rm -rf", "shutdown", "reboot", "sudo"]

        if any(x in command for x in deny):
            return self.fail("command not allowed")

        try:

            p = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            return self.success(
                {
                    "stdout": p.stdout,
                    "stderr": p.stderr,
                    "exit_code": p.returncode,
                }
            )

        except Exception as e:
            return self.fail(str(e))


# ================= GIT =================
class GitDiffTool(BaseTool):

    name = "git_diff"
    description = "Show git diff"

    parameters = {"type": "object", "properties": {}}

    def run(self, parameters):

        try:

            p = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
            )

            return self.success(p.stdout)

        except Exception as e:
            return self.fail(str(e))


class BaseAgent:
    def __init__(
        self, model: Optional[str] = None, system_prompt: Optional[str] = None
    ):
        self.model = model or OPENAI_MODEL
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=300.0,
        )
        self.tools = []
        self.messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": system_prompt or "You are a helpful assistant.",
            }
        ]

    def register_tool(self, tool: BaseTool) -> None:
        self.tools.append(tool)

    def get_tools(self) -> List[BaseTool]:
        return [{"type": "function", "function": tool.to_dict()} for tool in self.tools]

    def execute_tool(self, name: str, args_json: str) -> str:
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError:
            return "参数 JSON 解析失败"
        tool = next((t for t in self.tools if t.name == name), None)
        if not tool:
            return f"未找到工具：{name}"
        return tool.run(args)

    def chat(self, message: str, *, silent: bool = False) -> str:
        """
        silent: 为 True 时不向用户打印任何内容（用于 exec_agent 内部执行，反馈给 plan_agent）
        """
        self.messages.append({"role": "user", "content": message})
        tools = self.get_tools()
        api_kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": self.messages,
            "stream": True,
            "temperature": 1,
            "top_p": 0.95,
            # "extra_body": {"reasoning": {"enabled": False}},
            # "chat_template_kwargs": {"enable_thinking":False},
        }
        if tools:
            api_kwargs["tools"] = tools
            api_kwargs["tool_choice"] = "auto"

        while True:
            stream = self.client.chat.completions.create(**api_kwargs)

            content_parts: List[str] = []
            tool_call_acc: Dict[str, Dict[str, str]] = {}
            last_tool_call_id: Optional[str] = None

            if not silent:
                print("\n助手：", end="", flush=True)
            tool_call_started = False  # 是否已输出过工具调用前缀
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                logger.info(delta)

                if hasattr(delta, "content") and delta.content:
                    content_parts.append(delta.content)
                    if not silent:
                        print(delta.content, end="", flush=True)

                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        tc_id = tc.id or last_tool_call_id
                        if tc_id is None:
                            continue
                        last_tool_call_id = tc_id
                        if tc_id not in tool_call_acc:
                            tool_call_acc[tc_id] = {
                                "id": tc_id,
                                "name": "",
                                "arguments": "",
                            }
                            if not silent:
                                if not tool_call_started:
                                    print("【工具调用】", end="", flush=True)
                                    tool_call_started = True
                                else:
                                    print("\n【工具调用】", end="", flush=True)
                        if tc.function:
                            if tc.function.name:
                                tool_call_acc[tc_id]["name"] += tc.function.name
                                if not silent:
                                    print(tc.function.name, end="", flush=True)
                            if tc.function.arguments:
                                tool_call_acc[tc_id][
                                    "arguments"
                                ] += tc.function.arguments
                                if not silent:
                                    print(tc.function.arguments, end="", flush=True)

            full_content = "".join(content_parts)

            if tool_call_acc:
                if not silent:
                    print()  # 工具调用流式输出后换行
                tool_calls_list = [
                    {
                        "id": data["id"],
                        "type": "function",
                        "function": {
                            "name": data["name"],
                            "arguments": data["arguments"],
                        },
                    }
                    for data in tool_call_acc.values()
                ]
                for call in tool_calls_list:
                    result = self.execute_tool(
                        call["function"]["name"],
                        call["function"]["arguments"],
                    )
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": result,
                        }
                    )
                continue

            if full_content:
                self.messages.append({"role": "assistant", "content": full_content})
                if not silent:
                    print()  # 流式输出后换行
                return full_content

            # 空响应时避免死循环
            logger.warning("API 返回空响应")
            return ""


# ===================== Plan Agent =====================

tasks = {}

TASK_STATUS = ["pending", "running", "done", "failed"]


class TaskPlanTool(BaseTool):

    name = "task_plan"
    description = "Create tasks"

    parameters = {
        "type": "object",
        "properties": {
            "tasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"description": {"type": "string"}},
                    "required": ["description"],
                },
            }
        },
        "required": ["tasks"],
    }

    def run(self, parameters):

        created = []

        for desc in parameters["tasks"]:

            task_id = str(uuid.uuid4())[:8]

            task = {
                "id": task_id,
                "description": desc,
                "status": "pending",
                "result": None,
                "created_at": time.time(),
            }

            tasks[task_id] = task

            created.append(task)

        return self.success(created)


class TaskListTool(BaseTool):

    name = "list_tasks"
    description = "List tasks"

    parameters = {"type": "object", "properties": {}}

    def run(self, parameters):

        return self.success(list(tasks.values()))


class TaskUpdateTool(BaseTool):

    name = "update_task"

    parameters = {
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["pending", "running", "done", "failed"],
            },
            "result": {"type": "string"},
        },
        "required": ["task_id", "status"],
    }

    def run(self, parameters):

        task_id = parameters["task_id"]

        if task_id not in tasks:
            return self.fail("task not found")

        status = parameters["status"]

        if status not in TASK_STATUS:
            return self.fail("invalid status")

        tasks[task_id]["status"] = status

        if "result" in parameters:
            tasks[task_id]["result"] = parameters["result"]

        return self.success(tasks[task_id])


class TaskNextTool(BaseTool):

    name = "next_task"
    description = "Get next pending task"

    parameters = {"type": "object", "properties": {}}

    def run(self, parameters):

        for task in tasks.values():
            if task["status"] == "pending":
                return self.success(task)

        return self.success(None)
    

class PlanAgent(BaseAgent):
    """
    1. 与用户直接交互的 PlanAgent， 用户不会直接与 ExecuteAgent 交互
    2. 理解用户需求，使用工具查看环境、项目等结构。做出规划。 并生成任务列表。
    3. 分配任务给 ExecuteAgent 执行。
    4. ExecuteAgent 执行任务，直到子任务完成。并反馈任务进度。
    5. 当子任务完成时，PlanAgent 主动汇报任务完成情况。
    6. 当所有子任务完成时，PlanAgent 主动汇报任务完成情况。
    """

    def __init__(
        self, model: Optional[str] = None, system_prompt: Optional[str] = None
    ):
        super().__init__(model, system_prompt)
        
        system_prompt = """
你是一个任务规划 Agent（PlanAgent）。

你的职责是理解用户需求，并将复杂任务拆分成多个可执行的小任务。

规则：

1. 当用户提出复杂需求时，你应该：
   - 使用工具查看项目结构
   - 搜索相关代码
   - 阅读必要文件
   - 然后拆分任务

2. 使用 task_plan 工具创建任务列表。

3. 每个任务必须：
   - 明确
   - 可执行
   - 粒度适中

好的任务示例：
- 查看 login.py 的实现
- 搜索所有 login 相关代码
- 修改 login.py 添加日志
- 运行测试验证修改

坏的任务示例：
- 修复系统
- 修改代码

4. 如果任务已经存在，不要重复创建。

5. 可以使用以下工具理解项目：
- list_files
- search_code
- read_file_lines
- get_file_metadata

6. 你的目标是生成清晰的任务列表，而不是直接解决问题。

7. 执行 Agent 会静默执行任务，并将结果反馈给你。

8. 任务完成后，你会收到执行结果。若还有待办任务，请简要回复「继续」；若全部完成，请向用户汇报完成情况。
        """
        self.messages.append({
            "role": "system",
            "content": system_prompt,
        })
        self.register_tool(ListFilesTool())
        self.register_tool(GetFileMetadataTool())
        self.register_tool(SearchCodeTool())
        self.register_tool(ReadFileLinesTool())
        self.register_tool(TaskPlanTool())
        self.register_tool(TaskListTool())
        self.register_tool(TaskNextTool())


# ===================== Execute Agent =====================


class ExecuteAgent(BaseAgent):
    def __init__(
        self, model: Optional[str] = None, system_prompt: Optional[str] = None
    ):
        super().__init__(model, system_prompt)
        system_prompt = """
你是一个任务执行 Agent（ExecuteAgent）。

你的职责是执行单个任务，并反馈执行结果。

规则：

1. 你会收到一个任务描述，例如：

任务：
修改 login.py 添加日志

2. 为了完成任务，你可以使用以下工具：

代码理解：
- list_files
- search_code
- read_file_lines
- get_file_metadata

代码修改：
- write_file
- apply_patch

系统操作：
- run_command
- git_diff

3. 执行任务时应该：

步骤1：理解任务  
步骤2：查看相关代码  
步骤3：进行修改或执行命令  
步骤4：验证结果  

4. 尽量使用工具，而不是猜测代码。

5. 如果需要修改代码：
优先使用 apply_patch。

6. 当任务完成时，需要调用 update_task：

status = "done"

如果任务失败：

status = "failed"

7. 提供简短清晰的执行结果。
        """
        self.messages.append(
            {
                "role": "system",
                "content": system_prompt,
            }
        )
        self.register_tool(ListFilesTool())
        self.register_tool(GetFileMetadataTool())
        self.register_tool(SearchCodeTool())
        self.register_tool(ReadFileLinesTool())
        self.register_tool(WriteFileTool())
        self.register_tool(ApplyPatchTool())
        self.register_tool(RunCommandTool())
        self.register_tool(GitDiffTool())
        self.register_tool(TaskUpdateTool())


# ===================== TOOL Usage Example =====================


def run_tasks(plan_agent, exec_agent):
    """
    exec_agent 不直接与用户交互，执行结果反馈给 plan_agent。
    plan_agent 检查任务完成情况，决定下一个任务，直到问题解决。
    """
    summary_msg = (
        "所有任务已执行完毕。请根据任务列表中的执行结果，向用户汇报完成情况。"
    )

    while True:
        pending = [t for t in tasks.values() if t["status"] == "pending"]
        if not pending:
            # 所有任务完成，由 plan_agent 向用户汇报
            plan_agent.chat(summary_msg)
            break

        task = pending[0]
        task["status"] = "running"
        print(f"\n[执行中] {task['description']}")

        # exec_agent 静默执行，不向用户打印，结果仅反馈给 plan_agent
        result = exec_agent.chat(task["description"], silent=True)

        task["status"] = "done"
        task["result"] = result

        # 将执行结果反馈给 plan_agent
        remaining = [t for t in tasks.values() if t["status"] == "pending"]
        if remaining:
            # 还有待办，plan_agent 知晓后继续下一轮
            feedback = (
                f"任务「{task['description']}」已完成。\n"
                f"执行结果：{result}\n\n"
                "还有待办任务，请简要回复「继续」以执行下一个。"
            )
            plan_agent.chat(feedback)
        else:
            # 最后一个任务完成，plan_agent 向用户汇报
            plan_agent.chat(summary_msg)
            break


if __name__ == "__main__":
    plan_agent = PlanAgent()
    exec_agent = ExecuteAgent()

    while True:
        user_input = input("用户：")
        if user_input in {"quit", "exit"}:
            break
        # 1 规划任务
        plan_agent.chat(user_input)
        # 2 执行任务（exec_agent 静默执行，反馈给 plan_agent，由 plan_agent 驱动流转）
        run_tasks(plan_agent, exec_agent)
