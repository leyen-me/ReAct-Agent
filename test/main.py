import os
import json
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
logger = logging.getLogger("ReActAgent")


# ===================== 配置 =====================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("必须设置环境变量 OPENAI_API_KEY")

OPENAI_BASE_URL = "https://integrate.api.nvidia.com/v1"
OPENAI_MODEL = "qwen/qwen3.5-397b-a17b"
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


class ReActAgent:
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

    def chat(self, message: str) -> str:
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

            print("\n助手：", end="", flush=True)
            tool_call_started = False  # 是否已输出过工具调用前缀
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                logger.info(delta)

                if hasattr(delta, "content") and delta.content:
                    content_parts.append(delta.content)
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
                            if not tool_call_started:
                                print("【工具调用】", end="", flush=True)
                                tool_call_started = True
                            else:
                                print("\n【工具调用】", end="", flush=True)
                        if tc.function:
                            if tc.function.name:
                                tool_call_acc[tc_id]["name"] += tc.function.name
                                print(tc.function.name, end="", flush=True)
                            if tc.function.arguments:
                                tool_call_acc[tc_id][
                                    "arguments"
                                ] += tc.function.arguments
                                print(tc.function.arguments, end="", flush=True)

            full_content = "".join(content_parts)

            if tool_call_acc:
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
                print()  # 流式输出后换行
                return full_content

            # 空响应时避免死循环
            logger.warning("API 返回空响应")
            return ""


# ===================== TOOL Usage Example =====================

if __name__ == "__main__":
    agent = ReActAgent()
    agent.register_tool(ListFilesTool())
    agent.register_tool(GetFileMetadataTool())
    agent.register_tool(SearchCodeTool())
    agent.register_tool(ReadFileLinesTool())
    agent.register_tool(WriteFileTool())
    agent.register_tool(ApplyPatchTool())
    agent.register_tool(RunCommandTool())
    agent.register_tool(GitDiffTool())

    while True:
        user_input = input("用户：").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        agent.chat(user_input)
