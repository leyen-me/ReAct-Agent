import os
import re
import json
from openai import OpenAI
from system_prompt import get_system_prompt

# ReAct
# Reasoning And Acting

# ======================== 基础配置 ========================
# model = "deepseek-ai/deepseek-v3.1-terminus"
model = "Pro/deepseek-ai/DeepSeek-V3.2"
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)

operating_system = "macOS"
work_dir = "/Users/apple/Desktop/project/agent/workspace"
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
        with open(parameters["path"], "r") as file:
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
        with open(parameters["path"], "w") as file:
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
            return os.listdir(parameters["path"])
        else:
            return f"目录{parameters['path']}不存在"


tools = [
    ReadFileTool(),
    WriteFileTool(),
    DeleteFileTool(),
    CreateFileTool(),
    RenameFileTool(),
    ListFilesTool(),
]

tools_dict = [tool.to_dict() for tool in tools]


def chat(task_message):
    system_prompt = get_system_prompt(tools_dict, operating_system, work_dir)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"<question>{task_message}</question>"},
    ]

    count = 0
    while True:
        count += 1

        if debug_mode:
            print(
                f"-------------------------------- {count} --------------------------------"
            )
            print(json.dumps(messages, indent=4, ensure_ascii=False))

        response = client.chat.completions.create(model=model, messages=messages)
        content = response.choices[0].message.content

        if "<thought>" in content:
            thought = re.search(r"<thought>(.*?)</thought>", content, re.DOTALL)
            thought = thought.group(1)
            print(f"💭 Thought: {thought}")
        if "<final_answer>" in content:
            final_answer = re.search(
                r"<final_answer>(.*?)</final_answer>", content, re.DOTALL
            )
            return final_answer.group(1)
        if "<action>" in content:
            action = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
            action = action.group(1)
            observation = None
            try:
                observation = eval(action)
            except Exception as e:
                observation = f"执行工具失败: {e}"
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {"role": "user", "content": f"<observation>{observation}</observation>"}
            )
            continue
        else:
            raise RuntimeError("模型未输出 <action> 或 <final_answer>")


# 写一个贪吃蛇游戏，使用 HTML、CSS、JavaScript 实现，代码分别放在不同的文件中
while True:
    task_message = input("请输入任务，输入 exit 退出: ")
    if task_message == "exit":
        break
    final_answer = chat(task_message)
    print(
        "-------------------------------- final_answer --------------------------------"
    )
    print(final_answer)
    print(
        "-------------------------------- final_answer --------------------------------"
    )
