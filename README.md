# ReAct Agent

一个基于 ReAct（Reasoning and Acting）模式的智能代理实现，通过大语言模型进行推理和行动，能够自主完成复杂的文件操作任务。

## 📖 项目简介

ReAct Agent 是一个研究项目，旨在实现和探索 ReAct（推理与行动）模式。该模式结合了推理（Reasoning）和行动（Acting）两个关键组件，使 AI 代理能够：

- **思考（Thought）**：分析任务，制定计划
- **行动（Action）**：调用工具执行具体操作
- **观察（Observation）**：获取行动结果，调整策略
- **反思（Reflection）**：完成任务后进行总结和反思

## ✨ 功能特性

- 🤔 **智能推理**：基于大语言模型进行任务分解和规划
- 🛠️ **工具调用**：支持多种文件操作工具（读取、写入、创建、删除等）
- 🔄 **流式响应**：实时显示模型推理和输出过程
- 💬 **对话式交互**：支持多轮对话，持续完成任务
- 🔒 **安全机制**：路径验证，防止越权文件操作
- 📝 **详细日志**：调试模式可查看完整的对话历史

## 🛠️ 可用工具

| 工具名称 | 功能描述 |
|---------|---------|
| `ReadFileTool` | 读取文件内容 |
| `WriteFileTool` | 写入文件内容 |
| `CreateFileTool` | 创建新文件 |
| `DeleteFileTool` | 删除文件 |
| `RenameFileTool` | 重命名文件 |
| `CreateFolderTool` | 创建文件夹 |
| `ListFilesTool` | 列出目录文件列表 |

## 📋 环境要求

- Python 3.7+
- OpenAI Python SDK（兼容 SiliconFlow API）

## 🚀 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd ReAct-Agent
```

2. **安装依赖**
```bash
pip install openai
```

3. **配置 API Key**
```bash
# Windows
set SILICONFLOW_API_KEY=your_api_key_here

# Linux/macOS
export SILICONFLOW_API_KEY=your_api_key_here
```

## 💻 使用方法

1. **运行程序**
```bash
python main.py
```

2. **输入任务**
程序启动后，会提示你输入任务。例如：
```
请输入任务，输入 exit 退出: 写一个贪吃蛇游戏，使用 HTML、CSS、JavaScript 实现，代码分别放在不同的文件中
```

3. **观察执行过程**
程序会实时显示：
- 模型的思考过程（`<thought>`）
- 执行的行动（`<action>`）
- 工具返回的观察结果（`<observation>`）
- 最终答案（`<final_answer>`）
- 任务反思（`<reflection>`）

4. **退出程序**
输入 `exit` 或使用 `Ctrl+C` 退出

## 📁 项目结构

```
ReAct-Agent/
├── main.py              # 主程序文件
├── README.md            # 项目说明文档
├── workspace/           # 工作目录（示例）
└── workspace3/          # 主要工作目录
    └── snake-game/      # 示例项目目录
        ├── index.html
        ├── script.js
        └── style.css
```

## 🔧 配置说明

在 `main.py` 中可以修改以下配置：

```python
# 模型配置
model = "Qwen/Qwen3-235B-A22B-Instruct-2507"

# API 配置（通过环境变量）
api_key = os.getenv("SILICONFLOW_API_KEY")
base_url = "https://api.siliconflow.cn/v1"

# 工作目录
work_dir = os.path.join(os.path.dirname(__file__), "workspace3")

# 调试模式
debug_mode = True  # 设置为 False 可关闭详细日志
```

## 🧠 工作原理

### ReAct 循环

1. **接收问题**：用户输入任务描述
2. **思考阶段**：模型分析任务，制定执行计划
3. **行动阶段**：调用合适的工具执行操作
4. **观察阶段**：获取工具执行结果
5. **迭代循环**：根据观察结果继续思考-行动-观察，直到任务完成
6. **最终答案**：输出任务完成结果
7. **反思总结**：对复杂任务进行反思和总结

### XML 标签格式

程序使用 XML 标签来结构化输出：

- `<question>`：用户问题
- `<thought>`：思考过程
- `<action>`：工具调用
- `<observation>`：工具返回结果
- `<final_answer>`：最终答案
- `<reflection>`：任务反思

## ⚠️ 注意事项

1. **API Key 安全**：请妥善保管你的 API Key，不要提交到代码仓库
2. **工作目录限制**：所有文件操作都限制在 `workspace3` 目录下，确保安全性
3. **路径格式**：文件路径必须使用绝对路径，且必须在工作目录内
4. **错误处理**：如果工具执行失败，程序会显示错误信息并继续执行

## 🔍 示例输出

```
-------------------------------- thought --------------------------------
thought: 用户要求创建一个贪吃蛇游戏，需要分别创建 HTML、CSS、JavaScript 文件。我应该先创建目录结构，然后依次创建这三个文件。
-------------------------------- thought --------------------------------

-------------------------------- action --------------------------------
CreateFolderTool().run({'path': 'workspace3/snake-game'})
-------------------------------- action --------------------------------

-------------------------------- observation --------------------------------
文件夹workspace3/snake-game创建成功
-------------------------------- observation --------------------------------

...

-------------------------------- final_answer --------------------------------
final_answer: 我已经成功创建了贪吃蛇游戏的所有文件...
-------------------------------- final_answer --------------------------------

-------------------------------- reflection --------------------------------
reflection: 任务顺利完成，按照计划创建了三个文件...
-------------------------------- reflection --------------------------------
```

## 📚 相关资源

- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [SiliconFlow 文档](https://siliconflow.cn/)
- [OpenAI Python SDK](https://github.com/openai/openai-python)

## 📄 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

**注意**：本项目主要用于研究 ReAct Agent 的实现原理和应用场景。在生产环境中使用前，请确保充分测试和评估安全性。

