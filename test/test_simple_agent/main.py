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
    raise ValueError("必须设置环境变量 OPENAI_API_KEY")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://integrate.api.nvidia.com/v1  ")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")

# 沙箱根目录（防止路径遍历）
BASE_DIR = Path.cwd().resolve()


def safe_resolve_path(user_path: str) -> Path:
    """安全解析路径，限制在 BASE_DIR 内"""
    abs_path = (BASE_DIR / user_path).resolve()
    if not abs_path.is_relative_to(BASE_DIR):
        raise PermissionError(f"路径 {user_path} 超出了允许的目录范围：{BASE_DIR}")
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
            "按路径读取文件，可选指定行范围或分页读取。"
            "适用于大文件，避免上下文过载。"
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对文件路径"},
                "encoding": {
                    "type": "string",
                    "description": "文件编码",
                    "default": "utf-8",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从1开始，包含）。默认：1",
                    "default": 1,
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号（从1开始，包含）。若省略，则读取到文件末尾或达到 max_lines 限制。",
                },
                "max_lines": {
                    "type": "integer",
                    "description": "最多返回的行数（从 start_line 开始）。默认：100",
                    "default": 100,
                },
                "with_line_numbers": {
                    "type": "boolean",
                    "description": "在输出中包含行号（例如：'   1 | 内容'）",
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
                return f"文件未找到：{path}"
            if not abs_path.is_file():
                return f"不是文件：{path}"

            # 逐行读取，避免将整个大文件加载到内存中
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
                    return f"文件为空：{path}"
                else:
                    return f"指定范围内无内容 [{start_line}, ...]。文件共有 {total_lines} 行。"

            # 添加行号
            if with_line_numbers:
                start_num = start_line
                output_lines = [
                    f"{(start_num + i):4d} | {line}" for i, line in enumerate(lines)
                ]
            else:
                output_lines = lines

            result = "\n".join(output_lines)

            # 添加元信息（帮助 Agent 理解上下文）
            info = f"[文件: {path}, 第 {start_line}-{start_line + len(lines) - 1} 行 / 共 {total_lines} 行]"
            if len(lines) == max_lines and (
                not end_line or start_line + max_lines - 1 < end_line
            ):
                info += "（已截断，如需查看更多内容，请增大 end_line 或 max_lines）"

            return f"{info}\n{result}"

        except Exception as e:
            logger.error(f"ReadFileTool 错误：{e}")
            return f"读取文件时出错：{e}"


class EditFileByLineTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "edit_file_by_line"
        self.description = "通过行范围替换文件中的内容"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对文件路径"},
                "start_line": {
                    "type": "integer",
                    "description": "起始行（从1开始，包含）",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行（从1开始，包含）",
                },
                "new_string": {
                    "type": "string",
                    "description": "要插入的新内容（可包含 \\n）",
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
                return f"文件未找到：{path}"
            if not abs_path.is_file():
                return f"不是文件：{path}"

            with open(abs_path, "r", encoding="utf-8") as f:
                original_lines = f.readlines()

            total = len(original_lines)
            if not (1 <= start_line <= total and 1 <= end_line <= total):
                return f"行号超出范围。文件共有 {total} 行。"
            if start_line > end_line:
                return f"无效范围：起始行 ({start_line}) 大于结束行 ({end_line})"

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
            return f"成功替换文件 {path} 中第 {start_line}-{end_line} 行（共 {replaced_count} 行）。"

        except Exception as e:
            logger.error(f"EditFileByLineTool 错误：{e}")
            return f"编辑文件时出错：{e}"


class MemoryTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "memory"
        self.description = (
            "访问你的长期记忆，用于回忆用户偏好、项目事实或存储的键值。"
            "在回答有关过往交互或个人信息的问题前，务必先调用此工具。"
        )
        self.parameters = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["store", "recall", "list_keys", "list_all"],
                    "description": (
                        "'store'：保存一条事实；"
                        "'recall'：通过键或自然语言查询获取记忆；"
                        "'list_keys'：列出所有记忆键；"
                        "'list_all'：列出所有记忆（键 + 值预览）"
                    ),
                },
                "key": {
                    "type": "string",
                    "description": "记忆标识符（'store' 必填；'recall' 可选）",
                },
                "value": {
                    "type": "string",
                    "description": "要存储的事实（'store' 必填）",
                },
                "query": {
                    "type": "string",
                    "description": "用于查找相关记忆的自然语言查询（用于 'recall'）",
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
                logger.warning(f"从 {self._memory_path} 加载记忆失败：{e}")

    def _save(self):
        try:
            # 确保目录存在
            self._memory_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._memory_path, "w", encoding="utf-8") as f:
                json.dump(self._storage, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆到 {self._memory_path} 失败：{e}")

    def run(self, parameters: Dict[str, Any]) -> str:
        action = parameters.get("action")

        if action == "store":
            key = parameters.get("key")
            value = parameters.get("value")
            if not key or value is None:
                return "错误：执行 'store' 操作时，'key' 和 'value' 为必填项。"
            self._storage[str(key)] = str(value)
            self._save()
            return f"✅ 已存储记忆：'{key}' = '{value}'"

        elif action == "recall":
            key = parameters.get("key")
            query = parameters.get("query")

            if key:
                # 精确键查找
                if key in self._storage:
                    return f"📌 通过键 '{key}' 回忆：{self._storage[key]}"
                else:
                    return f"❌ 未找到键为 '{key}' 的记忆"

            elif query:
                # 简单模糊匹配：检查键或值是否包含查询词（不区分大小写）
                query_lower = str(query).lower()
                matches = []
                for k, v in self._storage.items():
                    if query_lower in k.lower() or query_lower in v.lower():
                        matches.append(f"{k}: {v}")
                if matches:
                    return "🔍 相关记忆：\n" + "\n".join(matches)
                else:
                    return "❌ 未找到与查询 '{}' 相关的记忆".format(query)

            else:
                return "错误：执行 'recall' 操作时，需提供 'key' 或 'query'。"

        elif action == "list_keys":
            if not self._storage:
                return "📭 尚未存储任何记忆。"
            keys = ", ".join(sorted(self._storage.keys()))
            return f"🔑 可用的记忆键（共 {len(self._storage)} 个）：{keys}"

        elif action == "list_all":
            if not self._storage:
                return "📭 尚未存储任何记忆。"
            items = []
            for k, v in sorted(self._storage.items()):
                # 预览长内容
                preview = (v[:60] + "...") if len(v) > 60 else v
                items.append(f"• {k}: {preview}")
            return "📚 所有记忆：\n" + "\n".join(items)

        else:
            return f"❌ 无效操作：'{action}'。支持的操作：store, recall, list_keys, list_all."


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
                    "你是一个有用的编程助手，具备文件访问和长期记忆能力。\n"
                    "在回答有关用户偏好、项目细节或历史事实的问题前，"
                    "务必先通过调用 'memory' 工具（使用 action='list_keys' 或 action='recall'）检查你的记忆。\n"
                    "如果你不知道某件事，请先检查记忆，再不要直接说“我不知道”。"
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
            return f"参数 JSON 格式无效：{e}"

        for tool in ALL_TOOLS:
            if tool.name == tool_name:
                return tool.run(params)
        return f"未找到工具：'{tool_name}'"

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
                    logger.info(f"正在执行工具：{tool_name}，参数：{args_str}")

                    result = self.execute_tool(tool_name, args_str)
                    self.add_tool_result_message(tool_id, result)
                    logger.info(f"工具执行结果：{result}")

                    time.sleep(0.5)  # 避免 API 限流
                continue  # 继续调用模型（可能多轮工具调用）

            if content:
                self.add_assistant_message(content)
                print(f"\n助手：{content}")
                return content

        return "代理在达到最大步骤数后停止。"


# === 主程序 ===
if __name__ == "__main__":

    agent = ReActAgent()
    while True:
        user_input = input("用户：")
        if user_input.lower() in ["quit", "exit"]:
            break
        agent.run(user_input)
