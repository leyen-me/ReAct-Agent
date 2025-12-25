# -*- coding: utf-8 -*-

import os
import re
import json
import subprocess
import shutil
import glob
import fnmatch

from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk
from datetime import datetime

# ReAct
# Reasoning And Acting

# ========================= 任务描述 =========================
# 1. 写一个贪吃蛇游戏，使用 HTML、CSS、JavaScript 实现，代码分别放在不同的文件中


# ======================== 基础配置 ========================

model = "Qwen/Qwen3-235B-A22B-Instruct-2507"
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)

operating_system = "macOS"
work_dir = os.path.join(os.path.dirname(__file__), "workspace2")
work_dir = work_dir.replace('\\', '/') # 规范化路径，确保在 Windows 上使用正确的反斜杠
debug_mode = True


# ======================== 工具列表 ========================
class Tool:
    def __init__(self):
        pass

    def set_metadata(self, name, description, parameters):
        self.name = name
        self.description = description
        self.parameters = parameters

    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self, parameters):
        pass


class ReadFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "读取文件内容"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件路径"}},
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        with open(parameters["path"], "r", encoding="utf-8") as file:
            return file.read()


class WriteFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "写入文件内容"
        parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
        }
        self.set_metadata(name, description, parameters)

    # 参数校验，防止大模型恶意输入路径
    def validate_parameters(self, parameters):
        # 只能是 workspace 目录下的文件
        if not parameters["path"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"文件{parameters['path']}路径错误"
        with open(parameters["path"], "w", encoding="utf-8") as file:
            file.write(parameters["content"])
        return f"文件{parameters['path']}写入成功"


class DeleteFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "删除文件"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件路径"}},
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 只能是 workspace 目录下的文件
        if not parameters["path"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if os.path.exists(parameters["path"]):
            os.remove(parameters["path"])
            return f"文件{parameters['path']}删除成功"
        else:
            return f"文件{parameters['path']}不存在"


class CreateFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "创建文件"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件路径"}},
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 只能是 workspace 目录下的文件
        if not parameters["path"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"文件{parameters['path']}路径错误"
        if not os.path.exists(parameters["path"]):
            with open(parameters["path"], "w") as file:
                file.write("")
                return f"文件{parameters['path']}创建成功"
        else:
            return f"文件{parameters['path']}已存在"


class RenameFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "重命名文件"
        parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "new_name": {"type": "string", "description": "新文件名"},
            },
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 只能是 workspace 目录下的文件
        if not parameters["path"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"文件{parameters['path']}路径错误"
        
        if not os.path.exists(parameters["path"]):
            return f"文件{parameters['path']}不存在"
        
        # new_name 应该是完整路径
        new_path = parameters["new_name"]
        if not new_path.startswith(work_dir):
            # 如果 new_name 不是完整路径，则视为相对于原文件目录的新文件名
            dir_name = os.path.dirname(parameters["path"])
            new_path = os.path.join(dir_name, parameters["new_name"])
        
        if os.path.exists(new_path):
            return f"目标文件{new_path}已存在"
        
        try:
            os.rename(parameters["path"], new_path)
            return f"文件{parameters['path']}重命名成功为{new_path}"
        except Exception as e:
            return f"重命名文件失败: {e}"

class CreateFolderTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "创建文件夹"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件夹路径"}},
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        if not os.path.exists(parameters["path"]):
            os.makedirs(parameters["path"])
            return f"文件夹{parameters['path']}创建成功"
        else:
            return f"文件夹{parameters['path']}已存在"


class ListFilesTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "列出文件列表"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件夹路径"}},
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        if os.path.exists(parameters["path"]):
            return [os.path.join(parameters["path"], path) for path in os.listdir(path=parameters["path"])]
        else:
            return f"目录{parameters['path']}不存在"


class EditFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "编辑文件内容（部分替换），只替换匹配的文本部分，保留文件其他内容不变。这是推荐的文件编辑方式，类似于 Cursor 的部分替换功能。"
        parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "old_string": {"type": "string", "description": "要替换的原始文本（必须精确匹配，包括空格、换行等）"},
                "new_string": {"type": "string", "description": "替换后的新文本"},
                "replace_all": {"type": "boolean", "description": "是否替换所有匹配项（默认 false，只替换第一个匹配项）", "default": False},
            },
            "required": ["path", "old_string", "new_string"],
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 只能是 workspace 目录下的文件
        if not parameters["path"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"文件{parameters['path']}路径错误"
        
        if not os.path.exists(parameters["path"]):
            return f"文件{parameters['path']}不存在"
        
        try:
            # 读取原文件内容
            with open(parameters["path"], "r", encoding="utf-8") as file:
                content = file.read()
            
            old_string = parameters["old_string"]
            new_string = parameters["new_string"]
            replace_all = parameters.get("replace_all", False)
            
            # 检查 old_string 是否存在于文件中
            if old_string not in content:
                return f"错误：文件中未找到要替换的文本。请确保 old_string 与文件中的内容完全匹配（包括空格、换行、缩进等）。"
            
            # 执行替换
            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1
            
            # 写回文件
            with open(parameters["path"], "w", encoding="utf-8") as file:
                file.write(new_content)
            
            return f"文件{parameters['path']}编辑成功，已替换 {count} 处匹配的文本"
        except Exception as e:
            return f"编辑文件失败: {e}"


class RunCommandTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "执行终端命令（如 npm install, python -m pytest, git status 等）。命令会在工作目录下执行。"
        parameters = {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令（如 'npm install' 或 'python -m pytest'）"},
                "timeout": {"type": "integer", "description": "命令超时时间（秒），默认 300 秒", "default": 300},
            },
            "required": ["command"],
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        command = parameters["command"]
        timeout = parameters.get("timeout", 300)
        
        try:
            # 切换到工作目录执行命令
            result = subprocess.run(
                command,
                shell=True,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding="utf-8",
                errors="replace"
            )
            
            output = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
            
            if result.returncode == 0:
                return f"命令执行成功:\n标准输出:\n{result.stdout}\n标准错误:\n{result.stderr}"
            else:
                return f"命令执行失败（返回码: {result.returncode}）:\n标准输出:\n{result.stdout}\n标准错误:\n{result.stderr}"
        except subprocess.TimeoutExpired:
            return f"命令执行超时（超过 {timeout} 秒）"
        except Exception as e:
            return f"执行命令失败: {e}"


class SearchInFilesTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "在文件中搜索文本内容（支持正则表达式）。可以在指定目录下的所有文件中搜索，或仅在特定文件中搜索。"
        parameters = {
            "type": "object",
            "properties": {
                "search_text": {"type": "string", "description": "要搜索的文本（支持正则表达式）"},
                "directory": {"type": "string", "description": "要搜索的目录路径（默认工作目录）", "default": work_dir},
                "file_pattern": {"type": "string", "description": "文件匹配模式（如 '*.py', '*.js'），默认搜索所有文件"},
                "case_sensitive": {"type": "boolean", "description": "是否区分大小写（默认 false）", "default": False},
                "use_regex": {"type": "boolean", "description": "是否使用正则表达式（默认 false）", "default": False},
            },
            "required": ["search_text"],
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        search_text = parameters["search_text"]
        directory = parameters.get("directory", work_dir)
        file_pattern = parameters.get("file_pattern", "*")
        case_sensitive = parameters.get("case_sensitive", False)
        use_regex = parameters.get("use_regex", False)
        
        if not os.path.exists(directory):
            return f"目录{directory}不存在"
        
        results = []
        
        try:
            # 遍历目录下的所有文件
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if fnmatch.fnmatch(file, file_pattern):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()
                                for line_num, line in enumerate(lines, 1):
                                    matched = False
                                    if use_regex:
                                        flags = 0 if case_sensitive else re.IGNORECASE
                                        if re.search(search_text, line, flags):
                                            matched = True
                                    else:
                                        if case_sensitive:
                                            matched = search_text in line
                                        else:
                                            matched = search_text.lower() in line.lower()
                                    
                                    if matched:
                                        results.append({
                                            "file": file_path,
                                            "line": line_num,
                                            "content": line.strip()
                                        })
                        except Exception:
                            continue
            
            if results:
                result_str = f"找到 {len(results)} 处匹配:\n"
                for r in results[:50]:  # 限制返回前50个结果
                    result_str += f"{r['file']}:{r['line']}: {r['content']}\n"
                if len(results) > 50:
                    result_str += f"... 还有 {len(results) - 50} 处匹配未显示"
                return result_str
            else:
                return f"未找到匹配 '{search_text}' 的内容"
        except Exception as e:
            return f"搜索失败: {e}"


class FindFilesTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "按文件名模式搜索文件（支持通配符，如 '*.py', 'test*.js'）。"
        parameters = {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "文件名匹配模式（如 '*.py', 'test*.js', '**/config.json'）"},
                "directory": {"type": "string", "description": "要搜索的目录路径（默认工作目录）", "default": work_dir},
                "recursive": {"type": "boolean", "description": "是否递归搜索子目录（默认 true）", "default": True},
            },
            "required": ["pattern"],
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        pattern = parameters["pattern"]
        directory = parameters.get("directory", work_dir)
        recursive = parameters.get("recursive", True)
        
        if not os.path.exists(directory):
            return f"目录{directory}不存在"
        
        try:
            files = []
            if recursive:
                # 递归搜索
                for root, dirs, filenames in os.walk(directory):
                    for filename in filenames:
                        if fnmatch.fnmatch(filename, pattern):
                            files.append(os.path.join(root, filename))
            else:
                # 仅在当前目录搜索
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path) and fnmatch.fnmatch(filename, pattern):
                        files.append(file_path)
            
            if files:
                result_str = f"找到 {len(files)} 个匹配的文件:\n"
                for f in files[:100]:  # 限制返回前100个文件
                    result_str += f"{f}\n"
                if len(files) > 100:
                    result_str += f"... 还有 {len(files) - 100} 个文件未显示"
                return result_str
            else:
                return f"未找到匹配模式 '{pattern}' 的文件"
        except Exception as e:
            return f"搜索文件失败: {e}"


class DeleteFolderTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "删除文件夹及其所有内容（递归删除）"
        parameters = {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "文件夹路径"}},
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 只能是 workspace 目录下的文件夹
        if not parameters["path"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"文件夹{parameters['path']}路径错误"
        
        folder_path = parameters["path"]
        if not os.path.exists(folder_path):
            return f"文件夹{folder_path}不存在"
        
        if not os.path.isdir(folder_path):
            return f"{folder_path}不是文件夹"
        
        try:
            shutil.rmtree(folder_path)
            return f"文件夹{folder_path}删除成功"
        except Exception as e:
            return f"删除文件夹失败: {e}"


class MoveFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "移动文件或文件夹到新位置"
        parameters = {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 源和目标都必须在 workspace 目录下
        if not parameters["source"].startswith(work_dir) or not parameters["destination"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"路径错误：源和目标都必须在工作目录下"
        
        source = parameters["source"]
        destination = parameters["destination"]
        
        if not os.path.exists(source):
            return f"源路径{source}不存在"
        
        try:
            shutil.move(source, destination)
            return f"成功将{source}移动到{destination}"
        except Exception as e:
            return f"移动文件失败: {e}"


class CopyFileTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "复制文件或文件夹到新位置"
        parameters = {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        }
        self.set_metadata(name, description, parameters)

    def validate_parameters(self, parameters):
        # 源和目标都必须在 workspace 目录下
        if not parameters["source"].startswith(work_dir) or not parameters["destination"].startswith(work_dir):
            return False
        return True

    def run(self, parameters):
        if not self.validate_parameters(parameters):
            return f"路径错误：源和目标都必须在工作目录下"
        
        source = parameters["source"]
        destination = parameters["destination"]
        
        if not os.path.exists(source):
            return f"源路径{source}不存在"
        
        try:
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            return f"成功将{source}复制到{destination}"
        except Exception as e:
            return f"复制文件失败: {e}"


tools = [
    ReadFileTool(),
    WriteFileTool(),
    DeleteFileTool(),
    CreateFileTool(),
    RenameFileTool(),
    ListFilesTool(),
    CreateFolderTool(),
    EditFileTool(),
    RunCommandTool(),
    SearchInFilesTool(),
    FindFilesTool(),
    DeleteFolderTool(),
    MoveFileTool(),
    CopyFileTool(),
]


def get_system_prompt(tools_dict, operating_system, work_dir):
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
<action>ReadFileTool().run({{'path': '{work_dir}/script.js'}})</action>
<observation>function hello() {{}}</observation>
<thought>使用 EditFileTool 替换函数名。</thought>
<action>EditFileTool().run({{'path': '{work_dir}/script.js', 'old_string': 'function hello()', 'new_string': 'function greet()'}})</action>
<observation>文件{work_dir}/script.js编辑成功，已替换 1 处匹配的文本</observation>
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

<action>WriteFileTool().run({{'path': '{work_dir}/test.txt', 'content': 'xxx\\nxxx'}})</action>

<action>EditFileTool().run({{'path': '{work_dir}/test.py', 'old_string': 'def hello():\\n    print(\\\"old\\\")', 'new_string': 'def hello():\\n    print(\\\"new\\\")'}})</action>

⸻

本次任务可用工具：
{json.dumps(tools_dict, indent=4, ensure_ascii=False)}

⸻

环境信息：

操作系统：{operating_system}
工作目录：{work_dir}
"""


tools_dict = [tool.to_dict() for tool in tools]
chat_count = 0
system_prompt = get_system_prompt(tools_dict, operating_system, work_dir)
messages = [
    {"role": "system", "content": system_prompt},
]


def chat(task_message):
    global messages
    global chat_count
    messages.append({"role": "user", "content": f"<question>{task_message}</question>"})

    while True:
        chat_count += 1
        if debug_mode:
            print(
                f"-------------------------------- {chat_count} --------------------------------"
            )
            print(json.dumps(messages, indent=4, ensure_ascii=False))

        # 使用流式响应
        stream_response: Stream[ChatCompletionChunk] = client.chat.completions.create(
            model=model, messages=messages, stream=True
        )

        content = ""
        print(
            "\n-------------------------------- 流式输出开始 --------------------------------"
        )
        for chunk in stream_response:

            if chunk.choices[0].delta.reasoning_content:
                print(chunk.choices[0].delta.reasoning_content, end="", flush=True)

            if chunk.choices[0].delta.content:
                chunk_content = chunk.choices[0].delta.content
                content += chunk_content
                print(chunk_content, end="", flush=True)

        print(
            "\n-------------------------------- 流式输出结束 --------------------------------\n"
        )

        # 解析各个标签
        if "<thought>" in content:
            thought = re.search(r"<thought>(.*?)</thought>", content, re.DOTALL)
            if thought:
                thought = thought.group(1)
                print(
                    "-------------------------------- thought --------------------------------"
                )
                print(f"thought: {thought}")
                print(
                    "-------------------------------- thought --------------------------------"
                )

        if "<final_answer>" in content:
            final_answer = re.search(
                r"<final_answer>(.*?)</final_answer>", content, re.DOTALL
            )
            if final_answer:
                final_answer = final_answer.group(1)
                print(
                    "-------------------------------- final_answer --------------------------------"
                )
                print(f"final_answer: {final_answer}")
                print(
                    "-------------------------------- final_answer --------------------------------"
                )
                messages.append({"role": "assistant", "content": f"<final_answer>{final_answer}</final_answer>"})
                break
        # 检查是否有反思和总结
        reflection = ""
        if "<reflection>" in content:
            reflection_match = re.search(
                r"<reflection>(.*?)</reflection>", content, re.DOTALL
            )
            if reflection_match:
                reflection = reflection_match.group(1)
                print(
                    "-------------------------------- reflection --------------------------------"
                )
                print(f"reflection: {reflection}")
                print(
                    "-------------------------------- reflection --------------------------------"
                )
                break
        if "<action>" in content:
            action = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
            if action:
                action = action.group(1)
                observation = None
                try:
                    observation = eval(action)
                except Exception as e:
                    observation = f"执行工具失败: {e}"
                    print(
                        "-------------------------------- action error --------------------------------"
                    )
                    print(action)
                    print(
                        "-------------------------------- action error --------------------------------"
                    )
                messages.append({"role": "assistant", "content": f"<action>{action}</action>"})
                messages.append(
                    {
                        "role": "user",
                        "content": f"<observation>{observation}</observation>",
                    }
                )
                continue
        else:
            print(
                "-------------------------------- error --------------------------------"
            )
            print(content)
            print(
                "-------------------------------- error --------------------------------"
            )
            raise RuntimeError("模型未输出 <action> 或 <final_answer>")


if __name__ == "__main__":
    try:
        while True:
            task_message = input("请输入任务，输入 exit 退出: ")
            if task_message == "exit":
                break
            chat(task_message)
    except EOFError:
        print("\n程序结束")
    except KeyboardInterrupt:
        print("\n程序被用户中断")
