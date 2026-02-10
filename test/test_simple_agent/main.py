import os
import json
from pathlib import Path
import time
from typing import Any, Dict, List
from openai import OpenAI
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === 配置 ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")

# 沙箱根目录（防止路径遍历）
BASE_DIR = Path.cwd().resolve()


def safe_resolve_path(user_path: str) -> Path:
    """安全解析路径，限制在 BASE_DIR 内"""
    abs_path = (BASE_DIR / user_path).resolve()
    if not abs_path.is_relative_to(BASE_DIR):
        raise PermissionError(
            f"Path {user_path} is outside allowed directory: {BASE_DIR}"
        )
    return abs_path


# === 工具基类 ===
class BaseTool:
    def __init__(self):
        self.name: str = ""
        self.description: str = ""
        self.parameters: Dict[str, Any] = {}

    def run(self, parameters: Dict[str, Any]) -> str:
        """统一接口：接收参数字典，返回结果字符串"""
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


# === 具体工具 ===
class ReadFileTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "read_file"
        self.description = (
            "Read a file by path with optional line range or pagination. "
            "Useful for large files to avoid overwhelming context."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "encoding": {
                    "type": "string",
                    "description": "File encoding",
                    "default": "utf-8",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Start line number (1-based, inclusive). Default: 1",
                    "default": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "End line number (1-based, inclusive). If omitted, reads to end or up to max_lines.",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to return (starting from start_line). Default: 100",
                    "default": 100,
                },
                "with_line_numbers": {
                    "type": "boolean",
                    "description": "Include line numbers in output (e.g., '   1 | content')",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    def run(self, parameters: Dict[str, Any]) -> str:
        try:
            path = parameters["path"]
            encoding = parameters.get("encoding", "utf-8")
            start_line = max(1, int(parameters.get("start_line", 1)))
            end_line = parameters.get("end_line")
            max_lines = int(parameters.get("max_lines", 100))
            with_line_numbers = parameters.get("with_line_numbers", False)

            if max_lines <= 0:
                max_lines = 100

            abs_path = safe_resolve_path(path)
            if not abs_path.exists():
                return f"File not found: {path}"
            if not abs_path.is_file():
                return f"Not a file: {path}"

            # 逐行读取，避免加载整个大文件到内存
            lines = []
            total_lines = 0
            with open(abs_path, "r", encoding=encoding, errors="replace") as f:
                for line in f:
                    total_lines += 1
                    if total_lines >= start_line:
                        # 去掉行尾换行符（保留原始内容，但便于控制输出）
                        lines.append(line.rstrip("\n"))
                    if end_line and total_lines >= end_line:
                        break
                    if len(lines) >= max_lines:
                        break

            if not lines:
                if total_lines == 0:
                    return f"File is empty: {path}"
                else:
                    return f"No lines in range [{start_line}, ...]. File has {total_lines} lines."

            # 应用行号
            if with_line_numbers:
                start_num = start_line
                output_lines = [
                    f"{(start_num + i):4d} | {line}" for i, line in enumerate(lines)
                ]
            else:
                output_lines = lines

            result = "\n".join(output_lines)

            # 添加元信息（帮助 Agent 理解上下文）
            info = f"[File: {path}, Lines {start_line}-{start_line + len(lines) - 1} of {total_lines}]"
            if len(lines) == max_lines and (
                not end_line or start_line + max_lines - 1 < end_line
            ):
                info += " (truncated, use higher end_line or max_lines to see more)"

            return f"{info}\n{result}"

        except Exception as e:
            logger.error(f"ReadFileTool error: {e}")
            return f"Error reading file: {e}"


class EditFileByLineTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "edit_file_by_line"
        self.description = "Replace lines in a file by line range"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative file path"},
                "start_line": {
                    "type": "integer",
                    "description": "Start line (1-based, inclusive)",
                },
                "end_line": {
                    "type": "integer",
                    "description": "End line (1-based, inclusive)",
                },
                "new_string": {
                    "type": "string",
                    "description": "New content to insert (may contain \\n)",
                },
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
            if not abs_path.exists():
                return f"File not found: {path}"
            if not abs_path.is_file():
                return f"Not a file: {path}"

            with open(abs_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            total = len(original_lines)
            if not (1 <= start_line <= total and 1 <= end_line <= total):
                return f"Line numbers out of range. File has {total} lines."
            if start_line > end_line:
                return (
                    f"Invalid range: start_line ({start_line}) > end_line ({end_line})"
                )

            # 处理新内容：确保每行以 \n 结尾（便于 writelines）
            new_lines = []
            if new_string:
                parts = new_string.split("\n")
                for i, part in enumerate(parts):
                    if i == len(parts) - 1 and not new_string.endswith("\n"):
                        # 最后一行无换行 → 保留原样
                        new_lines.append(part)
                    else:
                        new_lines.append(part + "\n")

            # 构建新文件内容
            updated_lines = (
                original_lines[: start_line - 1] + new_lines + original_lines[end_line:]
            )

            with open(abs_path, "w", encoding="utf-8") as f:
                f.writelines(updated_lines)

            replaced_count = end_line - start_line + 1
            return f"Successfully replaced lines {start_line}-{end_line} in {path} ({replaced_count} lines)."

        except Exception as e:
            logger.error(f"EditFileByLineTool error: {e}")
            return f"Error editing file: {e}"


class MemoryTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "memory"
        self.description = (
            "Access your long-term memory to recall user preferences, project facts, or stored keys. "
            "ALWAYS call this tool before answering questions about past interactions or personal details."
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["store", "recall", "list_keys", "list_all"],
                    "description": (
                        "'store': save a fact; "
                        "'recall': get by key or natural language query; "
                        "'list_keys': show all memory keys; "
                        "'list_all': show all memories (key + value preview)"
                    ),
                },
                "key": {
                    "type": "string",
                    "description": "Memory identifier (required for 'store'; optional for 'recall')",
                },
                "value": {
                    "type": "string",
                    "description": "The fact to store (required for 'store')",
                },
                "query": {
                    "type": "string",
                    "description": "Natural language query to find relevant memories (used in 'recall')",
                },
            },
            "required": ["action"],
        }
        # 持久化存储路径
        self._memory_path = BASE_DIR / ".agent_memory.json"
        self._storage: Dict[str, str] = {}
        self._load()

    def _load(self):
        if self._memory_path.exists():
            try:
                with open(self._memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # 确保是字符串字典
                    self._storage = {str(k): str(v) for k, v in data.items()}
            except Exception as e:
                logger.warning(f"Failed to load memory from {self._memory_path}: {e}")

    def _save(self):
        try:
            # 确保目录存在
            self._memory_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._memory_path, "w", encoding="utf-8") as f:
                json.dump(self._storage, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memory to {self._memory_path}: {e}")

    def run(self, parameters: Dict[str, Any]) -> str:
        action = parameters.get("action")

        if action == "store":
            key = parameters.get("key")
            value = parameters.get("value")
            if not key or value is None:
                return "Error: 'key' and 'value' are required for action='store'."
            self._storage[str(key)] = str(value)
            self._save()
            return f"✅ Stored memory: '{key}' = '{value}'"

        elif action == "recall":
            key = parameters.get("key")
            query = parameters.get("query")

            if key:
                # 精确 key 查找
                if key in self._storage:
                    return f"📌 Recall by key '{key}': {self._storage[key]}"
                else:
                    return f"❌ No memory found for key: '{key}'"

            elif query:
                # 简单模糊匹配：检查 key 或 value 是否包含 query（不区分大小写）
                query_lower = str(query).lower()
                matches = []
                for k, v in self._storage.items():
                    if query_lower in k.lower() or query_lower in v.lower():
                        matches.append(f"{k}: {v}")
                if matches:
                    return "🔍 Relevant memories:\n" + "\n".join(matches)
                else:
                    return "❌ No relevant memories found for query: '{}'".format(query)

            else:
                return "Error: 'key' or 'query' is required for action='recall'."

        elif action == "list_keys":
            if not self._storage:
                return "📭 No memories stored yet."
            keys = ", ".join(sorted(self._storage.keys()))
            return f"🔑 Available memory keys ({len(self._storage)}): {keys}"

        elif action == "list_all":
            if not self._storage:
                return "📭 No memories stored yet."
            items = []
            for k, v in sorted(self._storage.items()):
                # 预览长内容
                preview = (v[:60] + "...") if len(v) > 60 else v
                items.append(f"• {k}: {preview}")
            return "📚 All memories:\n" + "\n".join(items)

        else:
            return f"❌ Invalid action: '{action}'. Supported: store, recall, list_keys, list_all."


# === 工具注册 ===
ALL_TOOLS: List[BaseTool] = [
    ReadFileTool(),
    EditFileByLineTool(),
    MemoryTool(),
]

AI_ALL_TOOLS = [{"type": "function", "function": tool.to_dict()} for tool in ALL_TOOLS]


# === Agent ===
class ReActAgent:
    def __init__(self, model: str | None = None):
        self.model = model or OPENAI_MODEL
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=300.0,
        )
        self.messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful coding assistant with file access and long-term memory.\n"
                    "Before answering questions about user preferences, project details, or past facts, "
                    "ALWAYS check your memory first by calling the 'memory' tool with action='list_keys' or action='recall'.\n"
                    "If you don't know something, check memory before saying 'I don't know'."
                ),
            }
        ]

    def add_user_message(self, message: str):
        self.messages.append({"role": "user", "content": message})

    def add_assistant_message(self, content: str):
        message = {"role": "assistant", "content": content}
        self.messages.append(message)  # ← 修复：之前漏了 append！

    def add_tool_call_message(self, tool_call_id: str, tool_name: str, parameters: str):
        """parameters 应为 JSON 字符串"""
        self.messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tool_call_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": parameters},
                    }
                ],
            }
        )

    def add_tool_result_message(self, tool_call_id: str, tool_result: str):
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": tool_result,
            }
        )

    def execute_tool(self, tool_name: str, parameters_json: str) -> str:
        try:
            params = json.loads(parameters_json)
        except json.JSONDecodeError as e:
            return f"Invalid JSON parameters: {e}"

        for tool in ALL_TOOLS:
            if tool.name == tool_name:
                return tool.run(params)
        return f"Tool '{tool_name}' not found."

    def run(self, message: str) -> str:
        self.add_user_message(message)

        max_steps = 5  # 防止无限循环
        for _ in range(max_steps):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                tools=AI_ALL_TOOLS,
                tool_choice="auto",
            )
            msg = response.choices[0].message
            content = msg.content
            tool_calls = msg.tool_calls

            if tool_calls:
                for tool_call in tool_calls:
                    tool_id = tool_call.id
                    tool_name = tool_call.function.name
                    args_str = tool_call.function.arguments

                    self.add_tool_call_message(tool_id, tool_name, args_str)
                    logger.info(f"Executing tool: {tool_name} with args: {args_str}")

                    result = self.execute_tool(tool_name, args_str)
                    self.add_tool_result_message(tool_id, result)
                    logger.info(f"Tool result: {result}")

                    time.sleep(0.5)  # 避免 API 限流
                continue  # 继续调用模型（可能多轮工具调用）

            if content:
                self.add_assistant_message(content)
                print(f"\nAssistant: {content}")
                return content

        return "Agent stopped after maximum steps."


# === 主程序 ===
if __name__ == "__main__":

    agent = ReActAgent()
    while True:
        user_input = input("User: ")
        if user_input.lower() in ["quit", "exit"]:
            break
        agent.run(user_input)
