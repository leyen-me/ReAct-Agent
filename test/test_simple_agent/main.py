import os
import json
import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from openai import OpenAI


# ===================== 日志 =====================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ReActAgent")


# ===================== 配置 =====================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("必须设置环境变量 OPENAI_API_KEY")

OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL",
    "https://integrate.api.nvidia.com/v1",
).strip()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")

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
    name = "read_file"
    description = "读取文件，可指定行范围或分页读取。"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "encoding": {"type": "string", "default": "utf-8"},
            "start_line": {"type": "integer", "default": 1},
            "end_line": {"type": "integer"},
            "max_lines": {"type": "integer", "default": 100},
            "with_line_numbers": {"type": "boolean", "default": False},
        },
        "required": ["path"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:
        try:
            path = parameters["path"]
            encoding = parameters.get("encoding", "utf-8")
            start_line = max(1, int(parameters.get("start_line", 1)))
            end_line = parameters.get("end_line")
            max_lines = max(1, int(parameters.get("max_lines", 100)))
            with_line_numbers = parameters.get("with_line_numbers", False)

            abs_path = safe_resolve_path(path)

            if not abs_path.exists():
                return f"文件未找到：{path}"
            if not abs_path.is_file():
                return f"不是文件：{path}"

            lines: List[str] = []
            total_lines = 0

            with abs_path.open("r", encoding=encoding, errors="replace") as f:
                for line in f:
                    total_lines += 1
                    if total_lines >= start_line:
                        lines.append(line.rstrip("\n"))

                    if end_line and total_lines >= end_line:
                        break
                    if len(lines) >= max_lines:
                        break

            if not lines:
                return f"文件无可读取内容（共 {total_lines} 行）。"

            if with_line_numbers:
                lines = [
                    f"{start_line + i:4d} | {line}"
                    for i, line in enumerate(lines)
                ]

            meta = (
                f"[文件: {path}, 行 {start_line}-"
                f"{start_line + len(lines) - 1} / 共 {total_lines} 行]"
            )

            return meta + "\n" + "\n".join(lines)

        except Exception as e:
            logger.exception("ReadFileTool 出错")
            return f"读取文件失败：{e}"


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

            original_lines = abs_path.read_text(encoding="utf-8").splitlines(keepends=True)
            total = len(original_lines)

            if not (1 <= start_line <= total and 1 <= end_line <= total):
                return f"行号超出范围。文件共有 {total} 行。"

            if start_line > end_line:
                return "起始行不能大于结束行。"

            new_lines = new_string.splitlines(keepends=True)
            if not new_string.endswith("\n") and new_lines:
                new_lines[-1] = new_lines[-1].rstrip("\n")

            updated = (
                original_lines[: start_line - 1]
                + new_lines
                + original_lines[end_line:]
            )

            abs_path.write_text("".join(updated), encoding="utf-8")

            return f"已替换 {path} 第 {start_line}-{end_line} 行。"

        except Exception as e:
            logger.exception("EditFileByLineTool 出错")
            return f"编辑失败：{e}"


# ===================== Memory 工具 =====================

class MemoryTool(BaseTool):
    name = "memory"
    description = "长期记忆工具。"

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["store", "recall", "list_keys", "list_all"],
            },
            "key": {"type": "string"},
            "value": {"type": "string"},
            "query": {"type": "string"},
        },
        "required": ["action"],
    }

    def __init__(self):
        self._path = BASE_DIR / ".agent_memory.json"
        self._storage: Dict[str, str] = {}
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                self._storage = json.loads(self._path.read_text("utf-8"))
            except Exception:
                logger.warning("记忆文件损坏，已忽略")

    def _save(self):
        self._path.write_text(
            json.dumps(self._storage, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def run(self, parameters: Dict[str, Any]) -> str:
        action = parameters["action"]

        if action == "store":
            key = parameters.get("key")
            value = parameters.get("value")
            if not key or value is None:
                return "store 操作需要 key 和 value"
            self._storage[str(key)] = str(value)
            self._save()
            return f"已存储记忆：{key}"

        if action == "recall":
            key = parameters.get("key")
            query = parameters.get("query")

            if key:
                return self._storage.get(key, "未找到该键")

            if query:
                q = query.lower()
                matches = [
                    f"{k}: {v}"
                    for k, v in self._storage.items()
                    if q in k.lower() or q in v.lower()
                ]
                return "\n".join(matches) if matches else "未找到相关记忆"

            return "recall 需要 key 或 query"

        if action == "list_keys":
            return ", ".join(self._storage.keys()) or "暂无记忆"

        if action == "list_all":
            return json.dumps(self._storage, ensure_ascii=False, indent=2)

        return "未知操作"


# ===================== Dispatcher =====================

class DispatcherTool(BaseTool):
    name = "dispatcher"
    description = "并行分发任务"

    parameters = {
        "type": "object",
        "properties": {
            "prompts": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            }
        },
        "required": ["prompts"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:
        prompts = parameters["prompts"]

        def subtask(prompt: str) -> str:
            agent = ReActAgent()
            return agent.run(prompt)

        results = [""] * len(prompts)

        with ThreadPoolExecutor(max_workers=min(4, len(prompts))) as executor:
            futures = {
                executor.submit(subtask, p): i
                for i, p in enumerate(prompts)
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    results[idx] = f"子任务异常: {e}"

        return "\n\n".join(results)


# ===================== 工具注册 =====================

TOOLS = {
    tool.name: tool
    for tool in [
        ReadFileTool(),
        EditFileByLineTool(),
        MemoryTool(),
        DispatcherTool(),
    ]
}

AI_ALL_TOOLS = [
    {"type": "function", "function": tool.to_dict()}
    for tool in TOOLS.values()
]


# ===================== Agent =====================

class ReActAgent:
    def __init__(self, model: Optional[str] = None):
        self.model = model or OPENAI_MODEL
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=300.0,
        )
        self.messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": "你是一个具备文件访问和长期记忆能力的编程助手。",
            }
        ]

    def execute_tool(self, name: str, args_json: str) -> str:
        try:
            args = json.loads(args_json)
        except json.JSONDecodeError:
            return "参数 JSON 解析失败"

        tool = TOOLS.get(name)
        if not tool:
            return f"未找到工具：{name}"

        return tool.run(args)

    def run(self, message: str) -> str:
        self.messages.append({"role": "user", "content": message})

        for _ in range(5):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=AI_ALL_TOOLS,
                tool_choice="auto",
            )

            msg = response.choices[0].message

            if msg.tool_calls:
                for call in msg.tool_calls:
                    result = self.execute_tool(
                        call.function.name,
                        call.function.arguments,
                    )

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    })
                continue

            if msg.content:
                self.messages.append({
                    "role": "assistant",
                    "content": msg.content,
                })
                print(f"\n助手：{msg.content}")
                return msg.content

        return "达到最大步骤数，停止执行。"


# ===================== CLI =====================

if __name__ == "__main__":
    agent = ReActAgent()

    while True:
        user_input = input("用户：").strip()
        if user_input.lower() in {"quit", "exit"}:
            break
        agent.run(user_input)
