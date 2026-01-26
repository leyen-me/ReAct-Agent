# 工具测试指南

## 快速开始

所有测试文件都在 `test/` 目录下，你可以逐个运行它们来测试每个工具模块。

## 测试文件

### 1. test_file_tools.py
测试所有文件操作工具：
- ✅ print_tree - 打印目录树
- ✅ list_files - 列出文件
- ✅ search - 文件内容搜索
- ✅ open_file - 打开文件（带行号范围）
- ✅ read_file - 读取文件（支持二进制）
- ✅ write_file - 写入文件（覆盖/追加）
- ✅ diff - 文件对比
- ✅ checksum - 文件哈希计算

**运行方式：**
```bash
python test/test_file_tools.py
```

### 2. test_code_execution_tools.py
测试所有代码执行工具：
- ✅ code_interpreter / python - Python 代码执行
- ✅ run / execute - 执行代码或命令
- ✅ exec - 执行命令

**运行方式：**
```bash
python test/test_code_execution_tools.py
```

### 3. test_git_tools.py
测试 Git 操作工具：
- ✅ git status - 查看状态
- ✅ git add - 添加文件
- ✅ git commit - 提交更改
- ✅ git log - 查看日志
- ✅ git branch - 分支操作
- ✅ git diff - 查看差异

**运行方式：**
```bash
python test/test_git_tools.py
```

**注意：** 需要系统安装 Git

### 4. test_system_tools.py
测试系统命令工具：
- ✅ shell - Shell 命令执行
- ✅ terminal - 受限命令执行
- ✅ env - 环境变量操作
- ✅ sleep - 暂停执行

**运行方式：**
```bash
python test/test_system_tools.py
```

### 5. test_network_tools.py
测试网络工具：
- ⚠️ browse / search - 网络搜索（占位符）
- ⚠️ download - 文件下载
- ⚠️ upload - 文件上传（占位符）

**运行方式：**
```bash
python test/test_network_tools.py
```

**注意：** 部分工具是占位符实现，需要集成实际的 API

### 6. test_other_tools.py
测试其他工具：
- ✅ file_upload - 文件上传（本地）
- ✅ file_download - 文件下载（本地）
- ⚠️ dall-e - DALL·E 图像生成（占位符）
- ✅ zip - 压缩文件/目录
- ✅ unzip - 解压文件

**运行方式：**
```bash
python test/test_other_tools.py
```

### 7. test_all_tools.py
运行所有测试的综合测试文件。

**运行方式：**
```bash
python test/test_all_tools.py
```

## 测试说明

### 测试环境
- 每个测试都会创建临时目录
- 测试完成后自动清理临时文件
- 不会影响项目文件

### 测试输出
- 每个测试都会输出清晰的测试结果
- 使用 `===` 分隔不同的测试部分
- 使用 `✓` 标记完成的测试

### 自定义测试
你可以：
1. 修改测试文件添加更多测试用例
2. 单独运行某个测试函数
3. 修改测试参数来测试边界情况

### 示例：单独运行某个测试

```python
# 在 Python 交互式环境中
from test.test_file_tools import test_write_file
test_write_file()
```

## 故障排除

### 导入错误
如果遇到导入错误，确保：
1. 在项目根目录运行测试
2. Python 路径包含项目根目录
3. 所有依赖已安装

### Git 测试失败
如果 Git 测试失败：
1. 确保系统安装了 Git
2. 检查 Git 是否在 PATH 中
3. 某些测试需要 Git 配置（会自动配置测试用户）

### 网络测试失败
网络工具测试可能失败，因为：
1. 部分工具是占位符实现
2. 需要实际的 API 密钥
3. 需要网络连接

## 测试覆盖

当前测试覆盖：
- ✅ 所有工具的基本功能
- ✅ 参数验证
- ✅ 错误处理
- ✅ 边界情况

可以添加的测试：
- 性能测试
- 并发测试
- 安全性测试
- 集成测试
