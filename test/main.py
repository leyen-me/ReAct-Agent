import os
import json
import uuid
import subprocess
import time
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI


# ===================== 日志 =====================

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_LOG_DIR = Path(__file__).resolve().parent
_LOG_FILE = _LOG_DIR / "agent.log"
_TASK_FILE = _LOG_DIR / "task.json"

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
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_DIR = SCRIPT_DIR / "workspace"
WORKSPACE_DIR = Path(
    os.getenv("WORKSPACE_DIR", str(DEFAULT_WORKSPACE_DIR))
).expanduser().resolve()
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

ENABLE_COLOR = os.getenv("NO_COLOR") is None and os.getenv("TERM") != "dumb"
ANSI_RESET = "\033[0m"
PLAN_COLOR = "\033[38;5;25m"
EXECUTE_COLOR = "\033[38;5;81m"
INFO_COLOR = "\033[38;5;244m"


def color_text(text: str, color: str) -> str:
    if not ENABLE_COLOR:
        return text
    return f"{color}{text}{ANSI_RESET}"

# ================= PATH SECURITY =================


def safe_resolve_path(user_path: str) -> Path:

    abs_path = (WORKSPACE_DIR / user_path).resolve()

    try:
        abs_path.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise PermissionError("Path outside workspace")

    return abs_path


def to_workspace_relative(path: Path) -> str:
    return str(path.resolve().relative_to(WORKSPACE_DIR))


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


@dataclass
class TaskRecord:
    id: str
    description: str
    status: str = "pending"
    result: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRecord":
        return cls(
            id=data["id"],
            description=data["description"],
            status=data.get("status", "pending"),
            result=data.get("result"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class TaskStore:
    def __init__(self, storage_path: Path = _TASK_FILE):
        self.storage_path = storage_path
        self._tasks: Dict[str, TaskRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return

        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            logger.exception("加载 task.json 失败")
            return

        if not isinstance(raw, list):
            logger.warning("task.json 格式无效，已忽略")
            return

        self._tasks.clear()
        for item in raw:
            if not isinstance(item, dict):
                continue
            try:
                task = TaskRecord.from_dict(item)
            except KeyError:
                continue
            self._tasks[task.id] = task

    def _save(self) -> None:
        payload = [
            task.to_dict()
            for task in sorted(self._tasks.values(), key=lambda task: task.created_at)
        ]
        temp_path = self.storage_path.with_suffix(".json.tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(self.storage_path)

    def reset(self) -> None:
        self._tasks.clear()
        self._save()

    def create_tasks(self, raw_tasks: List[Any]) -> List[Dict[str, Any]]:
        created: List[Dict[str, Any]] = []

        for raw_task in raw_tasks:
            if isinstance(raw_task, dict):
                description = str(raw_task.get("description", "")).strip()
            else:
                description = str(raw_task).strip()

            if not description:
                continue

            if any(task.description == description for task in self._tasks.values()):
                continue

            task = TaskRecord(id=str(uuid.uuid4())[:8], description=description)
            self._tasks[task.id] = task
            created.append(task.to_dict())

        self._save()
        return created

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [task.to_dict() for task in self._tasks.values()]

    def get(self, task_id: str) -> Optional[TaskRecord]:
        return self._tasks.get(task_id)

    def get_next_pending(self) -> Optional[TaskRecord]:
        for task in self._tasks.values():
            if task.status == "pending":
                return task
        return None

    def pending_tasks(self) -> List[Dict[str, Any]]:
        return [
            task.to_dict()
            for task in self._tasks.values()
            if task.status == "pending"
        ]

    def update_task(
        self, task_id: str, status: str, result: Optional[str] = None
    ) -> Dict[str, Any]:
        if status not in TASK_STATUS:
            raise ValueError("invalid status")

        task = self.get(task_id)
        if not task:
            raise KeyError("task not found")

        task.status = status
        if result is not None:
            task.result = result
        task.updated_at = time.time()
        self._save()
        return task.to_dict()


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

                rel = p.relative_to(WORKSPACE_DIR)

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
                    "path": to_workspace_relative(path),
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

            for file in WORKSPACE_DIR.rglob("*"):

                if not file.is_file():
                    continue

                try:

                    with open(file, encoding="utf-8", errors="ignore") as f:

                        for i, line in enumerate(f):

                            if query in line:

                                results.append(
                                    {
                                        "file": to_workspace_relative(file),
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
                cwd=WORKSPACE_DIR,
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
                cwd=WORKSPACE_DIR,
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
                cwd=WORKSPACE_DIR,
            )

            return self.success(p.stdout)

        except Exception as e:
            return self.fail(str(e))


class BaseAgent:
    def __init__(
        self,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_name: str = "助手",
    ):
        self.model = model or OPENAI_MODEL
        self.agent_name = agent_name
        self.agent_color = INFO_COLOR
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=300.0,
        )
        self.tools = []
        self.system_prompt = system_prompt or "You are a helpful assistant."
        self.base_messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": self.system_prompt,
            }
        ]
        self.messages: List[Dict[str, Any]] = list(self.base_messages)

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

    def reset_conversation(self) -> None:
        self.messages = list(self.base_messages)

    def chat(
        self,
        message: str,
        *,
        silent: bool = False,
        reset_history: bool = False,
        stop_after_tool_names: Optional[List[str]] = None,
    ) -> str:
        """
        silent: 为 True 时不向用户打印任何内容（用于 exec_agent 内部执行，反馈给 plan_agent）
        """
        if reset_history:
            self.reset_conversation()

        stop_after_tool_names = set(stop_after_tool_names or [])
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
                print(
                    f"\n{color_text(f'{self.agent_name}：', self.agent_color)}",
                    end="",
                    flush=True,
                )
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
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": full_content or "",
                        "tool_calls": tool_calls_list,
                    }
                )
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
                if any(
                    call["function"]["name"] in stop_after_tool_names
                    for call in tool_calls_list
                ):
                    if not silent:
                        print()
                    return full_content
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

TASK_STATUS = ["pending", "running", "done", "failed"]


class TaskPlanTool(BaseTool):
    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

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

        created = self.task_store.create_tasks(parameters["tasks"])
        return self.success(created)


class TaskListTool(BaseTool):
    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

    name = "list_tasks"
    description = "List tasks"

    parameters = {"type": "object", "properties": {}}

    def run(self, parameters):

        return self.success(self.task_store.list_tasks())


class TaskUpdateTool(BaseTool):
    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

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

        try:
            updated = self.task_store.update_task(
                task_id=parameters["task_id"],
                status=parameters["status"],
                result=parameters.get("result"),
            )
            return self.success(updated)
        except KeyError:
            return self.fail("task not found")
        except ValueError:
            return self.fail("invalid status")


class TaskNextTool(BaseTool):
    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

    name = "next_task"
    description = "Get next pending task"

    parameters = {"type": "object", "properties": {}}

    def run(self, parameters):

        task = self.task_store.get_next_pending()
        return self.success(task.to_dict() if task else None)


def execute_single_task(exec_agent: "ExecuteAgent", task_store: TaskStore) -> Dict[str, Any]:
    task = task_store.get_next_pending()
    if task is None:
        return {"executed": False, "task": None}

    task_store.update_task(task.id, "running")
    print(color_text(f"\n[执行中] {task.description}", EXECUTE_COLOR))

    task_prompt = (
        f"任务ID：{task.id}\n"
        f"任务描述：{task.description}\n\n"
        "执行完成后请调用 update_task 更新最终状态。调用后不要继续长篇总结。"
    )

    try:
        result = exec_agent.chat(
            task_prompt,
            silent=False,
            reset_history=True,
            stop_after_tool_names=["update_task"],
        )
    except Exception as e:
        logger.exception("执行任务失败: %s", task.description)
        result = f"执行异常：{e}"
        task_store.update_task(task.id, "failed", result=result)

    latest_task = task_store.get(task.id)
    if latest_task and latest_task.status == "running":
        task_store.update_task(task.id, "done", result=result)
        latest_task = task_store.get(task.id)
    elif latest_task and not latest_task.result:
        task_store.update_task(task.id, latest_task.status, result=result)
        latest_task = task_store.get(task.id)

    if latest_task is None:
        raise RuntimeError(f"task disappeared: {task.id}")

    print(
        color_text(
            f"[任务结束] {latest_task.description} -> {latest_task.status}",
            EXECUTE_COLOR,
        )
    )
    return {"executed": True, "task": latest_task.to_dict()}


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
        self,
        task_store: TaskStore,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        system_prompt = system_prompt or """
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

工作区根目录是 WORKSPACE_DIR，所有路径都应理解为相对于该目录，而不是脚本所在目录。

6. 你的目标是生成清晰的任务列表，而不是直接解决问题。

7. 你可以在创建任务后调用 execute_next_task，把待办任务逐个交给 ExecuteAgent 执行；对于需要真正落地的需求，创建任务后就应立即开始调用它。

8. 当你确认要拆分任务时，只调用一次 task_plan。

9. 不要继续追加新的 task_plan。创建任务后，应该转入执行和汇总，而不是重复规划。

10. 如果用户只是寒暄、提问或闲聊，不要创建任务。

11. 当 execute_next_task 返回还有待办任务时，继续调用 execute_next_task；当没有待办任务时，再向用户汇总最终结果。
        """
        super().__init__(model, system_prompt, agent_name="PlanAgent")
        self.agent_color = PLAN_COLOR
        self.task_store = task_store
        self.register_tool(ListFilesTool())
        self.register_tool(GetFileMetadataTool())
        self.register_tool(SearchCodeTool())
        self.register_tool(ReadFileLinesTool())
        self.register_tool(TaskPlanTool(task_store))
        self.register_tool(TaskListTool(task_store))
        self.register_tool(TaskNextTool(task_store))


# ===================== Execute Agent =====================


class ExecuteAgent(BaseAgent):
    def __init__(
        self,
        task_store: TaskStore,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        system_prompt = system_prompt or """
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

所有文件路径和命令执行目录都限定在 WORKSPACE_DIR。

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
        super().__init__(model, system_prompt, agent_name="ExecuteAgent")
        self.agent_color = EXECUTE_COLOR
        self.task_store = task_store
        self.register_tool(ListFilesTool())
        self.register_tool(GetFileMetadataTool())
        self.register_tool(SearchCodeTool())
        self.register_tool(ReadFileLinesTool())
        self.register_tool(WriteFileTool())
        self.register_tool(ApplyPatchTool())
        self.register_tool(RunCommandTool())
        self.register_tool(GitDiffTool())
        self.register_tool(TaskUpdateTool(task_store))


# ===================== TOOL Usage Example =====================


class ExecuteNextTaskTool(BaseTool):
    def __init__(self, task_store: TaskStore, exec_agent: ExecuteAgent):
        self.task_store = task_store
        self.exec_agent = exec_agent

    name = "execute_next_task"
    description = "Dispatch next pending task to ExecuteAgent"
    parameters = {"type": "object", "properties": {}}

    def run(self, parameters):
        try:
            result = execute_single_task(self.exec_agent, self.task_store)
            return self.success(result)
        except Exception as e:
            return self.fail(str(e))


def print_task_summary(task_store: TaskStore) -> None:
    all_tasks = task_store.list_tasks()
    if not all_tasks:
        return

    print(f"\n{color_text('助手：任务执行完成，结果如下：', INFO_COLOR)}")
    for task in all_tasks:
        print(f"- [{task['status']}] {task['description']}")


if __name__ == "__main__":
    task_store = TaskStore()
    exec_agent = ExecuteAgent(task_store)
    plan_agent = PlanAgent(task_store)
    plan_agent.register_tool(ExecuteNextTaskTool(task_store, exec_agent))

    print(f"当前工作区：{WORKSPACE_DIR}")
    print(f"任务文件：{_TASK_FILE}")

    while True:
        user_input = input("用户：")
        if user_input in {"quit", "exit"}:
            break
        task_store.reset()
        # 1 规划任务
        plan_agent.chat(
            user_input,
            reset_history=True,
        )
