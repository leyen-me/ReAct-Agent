# 工具使用文档

本文档列出了当前环境中可用的所有工具及其使用方法。

## 目录
- [文件操作工具](#文件操作工具)
- [代码执行工具](#代码执行工具)
- [Git 操作工具](#git-操作工具)
- [系统命令工具](#系统命令工具)
- [网络工具](#网络工具)
- [其他工具](#其他工具)

---

## 文件操作工具

### print_tree
**功能描述**：递归打印指定目录（或仓库根目录）的文件树结构，帮助快速了解项目结构。

**参数**：
- `path`（可选）：要打印的根目录路径，默认是工作区根目录 `.`
- `depth`（可选）：递归深度，`0` 表示只显示根目录本身，`null` 或省略表示无限深度
- `ignore`（可选）：要忽略的文件/目录模式列表，如 `["*.pyc", "__pycache__"]`

**示例**：
```json
{"path": "src", "depth": 2}
{"path": ".", "depth": 3, "ignore": ["*.pyc", "__pycache__"]}
```

---

### list_files
**功能描述**：列出指定目录下的文件（支持递归）。

**参数**：
- `path`（必填）：要列出的目录路径
- `pattern`（可选）：glob 模式，如 `"*.js"`
- `recursive`（可选，布尔值）：是否递归列出子目录，默认 `false`

**示例**：
```json
{"path": "tests"}
{"path": "src", "pattern": "*.py", "recursive": true}
```

**返回值**：文件路径列表（字符串数组）

---

### search
**功能描述**：在代码库或文档中全文搜索关键字或正则表达式，返回匹配的文件路径和摘要。

**参数**：
- `query`（必填）：要搜索的字符串或正则表达式（支持 `re` 语法）
- `path`（可选）：搜索起始目录，默认是根目录 `.`
- `regex`（可选，布尔值）：是否使用正则表达式，默认 `false`
- `max_results`（可选）：返回的最大匹配数，默认 100，设为 `null` 表示不限制

**示例**：
```json
{"query": "TODO", "path": "src"}
{"query": "def .*print", "path": "src", "regex": true, "max_results": 20}
```

**返回值**：匹配项列表，每项包含文件路径、行号、匹配行内容

---

### open_file
**功能描述**：打开并读取指定文件的内容（最多 20 KB），返回纯文本。

**参数**：
- `path`（必填）：相对于工作区根目录的文件路径
- `line_start`（可选）：只返回从该行开始的内容，默认 `1`（文件开头）
- `line_end`（可选）：只返回到该行结束，默认返回到文件末尾或 20 KB 限制

**示例**：
```json
{"path": "src/main.py", "line_start": 1, "line_end": 200}
{"path": "README.md", "line_start": 1, "line_end": 50}
```

**返回值**：文件内容（字符串）

---

### read_file
**功能描述**：读取文件的完整内容，常用于后续处理。与 `open_file` 类似，但专注于读取操作，支持二进制读取。

**参数**：
- `path`（必填）：文件路径
- `binary`（可选，布尔值）：是否以二进制模式读取，默认 `false`
- `encoding`（可选）：文件编码，默认 `"utf-8"`

**示例**：
```json
{"path": "README.md"}
{"path": "image.png", "binary": true}
```

**返回值**：若 `binary=False` 返回字符串；若 `True` 返回 `bytes`（可 base64 编码后返回）

---

### write_file
**功能描述**：向指定文件写入内容（覆盖或追加），可用于创建新文件或修改已有文件。

**参数**：
- `path`（必填）：文件路径
- `content`（必填）：要写入的内容
- `append`（可选，布尔值）：是否追加模式，默认 `false`（覆盖模式）
- `mode`（可选）：写入模式，`"w"` 覆盖、`"a"` 追加，默认 `"w"`
- `encoding`（可选）：文件编码，默认 `"utf-8"`

**示例**：
```json
{"path": "src/utils.py", "content": "# 新增函数\ndef foo():\n    pass", "append": false}
{"path": "log.txt", "content": "New log line\n", "mode": "a"}
```

**返回值**：成功返回 `True`，异常抛出错误信息

---

### diff
**功能描述**：对比两个文件或目录，返回统一 diff 格式。

**参数**：
- `path_a`（必填）：第一个文件或目录路径
- `path_b`（必填）：第二个文件或目录路径
- `ignore_whitespace`（可选，布尔值）：是否忽略空白字符差异

**示例**：
```json
{"path_a": "/project/v1.py", "path_b": "/project/v2.py"}
```

**返回值**：diff 文本字符串

---

### checksum
**功能描述**：计算文件的哈希值（MD5、SHA1、SHA256 等）。

**参数**：
- `path`（必填）：文件路径
- `algorithm`（可选）：哈希算法，可选 `"md5"`、`"sha1"`、`"sha256"`，默认 `"sha256"`

**示例**：
```json
{"path": "/project/package.tar.gz", "algorithm": "md5"}
```

**返回值**：哈希十六进制字符串

---

## 代码执行工具

### code_interpreter / python
**功能描述**：在受限的 Python 环境中执行代码，支持读取/写入文件、绘图、数据分析等。

**参数**：
- `code`（必填）：要执行的 Python 代码
- `timeout`（可选）：超时时间（秒），默认 5
- `globals`（可选，字典）：全局变量字典
- `locals`（可选，字典）：局部变量字典

**示例**：
```json
{"code": "print('Hello, world!')"}
{"code": "sum([i*i for i in range(10)])", "timeout": 5}
```

**返回值**：`{ "result": 结果值, "stdout": "标准输出", "stderr": "错误输出", "exception": null }`

**典型使用场景**：处理数据、生成图表、运行算法、快速原型验证

---

### run / execute
**功能描述**：在受控的沙箱环境中执行一段 Python 代码或脚本，返回标准输出、错误信息和返回码。

**参数**：
- `code`（必填）：要执行的代码
- `cmd`（可选）：shell 命令（如果使用 shell 模式）
- `timeout`（可选）：超时时间（秒）
- `env`（可选，字典）：环境变量
- `cwd`（可选）：工作目录

**示例**：
```json
{"code": "print('Hello, world!')"}
{"cmd": "python - <<'PY'\nprint('hi')\nPY", "timeout": 10}
```

**返回值**：`{ "stdout": "标准输出", "stderr": "错误输出", "returncode": 0 }`

---

### exec
**功能描述**：与 `run` 类似，但默认在当前工作目录下执行，常用于一次性脚本。

**参数**：
- `command`（必填）：要执行的命令
- `input`（可选）：传递给 stdin 的输入
- `timeout`（可选）：超时时间（秒）

**示例**：
```json
{"command": "cat /etc/hosts"}
```

**返回值**：同 `run`

---

## Git 操作工具

### git
**功能描述**：对仓库执行 Git 操作，如 `clone`、`checkout`、`pull`、`commit`、`status`、`log` 等。

**参数**：
- `action`（必填）：Git 操作类型，如 `"clone"`、`"pull"`、`"status"`、`"log"` 等
- `args`（可选，列表）：操作参数列表
- `repo_path`（可选）：仓库路径，默认当前工作目录
- `remote`（可选）：远程仓库名称，如 `"origin"`
- `branch`（可选）：分支名称，如 `"main"`
- `timeout`（可选）：超时时间（秒）

**示例**：
```json
{"action": "pull", "remote": "origin", "branch": "main"}
{"action": "clone", "args": ["https://github.com/user/repo.git", "repo"], "repo_path": "/tmp"}
{"action": "status"}
```

**返回值**：根据 `action` 返回对应的 stdout / stderr / returncode

---

## 系统命令工具

### shell
**功能描述**：执行任意系统 Shell 命令（受限于安全策略），常用于查看文件、安装依赖等。支持交互式会话（保持同一进程），适合多步操作。

**参数**：
- `cmd`（必填）：要执行的 shell 命令
- `session_id`（可选）：会话标识符，用于保持同一进程
- `timeout`（可选）：超时时间（秒）

**示例**：
```json
{"cmd": "git status"}
{"cmd": "ls -la", "session_id": "sess-123"}
```

**返回值**：同 `run`，但后续调用同 `session_id` 时会在同一进程中继续执行

**典型使用场景**：检查文件、查看日志、执行脚本（受限）

---

### terminal
**功能描述**：执行简单的系统命令（受限的 shell），如 `ls`、`cat`、`grep` 等。

**参数**：
- `cmd`（必填）：要执行的命令

**示例**：
```json
{"cmd": "ls -la"}
```

**典型使用场景**：检查文件、查看日志、执行脚本（受限）

---

### env
**功能描述**：查询或修改当前进程的环境变量。

**参数**：
- `action`（必填）：操作类型，`"get"`/`"set"`/`"unset"`
- `key`（必填）：环境变量名
- `value`（`set` 时必填）：环境变量值

**示例**：
```json
{"action": "get", "key": "PATH"}
{"action": "set", "key": "MY_VAR", "value": "my_value"}
```

**返回值**：`get` 返回变量值；`set`/`unset` 返回布尔成功标志

---

### sleep
**功能描述**：让当前沙箱暂停指定秒数（用于调试或等待外部进程）。

**参数**：
- `seconds`（必填）：暂停的秒数（支持小数）

**示例**：
```json
{"seconds": 2.5}
```

**返回值**：暂停后返回 `True`

---

## 网络工具

### browse / search
**功能描述**：通过网络搜索获取最新的网页信息、文档或图片链接。`search` 是内部实现的 `browse` 的简化版，只返回搜索结果的摘要或链接。

**参数**：
- `query`（必填）：搜索关键词
- `max_results`（可选）：最大返回结果数

**示例**：
```json
{"query": "Python best practices"}
```

**典型使用场景**：查询实时数据、查找官方文档、获取最新新闻、快速获取答案、验证事实

---

### download
**功能描述**：从网络 URL 下载文件到本地临时目录。

**参数**：
- `url`（必填）：要下载的文件 URL
- `dest_path`（可选）：目标保存路径
- `timeout`（可选）：超时时间（秒）

**示例**：
```json
{"url": "https://example.com/data.csv", "dest_path": "/tmp/data.csv"}
```

**返回值**：下载成功返回本地路径，失败抛异常

---

### upload
**功能描述**：将本地文件上传到指定的远程存储（如 S3、FTP），需要预先配置凭证。

**参数**：
- `local_path`（必填）：本地文件路径
- `remote_path`（必填）：远程存储路径
- `service`（必填）：存储服务类型，如 `"s3"`
- `metadata`（可选）：元数据字典

**示例**：
```json
{"local_path": "/tmp/report.pdf", "remote_path": "s3://my-bucket/reports/report.pdf", "service": "s3"}
```

**返回值**：成功返回 `True`，失败返回错误信息

---

## 其他工具

### file_upload
**功能描述**：上传本地文件供模型读取。

**典型使用场景**：提供数据集、文档、代码等供后续处理

---

### file_download
**功能描述**：下载模型生成的文件（如图片、CSV、PDF 等）。

**典型使用场景**：获取生成的报告、图表或其他产出

---

### dall-e
**功能描述**：调用 DALL·E 生成图像（根据文字描述）。

**典型使用场景**：生成概念图、插画、示意图等视觉素材

---

### zip
**功能描述**：将指定文件/目录压缩为 zip 包。

**参数**：
- `source`（必填）：要压缩的文件或目录路径
- `dest_zip`（必填）：目标 zip 文件路径
- `compresslevel`（可选）：压缩级别（0-9），默认 6

**示例**：
```json
{"source": "/project", "dest_zip": "/tmp/project.zip", "compresslevel": 6}
```

**返回值**：成功返回 zip 文件路径

---

### unzip
**功能描述**：解压 zip 包到目标目录。

**参数**：
- `zip_path`（必填）：zip 文件路径
- `dest_dir`（必填）：目标解压目录
- `overwrite`（可选，布尔值）：是否覆盖已存在的文件

**示例**：
```json
{"zip_path": "/tmp/project.zip", "dest_dir": "/project", "overwrite": true}
```

**返回值**：成功返回解压后文件列表

---

## 使用建议

1. **文件操作**：优先使用 `read_file` 和 `write_file` 进行文件读写，使用 `print_tree` 了解项目结构
2. **代码执行**：使用 `code_interpreter` 或 `python` 执行 Python 代码，使用 `run` 或 `shell` 执行系统命令
3. **搜索定位**：使用 `search` 快速定位代码中的关键字或函数
4. **Git 操作**：使用 `git` 工具进行版本控制操作
5. **网络资源**：使用 `browse` 或 `download` 获取在线资源
