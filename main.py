import os
import re
import json
from openai import OpenAI, Stream
from openai.types.chat import ChatCompletionChunk

# ReAct
# Reasoning And Acting

# ======================== 基础配置 ========================
# model = "deepseek-ai/deepseek-v3.1-terminus"
# model = "Pro/deepseek-ai/DeepSeek-V3.2"
model = "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.siliconflow.cn/v1",
)

operating_system = "macOS"
work_dir = os.path.join(os.path.dirname(__file__), "workspace3")
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


class SummaryTool(Tool):
    def __init__(self):
        super().__init__()
        name = self.__class__.__name__
        description = "生成任务总结报告"
        parameters = {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "任务描述"},
                "process": {"type": "string", "description": "执行过程"},
                "result": {"type": "string", "description": "最终结果"},
                "reflection": {"type": "string", "description": "反思内容"},
            },
        }
        self.set_metadata(name, description, parameters)

    def run(self, parameters):
        # 生成总结报告
        summary_content = f"""# 任务总结报告

## 任务描述
{parameters['task']}

## 执行过程
{parameters['process']}

## 最终结果
{parameters['result']}

## 反思与改进
{parameters['reflection']}

## 生成时间
{os.path.basename(__file__)} 于 {os.path.dirname(__file__)}
"""
        
        # 生成文件名
        timestamp = re.sub(r'[^a-zA-Z0-9]', '_', parameters['task'][:50])
        filename = f"summary_{timestamp}.md"
        filepath = os.path.join(work_dir, filename)
        with open(filepath, "w", encoding="utf-8") as file:
            file.write(summary_content)
        
        return f"总结报告已生成: {filepath}"


tools = [
    ReadFileTool(),
    WriteFileTool(),
    DeleteFileTool(),
    CreateFileTool(),
    RenameFileTool(),
    ListFilesTool(),
    SummaryTool(),
]


def get_system_prompt(tools_dict, operating_system, work_dir):
    return f"""你需要解决一个问题。为此，你需要将问题分解为多个步骤。对于每个步骤，首先使用 <thought> 思考要做什么，然后使用可用工具之一决定一个 <action>。接着，你将根据你的行动从环境/工具中收到一个 <observation>。持续这个思考和行动的过程，直到你有足够的信息来提供 <final_answer>。

在提供最终答案后，你需要进行反思和总结：
1. 使用 <reflection> 标签进行任务反思
2. 使用 <summary> 标签生成总结报告

所有步骤请严格使用以下 XML 标签格式输出：
- <question> 用户问题
- <thought> 思考
- <action> 采取的工具操作
- <observation> 工具或环境返回的结果
- <final_answer> 最终答案
- <reflection> 任务反思
- <summary> 总结报告

⸻

例子 1:

<question>埃菲尔铁塔有多高？</question>
<thought>我需要找到埃菲尔铁塔的高度。可以使用搜索工具。</thought>
<action>GetHeightTool().run({{'query': '埃菲尔铁塔'}})</action>
<observation>埃菲尔铁塔的高度约为330米（包含天线）。</observation>
<thought>搜索结果显示了高度。我已经得到答案了。</thought>
<final_answer>埃菲尔铁塔的高度约为330米。</final_answer>
<reflection>这个任务比较简单直接，通过一次搜索就得到了准确答案。工具使用恰当，没有遇到困难。</reflection>
<summary>任务顺利完成，找到了埃菲尔铁塔的高度信息。</summary>

⸻

例子 2:

<question>帮我找一个简单的番茄炒蛋食谱，并看看家里的冰箱里有没有西红柿。</question>
<thought>这个任务分两步。第一步，找到番茄炒蛋的食谱。第二步，检查冰箱里是否有西红柿。我先用 FindRecipeTool().run 工具找食谱。</thought>
<action>FindRecipeTool().run({{'dish': '番茄炒蛋'}})</action>
<observation>简单的番茄炒蛋食谱：将2个鸡蛋打散，2个番茄切块。热油，先炒鸡蛋，盛出。再热油，炒番茄至软烂，加入鸡蛋，放盐调味即可。</observation>
<thought>好的，我已经有食谱了。食谱需要西红柿。现在我需要用 CheckFridgeTool().run 工具看看冰箱里有没有西红柿。</thought>
<action>CheckFridgeTool().run({{'item': '西红柿'}})</action>
<observation>冰箱检查结果：有3个西红柿。</observation>
<thought>我找到了食谱，并且确认了冰箱里有西红柿。可以回答问题了。</thought>
<final_answer>简单的番茄炒蛋食谱是：鸡蛋打散，番茄切块。先炒鸡蛋，再炒番茄，混合后加盐调味。冰箱里有3个西红柿。</final_answer>
<reflection>任务顺利完成，分两步执行很合理。食谱查找和冰箱检查都成功完成，信息完整。</reflection>
<summary>成功找到番茄炒蛋食谱并确认冰箱有西红柿，任务完成度100%。</summary>

⸻

请严格遵守：
- 你每次回答都必须包括两个标签，第一个是 <thought>，第二个是 <action> 或 <final_answer>
- 输出 <action> 后立即停止生成，等待真实的 <observation>，擅自生成 <observation> 将导致错误
- 多行参数请使用Python的三引号多行字符串来表示，如：<action>WriteFileTool().run({{'path': '{work_dir}/test.txt', 'content': \"\"\"xxx\"\"\"}})</action>
- 使用文件类型工具时，path 参数必须使用绝对路径，如：<action>WriteFileTool().run({{'path': '{work_dir}/test.txt', 'content': 'xxx'}})</action>
- 在 <final_answer> 后必须添加 <reflection> 和 <summary> 标签
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
    
    # 记录任务执行过程
    task_process = []
    task_result = ""
    
    while True:
        chat_count += 1
        if debug_mode:
            print(
                f"-------------------------------- {chat_count} --------------------------------"
            )
            print(json.dumps(messages, indent=4, ensure_ascii=False))
        
        # 使用流式响应
        stream_response: Stream[ChatCompletionChunk] = client.chat.completions.create(
            model=model, 
            messages=messages,
            stream=True
        )
        
        content = ""
        print("\n-------------------------------- 流式输出开始 --------------------------------")
        for chunk in stream_response:
            if chunk.choices[0].delta.reasoning_content:
                print(chunk.choices[0].delta.reasoning_content, end="", flush=True)
            if chunk.choices[0].delta.content:
                chunk_content = chunk.choices[0].delta.content
                content += chunk_content
                print(chunk_content, end="", flush=True)
        print("\n-------------------------------- 流式输出结束 --------------------------------\n")
        
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
                task_process.append(f"思考: {thought}")
                
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
                task_result = final_answer
                messages.append({"role": "assistant", "content": content})
                
                # 检查是否有反思和总结
                reflection = ""
                summary = ""
                
                if "<reflection>" in content:
                    reflection_match = re.search(r"<reflection>(.*?)</reflection>", content, re.DOTALL)
                    if reflection_match:
                        reflection = reflection_match.group(1)
                        print("-------------------------------- reflection --------------------------------")
                        print(f"reflection: {reflection}")
                        print("-------------------------------- reflection --------------------------------")
                
                if "<summary>" in content:
                    summary_match = re.search(r"<summary>(.*?)</summary>", content, re.DOTALL)
                    if summary_match:
                        summary = summary_match.group(1)
                        print("-------------------------------- summary --------------------------------")
                        print(f"summary: {summary}")
                        print("-------------------------------- summary --------------------------------")
                
                # 如果没有反思和总结，让模型补充
                if not reflection or not summary:
                    print("检测到缺少反思和总结，正在补充...")
                    messages.append({"role": "user", "content": "请补充 <reflection> 和 <summary> 标签"})
                    continue
                
                # 生成总结报告
                process_text = "\n".join(task_process)
                summary_tool = SummaryTool()
                summary_result = summary_tool.run({
                    "task": task_message,
                    "process": process_text,
                    "result": task_result,
                    "reflection": reflection
                })
                print(f"总结报告生成结果: {summary_result}")
                
                break
                
        if "<action>" in content:
            action = re.search(r"<action>(.*?)</action>", content, re.DOTALL)
            if action:
                action = action.group(1)
                observation = None
                try:
                    observation = eval(action)
                    task_process.append(f"操作: {action}")
                    task_process.append(f"结果: {observation}")
                except Exception as e:
                    observation = f"执行工具失败: {e}"
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {"role": "user", "content": f"<observation>{observation}</observation>"}
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


# 写一个贪吃蛇游戏，使用 HTML、CSS、JavaScript 实现，代码分别放在不同的文件中
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