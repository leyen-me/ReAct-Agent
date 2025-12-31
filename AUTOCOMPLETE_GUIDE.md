# 自动补全功能使用指南

## 功能概述

ReAct Agent 现在支持类似 Element Plus 的动态指令提示功能。当你在终端中输入 `/` 后，可以按 Tab 键查看所有可用指令。

## 使用方法

### 1. 查看所有指令
- 输入 `/` 然后按 Tab 键
- 系统会显示所有可用指令列表
- 使用方向键选择指令
- 按 Enter 确认选择

### 2. 自动补全
- 输入 `/h` 然后按 Tab 键
- 系统会自动补全为 `/help`
- 按 Enter 执行指令

### 3. 多列显示
- 当指令较多时，系统会以多列形式显示
- 便于浏览和选择

## 可用指令

当前支持的指令：
- `/help` - 显示帮助信息
- `/exit` - 退出程序

## 技术实现

本功能使用以下技术：
- **Prompt Toolkit**: 专业的终端交互库
- **WordCompleter**: 单词自动补全器
- **CompleteStyle.MULTI_COLUMN**: 多列显示样式

## 注意事项

- 自动补全功能需要真实的终端环境
- 在管道输入或重定向输入时无法使用
- 建议在交互式终端中使用以获得最佳体验

## 扩展指令

要添加新的指令，只需在 `CommandProcessor` 类的 `commands` 字典中添加新的指令处理函数即可。

```python
self.commands = {
    "help": self._help_command,
    "exit": self._exit_command,
    "clear": self._clear_command,  # 新增指令
}
```
