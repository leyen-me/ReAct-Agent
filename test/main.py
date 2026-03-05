import os
import json
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
OPENAI_MODEL = "minimaxai/minimax-m2.5"
BASE_DIR = Path.cwd().resolve()

# ===================== 工具系统 =====================


def safe_resolve_path(user_path: str) -> Path:
    """安全解析路径，防止目录穿越"""
    abs_path = (BASE_DIR / user_path).resolve()

    try:
        abs_path.relative_to(BASE_DIR)
    except ValueError:
        raise PermissionError(f"路径 {user_path} 超出允许范围：{BASE_DIR}")

    return abs_path


class BaseTool:
    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def run(self, parameters: Dict[str, Any]) -> str:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# ===================== 文件读取工具 =====================


class ReadFileTool(BaseTool):
    """Read file with pagination (SWE-agent / Open Interpreter style).
    Returns total_lines so agent can call read_file(start_line=N, end_line=M) for next chunk.
    """

    name = "read_file"
    description = "Read part of a file. Returns content, start_line, end_line, total_lines for pagination. Agent can call read_file(start_line=121, end_line=240) for next chunk."

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "start_line": {
                "type": "integer",
                "description": "Start line number, default 1",
            },
            "end_line": {
                "type": "integer",
                "description": "End line number, omit to read to end of file",
            },
        },
        "required": ["path"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:
        try:
            path = parameters["path"]
            start_line = max(1, int(parameters.get("start_line", 1)))
            end_line = parameters.get("end_line")

            abs_path = safe_resolve_path(path)

            if not abs_path.exists():
                return json.dumps({"error": f"File not found: {path}"})

            if not abs_path.is_file():
                return json.dumps({"error": f"Not a file: {path}"})

            with abs_path.open("r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()

            total_lines = len(all_lines)
            if total_lines == 0:
                return json.dumps(
                    {"content": "", "start_line": 1, "end_line": 0, "total_lines": 0},
                )

            end_line = (
                min(end_line, total_lines) if end_line is not None else total_lines
            )
            end_line = max(end_line, start_line)

            # 1-based line numbers, 0-based slice
            slice_start = start_line - 1
            slice_end = end_line
            lines = all_lines[slice_start:slice_end]
            content = "".join(lines).rstrip("\n")

            result = {
                "content": content,
                "start_line": start_line,
                "end_line": end_line,
                "total_lines": total_lines,
            }
            return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.exception("ReadFileTool error")
            return json.dumps({"error": f"Failed to read file: {e}"})


# ===================== 文件编辑工具 =====================


class EditFileByLineTool(BaseTool):
    name = "edit_file_by_line"
    description = "通过行范围替换文件内容。"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
            "new_string": {"type": "string"},
        },
        "required": ["path", "start_line", "end_line", "new_string"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:
        try:
            path = parameters["path"]
            start_line = int(parameters["start_line"])
            end_line = int(parameters["end_line"])
            new_string = parameters["new_string"]

            abs_path = safe_resolve_path(path)

            if not abs_path.exists() or not abs_path.is_file():
                return f"文件无效：{path}"

            original_lines = abs_path.read_text(encoding="utf-8").splitlines(
                keepends=True
            )
            total = len(original_lines)

            if not (1 <= start_line <= total and 1 <= end_line <= total):
                return f"行号超出范围。文件共有 {total} 行。"

            if start_line > end_line:
                return "起始行不能大于结束行。"

            new_lines = new_string.splitlines(keepends=True)
            if not new_string.endswith("\n") and new_lines:
                new_lines[-1] = new_lines[-1].rstrip("\n")

            updated = (
                original_lines[: start_line - 1] + new_lines + original_lines[end_line:]
            )

            abs_path.write_text("".join(updated), encoding="utf-8")

            return f"已替换 {path} 第 {start_line}-{end_line} 行。"

        except Exception as e:
            logger.exception("EditFileByLineTool 出错")
            return f"编辑失败：{e}"


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
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "extra_body": {"reasoning": {"enabled": False}},
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
    agent.register_tool(ReadFileTool())

    while True:
        user_input = input("用户：").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        agent.chat(user_input)
