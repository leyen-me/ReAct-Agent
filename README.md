# ReAct Agent

一个基于 ReAct（Reasoning and Acting）模式的智能代理实现，通过大语言模型进行推理和行动，能够自主完成复杂的文件操作、代码编辑和 Git 管理等任务。

## 📖 项目简介

ReAct Agent 是一个研究项目，旨在实现和探索 ReAct（推理与行动）模式。该模式结合了推理（Reasoning）和行动（Acting）两个关键组件，使 AI 代理能够：

- **思考（think）**：分析任务，制定计划
- **行动（Action）**：调用工具执行具体操作
- **观察（Observation）**：获取行动结果，调整策略

## ✨ 功能特性

- 🤔 **智能推理**：基于大语言模型进行任务分解和规划
- 🛠️ **丰富的工具集**：支持文件操作、代码搜索、命令执行、Git 管理、Todo List 管理等 24+ 种工具
- 🔄 **流式响应**：实时显示模型推理和输出过程
- 💬 **对话式交互**：支持多轮对话，持续完成任务
- 🔒 **安全机制**：路径验证，防止越权文件操作
- 📊 **上下文管理**：智能管理对话上下文，自动处理 token 限制
- 📝 **详细日志**：调试模式可查看完整的对话历史和 token 使用情况
- ✅ **任务管理**：内置类似 Cursor 的 todo-list 功能，支持任务跟踪和统计

## 🛠️ 可用工具

### 文件操作工具

| 工具名称 | 功能描述 |
|---------|---------|
| `ReadFileTool` | 读取文件内容 |
| `WriteFileTool` | 写入文件内容（全文替换） |
| `EditFileTool` | 编辑文件内容（部分替换，推荐使用） |
| `CreateFileTool` | 创建新文件 |
| `DeleteFileTool` | 删除文件 |
| `RenameFileTool` | 重命名文件 |
| `MoveFileTool` | 移动文件 |
| `CopyFileTool` | 复制文件 |
| `ListFilesTool` | 列出目录文件列表 |
| `CreateFolderTool` | 创建文件夹 |
| `DeleteFolderTool` | 删除文件夹 |

### 代码搜索工具

| 工具名称 | 功能描述 |
|---------|---------|
| `SearchInFilesTool` | 在文件中搜索文本内容 |
| `FindFilesTool` | 根据文件名模式查找文件 |

### 命令执行工具

| 工具名称 | 功能描述 |
|---------|---------|
| `RunCommandTool` | 执行系统命令（带超时保护） |

### Git 管理工具

| 工具名称 | 功能描述 |
|---------|---------|
| `GitStatusTool` | 查看 Git 仓库状态 |
| `GitDiffTool` | 查看文件差异 |
| `GitCommitTool` | 提交更改 |
| `GitBranchTool` | 管理 Git 分支 |
| `GitLogTool` | 查看提交历史 |

### Todo List 管理工具

| 工具名称 | 功能描述 |
|---------|---------|
| `AddTodoTool` | 添加新的 todo 项目 |
| `ListTodosTool` | 列出 todo 项目（支持状态筛选） |
| `UpdateTodoStatusTool` | 更新 todo 项目状态 |
| `DeleteTodoTool` | 删除 todo 项目 |
| `GetTodoStatsTool` | 获取 todo list 统计信息 |

## 📋 环境要求

- Python 3.7+
- OpenAI Python SDK（兼容 SiliconFlow API）

## 📦 分发方式

### 使用 GitHub Actions 自动打包（推荐）

项目配置了 GitHub Actions 工作流，可以自动为 Windows、macOS、Linux 三个平台打包二进制文件。

#### 触发打包

**方式一：推送版本标签（推荐）**
```bash
git tag v1.0.0
git push origin v1.0.0
```

**方式二：手动触发**
1. 在 GitHub 仓库页面，点击 "Actions" 标签
2. 选择 "Build Binaries" 工作流
3. 点击 "Run workflow"
4. 输入版本号（如 `1.0.0`），点击运行

#### 下载打包结果

打包完成后，有两种方式获取二进制文件：

1. **从 Artifacts 下载**：
   - 在 Actions 页面找到对应的运行记录
   - 点击进入详情页，在 Artifacts 部分下载对应平台的文件

2. **从 Releases 下载**（如果使用标签触发）：
   - 在 Releases 页面会自动创建 Release
   - 直接下载对应平台的可执行文件

#### 使用打包好的二进制文件

下载后，用户无需安装 Python 环境，直接运行：

**Linux/macOS:**
```bash
chmod +x ask-1.0.0
export OPENAI_API_KEY=your_api_key_here
./ask-1.0.0
```

**Windows:**
```cmd
set OPENAI_API_KEY=your_api_key_here
ask-1.0.0.exe
```

#### 自动更新

程序支持自动更新功能，可以通过以下命令管理更新：

**检查更新：**
```bash
ask --check-update
```

**执行更新：**
```bash
ask --update
```

**查看版本：**
```bash
ask --version
```

**帮助信息：**
```bash
ask --help
```

程序启动时会自动检查更新，如果有新版本会提示你。更新功能会自动：
- 从 GitHub Releases 获取最新版本
- 下载对应平台的二进制文件
- 备份当前版本
- 替换为最新版本

> **注意**：更新需要写入权限，可能需要管理员/root权限。更新前会自动备份当前版本到 `.backup` 文件。

### 本地打包（开发测试）

如果需要本地测试打包：

```bash
# 安装打包工具
pip install pyinstaller

# 打包
pyinstaller react_agent.spec --clean --noconfirm

# 二进制文件在 dist/ 目录
```

## 🚀 安装步骤（源码方式）

1. **克隆项目**
```bash
git clone <repository-url>
cd agent
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置环境变量**

必需的环境变量：
```bash
# Windows
set OPENAI_API_KEY=your_api_key_here

# Linux/macOS
export OPENAI_API_KEY=your_api_key_here
```

可选的环境变量：
```bash
# 模型名称（默认：Qwen/Qwen3-Next-80B-A3B-Instruct）
export MODEL=Qwen/Qwen3-Next-80B-A3B-Instruct

# API 基础 URL（默认：https://api.siliconflow.cn/v1）
export OPENAI_BASE_URL=https://api.siliconflow.cn/v1

# 操作系统（默认：macOS）
export OS=macOS

# 调试模式（默认：False）
export DEBUG=True

# 命令执行超时时间，单位：秒（默认：300）
export COMMAND_TIMEOUT=300

# 最大上下文 token 数（默认：根据模型自动设置）
export MAX_CONTEXT_TOKENS=128000

# 最大搜索结果数（默认：50）
export MAX_SEARCH_RESULTS=50

# 最大查找文件数（默认：100）
export MAX_FIND_FILES=100
```

## 💻 使用方法

1. **运行程序**
```bash
python main.py
```

或者使用命令行参数：

```bash
# 查看版本
python main.py --version

# 检查更新
python main.py --check-update

# 执行更新（仅二进制版本支持）
python main.py --update

# 查看帮助
python main.py --help
```

2. **输入任务**
程序启动后，会提示你输入任务。例如：
```
请输入任务，输入 exit 退出: 写一个贪吃蛇游戏，使用 HTML、CSS、JavaScript 实现，代码分别放在不同的文件中
```

3. **观察执行过程**
程序会实时显示：
- 模型的思考过程（`<think>`）
- 执行的行动（`<action>`）
- 工具返回的观察结果（`<observation>`）
- 最终答案（`<final_answer>`）
- 上下文使用情况（token 使用百分比和剩余数量）

4. **退出程序**
输入 `exit` 或使用 `Ctrl+C` 退出

## 📁 项目结构

```
agent/
├── __init__.py           # 包初始化文件
├── __main__.py           # 模块入口文件
├── main.py               # 主程序入口
├── agent.py              # ReAct Agent 核心逻辑
├── config.py             # 配置管理模块
├── logger_config.py      # 日志配置模块
├── tool_executor.py      # 工具执行器
├── utils.py              # 工具函数
├── react_agent.spec      # PyInstaller 打包配置
├── README.md             # 项目说明文档
├── requirements.txt      # 依赖包列表
├── target.md             # 目标文档（可选）
├── workspace/            # 工作目录（自动创建）
├── .github/               # GitHub 配置目录
│   └── workflows/        # GitHub Actions 工作流
│       └── build.yml     # 自动打包工作流
└── tools/                # 工具模块目录
    ├── __init__.py       # 工具模块导出
    ├── base.py           # 工具基类
    ├── file_tools.py     # 文件操作工具
    ├── command_tools.py  # 命令执行工具
    ├── search_tools.py   # 代码搜索工具
    └── git_tools.py      # Git 管理工具
```

## ✅ Todo List 功能

项目现在集成了类似 Cursor 的 todo-list 功能，可以管理任务列表。所有 todo 数据保存在工作目录的 `todos.json` 文件中。

### 主要特性

- **任务管理**：添加、查看、更新、删除 todo 项目
- **状态跟踪**：支持 pending、in_progress、completed、cancelled 四种状态
- **统计功能**：实时查看任务进度统计
- **持久化存储**：数据自动保存到 JSON 文件

### 使用示例

```bash
# 添加任务
ask "添加一个任务：实现用户认证功能"

# 查看所有任务
ask "列出所有待处理的任务"

# 更新任务状态
ask "将任务1标记为已完成"

# 查看统计信息
ask "显示任务进度统计"
```

详细使用说明请参考 [TODO_USAGE.md](TODO_USAGE.md)

## 🔧 配置说明

项目使用 `config.py` 进行统一配置管理，支持通过环境变量进行配置：

### 核心配置

- **模型配置**：通过 `MODEL` 环境变量设置，默认使用 `Qwen/Qwen3-Next-80B-A3B-Instruct`
- **API 配置**：通过 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL` 环境变量设置
- **工作目录**：默认使用项目根目录下的 `workspace` 文件夹，所有文件操作都限制在此目录内
- **调试模式**：通过 `DEBUG` 环境变量控制，启用后会显示详细的日志信息

### 高级配置

- **上下文管理**：自动根据模型设置最大上下文 token 数，支持通过 `MAX_CONTEXT_TOKENS` 手动设置
- **命令超时**：通过 `COMMAND_TIMEOUT` 设置命令执行超时时间（默认 300 秒）
- **搜索限制**：通过 `MAX_SEARCH_RESULTS` 和 `MAX_FIND_FILES` 限制搜索结果数量

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
- `<think>`：思考过程
- `<action>`：工具调用
- `<observation>`：工具返回结果
- `<final_answer>`：最终答案

### 上下文管理

- 自动跟踪 token 使用情况
- 当接近上下文限制时，自动删除最旧的消息（保留系统消息）
- 实时显示上下文使用百分比和剩余 token 数

## ⚠️ 注意事项

1. **API Key 安全**：请妥善保管你的 API Key，不要提交到代码仓库。建议使用 `.env` 文件或系统环境变量管理
2. **工作目录限制**：所有文件操作都限制在 `workspace` 目录下，确保安全性
3. **路径格式**：文件路径必须使用绝对路径，且必须在工作目录内
4. **错误处理**：如果工具执行失败，程序会显示错误信息并继续执行
5. **命令执行**：命令执行工具有超时保护，避免长时间阻塞
6. **文件编辑**：优先使用 `EditFileTool` 进行部分替换，而不是 `WriteFileTool` 全文替换，以保留文件的其他内容

## 🔍 示例输出

```
=== 流式输出开始 ===
<think>
用户要求创建一个贪吃蛇游戏，需要分别创建 HTML、CSS、JavaScript 文件。
我应该先创建目录结构，然后依次创建这三个文件。
</think>

<action>CreateFolderTool().run({'path': '/path/to/workspace/snake-game'})</action>
=== 流式输出结束 ===

=== Action ===
CreateFolderTool().run({'path': '/path/to/workspace/snake-game'})

=== Observation ===
文件夹 /path/to/workspace/snake-game 创建成功

...

=== Final Answer ===
我已经成功创建了贪吃蛇游戏的所有文件...

============================================================
[上下文使用: 15.3% (19,584/128,000 tokens) | 剩余: 108,416 tokens]
============================================================
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
