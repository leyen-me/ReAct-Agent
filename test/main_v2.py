"""单文件 Agent 实现（规范整理版）。

代码规范（后续 AI 修改本文件时必须遵守）：
1. 保持单文件架构，除非用户明确要求，否则不要拆分模块。
2. 允许重构表达方式，但禁止改变既有业务逻辑、状态流转和 prompt 语义。
3. 文件结构固定为：配置 -> 路径安全 -> 工具基类 -> 任务存储 -> 文件/命令工具 -> Agent 核心 -> 任务编排 -> 入口。
4. 所有路径输入都必须经过 `safe_resolve_path()` 校验，禁止绕过工作区边界。
5. 所有工具返回值都应复用 `BaseTool.success()` / `BaseTool.fail()` 的统一 JSON 结构。
6. 新增函数优先补充类型标注；关键类、关键函数需要有简短 docstring。
7. 注释只解释意图、边界和约束，不写重复代码字面意思的废话。
8. 保持依赖最小化；不要为了样式优化引入新的第三方库。
9. 修改时优先抽取小型辅助逻辑、统一命名和分段，不做跨语义的大改写。
10. 入口保持可直接运行，默认行为与原版保持一致。
"""

import fnmatch
import json
import logging
import os
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import OpenAI


# ==== 日志配置 ====

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


# ==== 运行时配置 ====

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("必须设置环境变量 OPENAI_API_KEY")

OPENAI_BASE_URL = "https://api.lkeap.cloud.tencent.com/coding/v3"
OPENAI_MODEL = "minimax-m2.5"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_WORKSPACE_DIR = Path.cwd().resolve()
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


# ==== Prompt 模板 ====

PLAN_AGENT_SYSTEM_PROMPT = """
<system>
  <role>
    你是任务规划 Agent（PlanAgent）。
    你负责理解用户需求、判断是否需要落地执行、拆分任务，并持续推动任务完成。
  </role>

  <primary_goal>
    在尽量少追问的前提下，生成清晰、可执行的任务列表，并把需要落地的请求推进到完成。
  </primary_goal>

  <hard_constraints>
    <rule>工作区根目录是 WORKSPACE_DIR，所有路径都应理解为相对于该目录，而不是脚本所在目录。</rule>
    <rule>你只能直接调用自己已注册的工具；不要假装拥有不存在的直接执行能力。</rule>
    <rule>当你不能直接修改文件或运行命令时，不要说“做不到”就停下；如果可以委派给 ExecuteAgent，就应推动任务继续。</rule>
    <rule>不要重复创建已存在的任务，不要反复规划同一件事。</rule>
  </hard_constraints>

  <available_tools>
    <tool>list_files</tool>
    <tool>search_code</tool>
    <tool>read_file_lines</tool>
    <tool>task_plan</tool>
    <tool>execute_next_task</tool>
  </available_tools>

  <decision_policy>
    <rule>如果用户只是寒暄、提问或闲聊，不要创建任务，直接回答即可。</rule>
    <rule>如果用户提出复杂需求，先使用工具查看项目结构、搜索相关代码、阅读必要文件，再决定如何拆分任务。</rule>
    <rule>如果请求需要真正落地，创建任务后应尽快调用 execute_next_task 开始执行，而不是停留在反复追问。</rule>
    <rule>如果用户明确表示“随便”“任意”“都行”“你决定”，说明用户已经授权你自行决定细节。对于低风险、低歧义、可安全落地的请求，应直接选择保守默认方案并执行。</rule>
  </decision_policy>

  <when_to_ask>
    <rule>只有在会覆盖已有重要文件、存在破坏性操作风险、或用户目标仍然无法安全执行时，才继续追问。</rule>
    <rule>如果低风险事项存在合理保守默认值，优先直接决策，而不是把选择权推回给用户。</rule>
  </when_to_ask>

  <tool_call_policy>
    <rule>先理解上下文，再规划任务；不要在没有任何检查的情况下直接规划复杂工作。</rule>
    <rule>调用 list_files 查看工作区根目录时，使用 "."，不要把 "WORKSPACE_DIR" 当作字面路径传给工具。</rule>
    <rule>当你确认要拆分任务时，只调用一次 task_plan。</rule>
    <rule>创建任务后，不要继续追加新的 task_plan；应转入执行和汇总，而不是重复规划。</rule>
  </tool_call_policy>

  <task_quality_rules>
    <rule>每个任务必须明确、可执行、粒度适中。</rule>
    <rule>任务描述应足够具体，让 ExecuteAgent 可以直接开始理解、修改、验证或运行命令。</rule>
    <rule>避免含糊任务，如“修复系统”“修改代码”。</rule>
  </task_quality_rules>

  <task_quality_examples>
    <good>查看 login.py 的实现</good>
    <good>搜索所有 login 相关代码</good>
    <good>修改 login.py 添加日志</good>
    <good>运行测试验证修改</good>
    <bad>修复系统</bad>
    <bad>修改代码</bad>
  </task_quality_examples>

  <execution_handoff>
    <rule>你可以在创建任务后调用 execute_next_task，把待办任务逐个交给 ExecuteAgent 执行。</rule>
    <rule>当 execute_next_task 返回还有待办任务时，继续调用 execute_next_task；当没有待办任务时，再向用户汇总最终结果。</rule>
    <rule>如果用户提到 replace_in_file、edit_by_lines、write_file、run_command 等执行类工具，或明确要求修改文件、运行命令、验证结果，不要仅因为你自己不能直接调用这些工具就说“没有这个工具”。应明确说明“我不能直接调用，但可以创建任务交给 ExecuteAgent 执行”，然后尽快使用 task_plan 和 execute_next_task 推动落地。</rule>
  </execution_handoff>

  <safe_defaults>
    <rule>即使工作区为空，也可以直接创建新文件；“工作区为空”不是拒绝执行的理由。</rule>
    <rule>创建简单示例文件时，默认放在工作区根目录。</rule>
    <rule>创建 Python 示例时，可默认命名为 example.py。</rule>
    <rule>文件内容应最小可用、可直接运行、便于用户理解。</rule>
  </safe_defaults>

  <output_contract>
    <rule>未开始规划时，不要假装已经执行过任务。</rule>
    <rule>任务仍在推进时，优先继续调用工具或执行下一步，而不是提前写大段总结。</rule>
    <rule>只有当没有待办任务时，才向用户做最终汇总。</rule>
  </output_contract>
</system>
"""

EXECUTE_AGENT_SYSTEM_PROMPT = """
<system>
  <role>
    你是任务执行 Agent（ExecuteAgent）。
    你负责消费单个任务、实际执行操作，并反馈最终结果。
  </role>

  <primary_goal>
    在不猜测、不偷懒、不虚构结果的前提下，尽最大可能把当前任务真实完成，并正确回写任务状态。
  </primary_goal>

  <continuity>
    <rule>同一轮用户请求中的多个任务属于同一个连续项目，你需要继承之前任务已经完成的工作，而不是把每个任务都当成全新项目。</rule>
  </continuity>

  <hard_constraints>
    <rule>所有文件路径和命令执行目录都限定在 WORKSPACE_DIR。</rule>
    <rule>不要假装读过未读文件、执行过未执行命令、验证过未验证结果。</rule>
    <rule>如果信息不足，先继续读取、搜索或检查，再执行修改。</rule>
    <rule>如果工具返回失败，不要假装成功；应根据现状重试、换策略，或如实失败。</rule>
  </hard_constraints>

  <task_input>
    <example>
任务：
修改 login.py 添加日志
    </example>
  </task_input>

  <available_tools>
    <code_understanding>
      <tool>list_files</tool>
      <tool>search_code</tool>
      <tool>read_file_lines</tool>
    </code_understanding>
    <code_editing>
      <tool>write_file</tool>
      <tool>replace_in_file</tool>
      <tool>edit_by_lines</tool>
    </code_editing>
    <system_operations>
      <tool>run_command</tool>
    </system_operations>
    <task_status>
      <tool>update_task</tool>
    </task_status>
  </available_tools>

  <execution_process>
    <step>先理解任务。</step>
    <step>再查看相关代码或环境。</step>
    <step>然后进行修改或执行命令。</step>
    <step>最后验证结果。</step>
  </execution_process>

  <tool_call_policy>
    <rule>尽量使用工具，而不是猜测代码或假设文件内容。</rule>
    <rule>先收集完成任务所需的最小必要上下文，再做修改；不要盲改。</rule>
    <rule>能验证就验证；如果无法验证，要在结果中明确说明未验证的原因。</rule>
  </tool_call_policy>

  <editing_strategy>
    <rule>如果需要修改代码，优先使用 replace_in_file 做唯一文本块替换；当你已经明确知道精确行区间时，使用 edit_by_lines；仅在需要新建文件或整体重写时使用 write_file。</rule>
    <rule>调用 replace_in_file 时，old_string 应包含足够的上下文，且必须保证在文件中唯一匹配；如果不唯一，应先继续读取更多上下文，再重试。</rule>
    <rule>调用 edit_by_lines 前，应先用 read_file_lines 确认目标行范围和当前内容，避免基于猜测修改。</rule>
    <rule>如果一种编辑策略失败，先分析失败原因，再选择更合适的下一种工具，而不是盲目重复同一步。</rule>
  </editing_strategy>

  <failure_handling>
    <rule>如果遇到缺少文件、命令失败、内容不匹配、权限受限等情况，应基于当前证据判断是否可继续推进。</rule>
    <rule>如果问题可通过补充读取、缩小范围、调整命令或更换编辑方式解决，应先继续尝试。</rule>
    <rule>只有在任务确实无法安全完成时，才将任务标记为 failed。</rule>
  </failure_handling>

  <completion_rules>
    <rule>当任务完成时，必须调用 update_task，并将 status 设为 "done"。</rule>
    <rule>如果任务失败，必须调用 update_task，并将 status 设为 "failed"。</rule>
    <rule>不要在未调用 update_task 的情况下就认为任务已经结束。</rule>
  </completion_rules>

  <output_contract>
    <rule>调用 update_task 后，提供简短清晰的执行结果，不要继续长篇发挥。</rule>
    <rule>结果应优先说明做了什么、是否验证、最终状态是什么。</rule>
    <rule>如果未验证成功，要明确说明未验证原因，而不是给出模糊总结。</rule>
  </output_contract>
</system>
"""

# ==== 路径安全 ====


def safe_resolve_path(user_path: str) -> Path:
    """将用户输入路径解析到工作区内，越界时直接拒绝。"""

    abs_path = (WORKSPACE_DIR / user_path).resolve()

    try:
        abs_path.relative_to(WORKSPACE_DIR)
    except ValueError:
        raise PermissionError("Path outside workspace")

    return abs_path


def to_workspace_relative(path: Path) -> str:
    """把绝对路径转换成相对工作区的显示路径。"""
    return str(path.resolve().relative_to(WORKSPACE_DIR))


IGNORED_PATH_PARTS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
}


def should_ignore_path(path: Path, root: Path) -> bool:
    """判断路径是否应被扫描流程忽略。"""
    try:
        rel = path.resolve().relative_to(root.resolve())
    except ValueError:
        rel = path.resolve().relative_to(WORKSPACE_DIR)
    return any(part in IGNORED_PATH_PARTS for part in rel.parts)


# ==== 工具基类 ====


class BaseTool:
    """所有工具的统一抽象基类。"""

    name: str = ""
    description: str = ""
    parameters: Dict[str, Any] = {}

    def run(self, parameters: Dict[str, Any]) -> str:
        raise NotImplementedError

    def success(self, data: Any) -> str:
        return json.dumps(
            {"success": True, "data": data, "error": None},
            ensure_ascii=False,
        )

    def fail(self, msg: str) -> str:
        return json.dumps(
            {"success": False, "data": None, "error": msg},
            ensure_ascii=False,
        )

    def to_dict(self) -> Dict[str, Any]:

        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class TaskRecord:
    """单个任务的持久化记录。"""
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
    """负责加载、保存和管理任务状态。"""
    def __init__(self, storage_path: Path = _TASK_FILE) -> None:
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

    def completed_tasks(self) -> List[Dict[str, Any]]:
        return [
            task.to_dict()
            for task in sorted(self._tasks.values(), key=lambda task: task.created_at)
            if task.status in {"done", "failed"}
        ]

    def has_active_tasks(self) -> bool:
        return any(task.status in {"pending", "running"} for task in self._tasks.values())

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


# ==== 文件导航工具 ====


class ListFilesTool(BaseTool):
    """列出工作区内目录或文件。"""

    name = "list_files"
    description = "List files in directory"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "depth": {"type": "integer"},
            "type": {"type": "string"},
            "glob": {"type": "string"},
            "limit": {"type": "integer"},
        },
    }

    def run(self, parameters: Dict[str, Any]) -> str:

        path = parameters.get("path", ".")
        depth = parameters.get("depth", 3)
        entry_type = parameters.get("type", "all")
        glob_pattern = parameters.get("glob")
        limit = parameters.get("limit", 200)

        try:

            root = safe_resolve_path(path)
            if not root.exists():
                return self.fail("path not found")

            if entry_type not in {"all", "file", "directory"}:
                return self.fail("type must be one of: all, file, directory")

            if limit < 1:
                return self.fail("limit must be >= 1")

            if root.is_file():
                item_type = "file"
                rel = root.relative_to(WORKSPACE_DIR)
                if entry_type not in {"all", "file"}:
                    return self.success([])
                if glob_pattern and not fnmatch.fnmatch(root.name, glob_pattern):
                    return self.success([])
                return self.success([{"path": str(rel), "type": item_type}])

            results = []

            for p in root.rglob("*"):
                if should_ignore_path(p, root):
                    continue

                rel = p.relative_to(WORKSPACE_DIR)
                rel_to_root = p.relative_to(root)

                if len(rel_to_root.parts) > depth:
                    continue

                item_type = "directory" if p.is_dir() else "file"

                if entry_type != "all" and item_type != entry_type:
                    continue

                if glob_pattern and not fnmatch.fnmatch(str(rel_to_root), glob_pattern):
                    continue

                results.append(
                    {
                        "path": str(rel),
                        "type": item_type,
                    }
                )

            results.sort(key=lambda item: (item["type"] != "directory", item["path"]))

            return self.success(results[:limit])

        except Exception as e:
            return self.fail(str(e))


# ==== 搜索工具 ====


class SearchCodeTool(BaseTool):
    """基于 ripgrep 在代码中查找关键字。"""

    name = "search_code"
    description = "Search keyword in codebase"

    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer"},
            "path": {"type": "string"},
            "glob": {"type": "string"},
            "regex": {"type": "boolean"},
            "case_sensitive": {"type": "boolean"},
        },
        "required": ["query"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:

        query = parameters["query"]
        max_results = parameters.get("max_results", 20)
        path = parameters.get("path", ".")
        glob_pattern = parameters.get("glob")
        regex = parameters.get("regex", False)
        case_sensitive = parameters.get("case_sensitive", True)

        try:
            if max_results < 1:
                return self.fail("max_results must be >= 1")

            target = safe_resolve_path(path)
            if not target.exists():
                return self.fail("path not found")

            command = ["rg", "--json", "--line-number", "--color", "never"]

            if not regex:
                command.append("--fixed-strings")

            if not case_sensitive:
                command.append("--ignore-case")

            if glob_pattern:
                command.extend(["--glob", glob_pattern])

            command.extend([query, str(target)])

            p = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=WORKSPACE_DIR,
                timeout=20,
            )

            if p.returncode not in {0, 1}:
                details = (p.stderr or p.stdout).strip() or "rg failed"
                return self.fail(f"search failed (exit {p.returncode}): {details}")

            results = []
            for line in p.stdout.splitlines():
                if not line.strip():
                    continue

                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if event.get("type") != "match":
                    continue

                data = event["data"]
                path_data = data.get("path") or {}
                lines_data = data.get("lines") or {}

                file_path = path_data.get("text")
                if not file_path:
                    continue

                snippet = (lines_data.get("text") or "").rstrip("\n")
                match_line = data.get("line_number")

                try:
                    file_path = str(Path(file_path).resolve().relative_to(WORKSPACE_DIR))
                except ValueError:
                    file_path = file_path

                results.append(
                    {
                        "file": file_path,
                        "line": match_line,
                        "snippet": snippet,
                    }
                )

                if len(results) >= max_results:
                    break

            return self.success(results)

        except subprocess.TimeoutExpired:
            return self.fail("search command timed out")
        except Exception as e:
            return self.fail(str(e))


# ==== 文件读取工具 ====


class ReadFileLinesTool(BaseTool):
    """按行读取文件内容。"""

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

    def run(self, parameters: Dict[str, Any]) -> str:

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


# ==== 文件写入工具 ====


class WriteFileTool(BaseTool):
    """整文件覆盖写入。"""

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

    def run(self, parameters: Dict[str, Any]) -> str:

        try:

            path = safe_resolve_path(parameters["path"])

            path.write_text(parameters["content"], encoding="utf-8")

            return self.success("written")

        except Exception as e:
            return self.fail(str(e))


# ==== 文件编辑工具 ====


class ReplaceInFileTool(BaseTool):
    """替换文件中的唯一文本块。"""

    name = "replace_in_file"
    description = "Replace a unique text block"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_string": {"type": "string"},
            "new_string": {"type": "string"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:

        try:

            path = safe_resolve_path(parameters["path"])
            old_string = parameters["old_string"]
            new_string = parameters["new_string"]

            if not old_string:
                return self.fail("old_string must not be empty")

            content = path.read_text(encoding="utf-8")
            match_count = content.count(old_string)

            if match_count == 0:
                return self.fail("old_string not found")

            if match_count > 1:
                return self.fail(
                    f"old_string is not unique (found {match_count} matches)"
                )

            updated = content.replace(old_string, new_string, 1)
            path.write_text(updated, encoding="utf-8")

            return self.success(
                {
                    "path": to_workspace_relative(path),
                    "replacements": 1,
                }
            )

        except Exception as e:
            return self.fail(str(e))


class EditByLinesTool(BaseTool):
    """按行号替换指定区间内容。"""

    name = "edit_by_lines"
    description = "Replace a line range"

    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
            "new_text": {"type": "string"},
        },
        "required": ["path", "start_line", "end_line", "new_text"],
    }

    def run(self, parameters: Dict[str, Any]) -> str:

        try:

            path = safe_resolve_path(parameters["path"])
            start_line = parameters["start_line"]
            end_line = parameters["end_line"]
            new_text = parameters["new_text"]

            if start_line < 1 or end_line < start_line:
                return self.fail("invalid line range")

            lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
            total_lines = len(lines)

            if end_line > total_lines:
                return self.fail(
                    f"line range out of bounds (file has {total_lines} lines)"
                )

            replacement_lines = new_text.splitlines(keepends=True)
            if new_text and not new_text.endswith(("\n", "\r")):
                replacement_lines.append("\n")

            updated_lines = (
                lines[: start_line - 1] + replacement_lines + lines[end_line:]
            )
            path.write_text("".join(updated_lines), encoding="utf-8")

            return self.success(
                {
                    "path": to_workspace_relative(path),
                    "start_line": start_line,
                    "end_line": end_line,
                    "new_line_count": len(replacement_lines),
                }
            )

        except Exception as e:
            return self.fail(str(e))


# ==== 命令执行工具 ====


class RunCommandTool(BaseTool):
    """在工作区内执行受限命令。"""

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

    def run(self, parameters: Dict[str, Any]) -> str:

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


class BaseAgent:
    """封装带工具调用能力的基础 Agent。"""
    def __init__(
        self,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        agent_name: str = "助手",
        temperature: float = 1,
        top_p: float = 0.95,
    ):
        self.model = model or OPENAI_MODEL
        self.agent_name = agent_name
        self.agent_color = INFO_COLOR
        self.temperature = temperature
        self.top_p = top_p
        self.client = OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=300.0,
        )
        self.tools: List[BaseTool] = []
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

    def get_tools(self) -> List[Dict[str, Any]]:
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

    def format_tool_result(self, result: str, max_len: int = 600) -> str:
        try:
            payload = json.loads(result)
        except Exception:
            text = result.strip()
        else:
            if isinstance(payload, dict) and "success" in payload:
                if payload.get("success"):
                    text = json.dumps(
                        {"success": True, "data": payload.get("data")},
                        ensure_ascii=False,
                    )
                else:
                    text = json.dumps(
                        {"success": False, "error": payload.get("error")},
                        ensure_ascii=False,
                    )
            else:
                text = json.dumps(payload, ensure_ascii=False)

        text = text.strip()
        if not text:
            return "<empty>"
        if len(text) <= max_len:
            return text
        return text[:max_len] + "...<truncated>"

    def reset_conversation(self) -> None:
        """将当前会话恢复到仅含 system prompt 的初始状态。"""
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
            "temperature": self.temperature,
            "top_p": self.top_p,
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
                    if not silent:
                        print(
                            f"【工具结果】{call['function']['name']} -> "
                            f"{self.format_tool_result(result)}",
                            flush=True,
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


# ==== Plan Agent ====

TASK_STATUS = ["pending", "running", "done", "failed"]


class TaskPlanTool(BaseTool):
    """向任务存储写入规划后的任务列表。"""
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

    def run(self, parameters: Dict[str, Any]) -> str:

        created = self.task_store.create_tasks(parameters["tasks"])
        return self.success(created)


class TaskUpdateTool(BaseTool):
    """更新任务执行状态和结果。"""
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

    def run(self, parameters: Dict[str, Any]) -> str:

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


def execute_single_task(exec_agent: "ExecuteAgent", task_store: TaskStore) -> Dict[str, Any]:
    """取出一个待执行任务，并交给 ExecuteAgent 处理。"""
    task = task_store.get_next_pending()
    if task is None:
        return {"executed": False, "task": None}

    task_store.update_task(task.id, "running")
    print(color_text(f"\n[执行中] {task.description}", EXECUTE_COLOR))

    previous_task_lines: List[str] = []
    for previous in task_store.completed_tasks():
        result = (previous.get("result") or "").strip()
        if len(result) > 200:
            result = result[:200] + "..."
        previous_task_lines.append(
            f"- [{previous['status']}] {previous['description']}"
            + (f" | 结果：{result}" if result else "")
        )

    previous_task_summary = "\n".join(previous_task_lines) or "无"

    task_prompt = (
        f"任务ID：{task.id}\n"
        f"任务描述：{task.description}\n\n"
        f"已完成任务摘要：\n{previous_task_summary}\n\n"
        "你正在延续同一个项目，请基于当前工作区现状和上述已完成任务继续执行，不要从零假设整个项目。\n"
        "执行完成后请调用 update_task 更新最终状态。调用后不要继续长篇总结。"
    )

    try:
        result = exec_agent.chat(
            task_prompt,
            silent=False,
            reset_history=False,
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
    """负责理解需求、拆解任务并驱动执行流程。"""
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
<system>
  <role>
    你是任务规划 Agent（PlanAgent）。
    你负责理解用户需求、判断是否需要落地执行、拆分任务，并持续推动任务完成。
  </role>

  <primary_goal>
    在尽量少追问的前提下，生成清晰、可执行的任务列表，并把需要落地的请求推进到完成。
  </primary_goal>

  <hard_constraints>
    <rule>工作区根目录是 WORKSPACE_DIR，所有路径都应理解为相对于该目录，而不是脚本所在目录。</rule>
    <rule>你只能直接调用自己已注册的工具；不要假装拥有不存在的直接执行能力。</rule>
    <rule>当你不能直接修改文件或运行命令时，不要说“做不到”就停下；如果可以委派给 ExecuteAgent，就应推动任务继续。</rule>
    <rule>不要重复创建已存在的任务，不要反复规划同一件事。</rule>
  </hard_constraints>

  <available_tools>
    <tool>list_files</tool>
    <tool>search_code</tool>
    <tool>read_file_lines</tool>
    <tool>task_plan</tool>
    <tool>execute_next_task</tool>
  </available_tools>

  <decision_policy>
    <rule>如果用户只是寒暄、提问或闲聊，不要创建任务，直接回答即可。</rule>
    <rule>如果用户提出复杂需求，先使用工具查看项目结构、搜索相关代码、阅读必要文件，再决定如何拆分任务。</rule>
    <rule>如果请求需要真正落地，创建任务后应尽快调用 execute_next_task 开始执行，而不是停留在反复追问。</rule>
    <rule>如果用户明确表示“随便”“任意”“都行”“你决定”，说明用户已经授权你自行决定细节。对于低风险、低歧义、可安全落地的请求，应直接选择保守默认方案并执行。</rule>
  </decision_policy>

  <when_to_ask>
    <rule>只有在会覆盖已有重要文件、存在破坏性操作风险、或用户目标仍然无法安全执行时，才继续追问。</rule>
    <rule>如果低风险事项存在合理保守默认值，优先直接决策，而不是把选择权推回给用户。</rule>
  </when_to_ask>

  <tool_call_policy>
    <rule>先理解上下文，再规划任务；不要在没有任何检查的情况下直接规划复杂工作。</rule>
    <rule>调用 list_files 查看工作区根目录时，使用 "."，不要把 "WORKSPACE_DIR" 当作字面路径传给工具。</rule>
    <rule>当你确认要拆分任务时，只调用一次 task_plan。</rule>
    <rule>创建任务后，不要继续追加新的 task_plan；应转入执行和汇总，而不是重复规划。</rule>
  </tool_call_policy>

  <task_quality_rules>
    <rule>每个任务必须明确、可执行、粒度适中。</rule>
    <rule>任务描述应足够具体，让 ExecuteAgent 可以直接开始理解、修改、验证或运行命令。</rule>
    <rule>避免含糊任务，如“修复系统”“修改代码”。</rule>
  </task_quality_rules>

  <task_quality_examples>
    <good>查看 login.py 的实现</good>
    <good>搜索所有 login 相关代码</good>
    <good>修改 login.py 添加日志</good>
    <good>运行测试验证修改</good>
    <bad>修复系统</bad>
    <bad>修改代码</bad>
  </task_quality_examples>

  <execution_handoff>
    <rule>你可以在创建任务后调用 execute_next_task，把待办任务逐个交给 ExecuteAgent 执行。</rule>
    <rule>当 execute_next_task 返回还有待办任务时，继续调用 execute_next_task；当没有待办任务时，再向用户汇总最终结果。</rule>
    <rule>如果用户提到 replace_in_file、edit_by_lines、write_file、run_command 等执行类工具，或明确要求修改文件、运行命令、验证结果，不要仅因为你自己不能直接调用这些工具就说“没有这个工具”。应明确说明“我不能直接调用，但可以创建任务交给 ExecuteAgent 执行”，然后尽快使用 task_plan 和 execute_next_task 推动落地。</rule>
  </execution_handoff>

  <safe_defaults>
    <rule>即使工作区为空，也可以直接创建新文件；“工作区为空”不是拒绝执行的理由。</rule>
    <rule>创建简单示例文件时，默认放在工作区根目录。</rule>
    <rule>创建 Python 示例时，可默认命名为 example.py。</rule>
    <rule>文件内容应最小可用、可直接运行、便于用户理解。</rule>
  </safe_defaults>

  <output_contract>
    <rule>未开始规划时，不要假装已经执行过任务。</rule>
    <rule>任务仍在推进时，优先继续调用工具或执行下一步，而不是提前写大段总结。</rule>
    <rule>只有当没有待办任务时，才向用户做最终汇总。</rule>
  </output_contract>
</system>
        """
        super().__init__(
            model,
            system_prompt,
            agent_name="PlanAgent",
            temperature=0.3,
            top_p=0.85,
        )
        self.agent_color = PLAN_COLOR
        self.task_store = task_store
        self.register_tool(ListFilesTool())
        self.register_tool(SearchCodeTool())
        self.register_tool(ReadFileLinesTool())
        self.register_tool(TaskPlanTool(task_store))


# ==== Execute Agent ====


class ExecuteAgent(BaseAgent):
    """负责消费单个任务并落地执行。"""
    def __init__(
        self,
        task_store: TaskStore,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ):
        system_prompt = system_prompt or """
<system>
  <role>
    你是任务执行 Agent（ExecuteAgent）。
    你负责消费单个任务、实际执行操作，并反馈最终结果。
  </role>

  <primary_goal>
    在不猜测、不偷懒、不虚构结果的前提下，尽最大可能把当前任务真实完成，并正确回写任务状态。
  </primary_goal>

  <continuity>
    <rule>同一轮用户请求中的多个任务属于同一个连续项目，你需要继承之前任务已经完成的工作，而不是把每个任务都当成全新项目。</rule>
  </continuity>

  <hard_constraints>
    <rule>所有文件路径和命令执行目录都限定在 WORKSPACE_DIR。</rule>
    <rule>不要假装读过未读文件、执行过未执行命令、验证过未验证结果。</rule>
    <rule>如果信息不足，先继续读取、搜索或检查，再执行修改。</rule>
    <rule>如果工具返回失败，不要假装成功；应根据现状重试、换策略，或如实失败。</rule>
  </hard_constraints>

  <task_input>
    <example>
任务：
修改 login.py 添加日志
    </example>
  </task_input>

  <available_tools>
    <code_understanding>
      <tool>list_files</tool>
      <tool>search_code</tool>
      <tool>read_file_lines</tool>
    </code_understanding>
    <code_editing>
      <tool>write_file</tool>
      <tool>replace_in_file</tool>
      <tool>edit_by_lines</tool>
    </code_editing>
    <system_operations>
      <tool>run_command</tool>
    </system_operations>
    <task_status>
      <tool>update_task</tool>
    </task_status>
  </available_tools>

  <execution_process>
    <step>先理解任务。</step>
    <step>再查看相关代码或环境。</step>
    <step>然后进行修改或执行命令。</step>
    <step>最后验证结果。</step>
  </execution_process>

  <tool_call_policy>
    <rule>尽量使用工具，而不是猜测代码或假设文件内容。</rule>
    <rule>先收集完成任务所需的最小必要上下文，再做修改；不要盲改。</rule>
    <rule>能验证就验证；如果无法验证，要在结果中明确说明未验证的原因。</rule>
  </tool_call_policy>

  <editing_strategy>
    <rule>如果需要修改代码，优先使用 replace_in_file 做唯一文本块替换；当你已经明确知道精确行区间时，使用 edit_by_lines；仅在需要新建文件或整体重写时使用 write_file。</rule>
    <rule>调用 replace_in_file 时，old_string 应包含足够的上下文，且必须保证在文件中唯一匹配；如果不唯一，应先继续读取更多上下文，再重试。</rule>
    <rule>调用 edit_by_lines 前，应先用 read_file_lines 确认目标行范围和当前内容，避免基于猜测修改。</rule>
    <rule>如果一种编辑策略失败，先分析失败原因，再选择更合适的下一种工具，而不是盲目重复同一步。</rule>
  </editing_strategy>

  <failure_handling>
    <rule>如果遇到缺少文件、命令失败、内容不匹配、权限受限等情况，应基于当前证据判断是否可继续推进。</rule>
    <rule>如果问题可通过补充读取、缩小范围、调整命令或更换编辑方式解决，应先继续尝试。</rule>
    <rule>只有在任务确实无法安全完成时，才将任务标记为 failed。</rule>
  </failure_handling>

  <completion_rules>
    <rule>当任务完成时，必须调用 update_task，并将 status 设为 "done"。</rule>
    <rule>如果任务失败，必须调用 update_task，并将 status 设为 "failed"。</rule>
    <rule>不要在未调用 update_task 的情况下就认为任务已经结束。</rule>
  </completion_rules>

  <output_contract>
    <rule>调用 update_task 后，提供简短清晰的执行结果，不要继续长篇发挥。</rule>
    <rule>结果应优先说明做了什么、是否验证、最终状态是什么。</rule>
    <rule>如果未验证成功，要明确说明未验证原因，而不是给出模糊总结。</rule>
  </output_contract>
</system>
        """
        super().__init__(
            model,
            system_prompt,
            agent_name="ExecuteAgent",
            temperature=0.6,
            top_p=0.9,
        )
        self.agent_color = EXECUTE_COLOR
        self.task_store = task_store
        self.register_tool(ListFilesTool())
        self.register_tool(SearchCodeTool())
        self.register_tool(ReadFileLinesTool())
        self.register_tool(WriteFileTool())
        self.register_tool(ReplaceInFileTool())
        self.register_tool(EditByLinesTool())
        self.register_tool(RunCommandTool())
        self.register_tool(TaskUpdateTool(task_store))


# ==== 任务分发工具 ====


class ExecuteNextTaskTool(BaseTool):
    """把下一个待办任务分发给 ExecuteAgent。"""
    def __init__(self, task_store: TaskStore, exec_agent: ExecuteAgent):
        self.task_store = task_store
        self.exec_agent = exec_agent

    name = "execute_next_task"
    description = "Dispatch next pending task to ExecuteAgent"
    parameters = {"type": "object", "properties": {}}

    def run(self, parameters: Dict[str, Any]) -> str:
        try:
            result = execute_single_task(self.exec_agent, self.task_store)
            return self.success(result)
        except Exception as e:
            return self.fail(str(e))


def print_task_summary(task_store: TaskStore) -> None:
    """打印当前任务列表的最终汇总。"""
    all_tasks = task_store.list_tasks()
    if not all_tasks:
        return

    print(f"\n{color_text('助手：任务执行完成，结果如下：', INFO_COLOR)}")
    for task in all_tasks:
        print(f"- [{task['status']}] {task['description']}")


def main() -> None:
    """启动交互式命令行入口。"""
    task_store = TaskStore()
    exec_agent = ExecuteAgent(task_store)
    plan_agent = PlanAgent(task_store)
    plan_agent.register_tool(ExecuteNextTaskTool(task_store, exec_agent))

    print(f"当前工作区：{WORKSPACE_DIR}")
    print(f"任务文件：{_TASK_FILE}")
    print("输入 /reset 可清空当前会话和任务状态")

    while True:
        user_input = input("用户：")
        if user_input in {"quit", "exit"}:
            break
        if user_input.strip() == "/reset":
            task_store.reset()
            exec_agent.reset_conversation()
            plan_agent.reset_conversation()
            print("已清空当前会话和任务状态")
            continue

        # 1. 规划任务
        plan_agent.chat(
            user_input,
            reset_history=False,
        )
        if not task_store.has_active_tasks():
            task_store.reset()
            exec_agent.reset_conversation()


if __name__ == "__main__":
    main()
