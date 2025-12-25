# -*- coding: utf-8 -*-

import os
import re
import json

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
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)

operating_system = "macOS"
work_dir = os.path.join(os.path.dirname(__file__), "workspace3")
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
        os.rename(parameters["path"], parameters["new_name"])
        if not os.path.exists(parameters["path"]):
            return f"文件{parameters['path']}不存在"
        else:
            os.rename(parameters["path"], parameters["new_name"])
            return f"文件{parameters['path']}重命名成功"

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


tools = [
    ReadFileTool(),
    WriteFileTool(),
    DeleteFileTool(),
    CreateFileTool(),
    RenameFileTool(),
    ListFilesTool(),
    CreateFolderTool(),
    EditFileTool(),
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
