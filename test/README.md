# 工具测试说明

本目录包含所有重构后工具的测试文件。你可以逐个运行测试来验证每个工具的功能。

## 测试文件列表

1. **test_file_tools.py** - 文件操作工具测试
   - PrintTreeTool (print_tree)
   - ListFilesTool (list_files)
   - FileSearchTool (search)
   - OpenFileTool (open_file)
   - ReadFileTool (read_file)
   - WriteFileTool (write_file)
   - DiffTool (diff)
   - ChecksumTool (checksum)

2. **test_code_execution_tools.py** - 代码执行工具测试
   - CodeInterpreterTool (code_interpreter)
   - PythonTool (python)
   - RunTool (run)
   - ExecuteTool (execute)
   - ExecTool (exec)

3. **test_git_tools.py** - Git 操作工具测试
   - GitTool (git) - 包括 status, add, commit, log, branch, diff 等操作

4. **test_system_tools.py** - 系统命令工具测试
   - ShellTool (shell)
   - TerminalTool (terminal)
   - EnvTool (env)
   - SleepTool (sleep)

5. **test_network_tools.py** - 网络工具测试
   - BrowseTool (browse)
   - NetworkSearchTool (search)
   - DownloadTool (download)
   - UploadTool (upload)

6. **test_other_tools.py** - 其他工具测试
   - FileUploadTool (file_upload)
   - FileDownloadTool (file_download)
   - DalleTool (dall-e)
   - ZipTool (zip)
   - UnzipTool (unzip)

7. **test_all_tools.py** - 所有工具的综合测试（一次性运行所有测试）

## 运行测试

### 运行单个测试文件

```bash
# 文件操作工具测试
python test/test_file_tools.py

# 代码执行工具测试
python test/test_code_execution_tools.py

# Git 操作工具测试（需要安装 Git）
python test/test_git_tools.py

# 系统命令工具测试
python test/test_system_tools.py

# 网络工具测试
python test/test_network_tools.py

# 其他工具测试
python test/test_other_tools.py
```

### 运行所有测试

```bash
python test/test_all_tools.py
```

## 注意事项

1. **Git 工具测试**：需要系统安装 Git，部分测试可能会失败如果没有 Git
2. **网络工具测试**：部分工具是占位符实现，需要集成实际的 API
3. **系统命令工具测试**：某些命令在不同操作系统上可能不同（Windows vs Unix）
4. **测试环境**：每个测试都会创建临时目录，测试完成后会自动清理

## 测试结构

每个测试文件都包含：
- `setup_test_env()` - 设置测试环境（创建临时目录和测试文件）
- `cleanup_test_env()` - 清理测试环境（删除临时目录）
- 多个测试函数，每个函数测试一个工具的不同功能
- 清晰的输出，显示每个测试的结果

## 自定义测试

你可以修改测试文件来：
- 添加更多测试用例
- 测试特定的边界情况
- 验证错误处理
- 测试性能

每个测试函数都是独立的，你可以单独运行或修改它们。
