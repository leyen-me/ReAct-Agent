#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from prompt_toolkit.shortcuts import CompleteStyle
import sys

COMMANDS = ["help", "exit", "status", "get_messages"]
COMMAND_NAMES = [f"/{cmd}" for cmd in COMMANDS]

def get_prompt_message(first_time: bool) -> HTML:
    if first_time:
        # 使用灰色 placeholder 作为输入提示
        return HTML("<ansicyan>> </ansicyan><ansigray>请输入任务或指令...</ansigray>")
    else:
        return HTML("<ansicyan>> </ansicyy>")  # 注意：这里应该是白色，修正如下

def get_prompt_message(first_time: bool) -> HTML:
    if first_time:
        return HTML("<ansicyan>> </ansicyan><ansigray>请输入任务或指令...</ansigray>")
    else:
        return HTML("<ansicyan>> </ansicyan>")

def main():
    completer = WordCompleter(
        COMMAND_NAMES,
        ignore_case=True,
        match_middle=True,
        sentence=True
    )

    custom_style = Style.from_dict({
        '': '#ffffff bg:#1e1e1e',
    })

    session = PromptSession(
        completer=completer,
        complete_style=CompleteStyle.MULTI_COLUMN,
        style=custom_style
    )

    print("\n" + "=".ljust(60, "="))
    print("ReAct Agent - 紧凑型 Placeholder 输入")
    print("=".ljust(60, "="))

    first_input = True
    try:
        while True:
            # 打印 border
            print("\n" + "─".ljust(60, "─"))

            # 获取 prompt（包含或不包含 placeholder）
            prompt_msg = get_prompt_message(first_input)

            user_input = session.prompt(prompt_msg)

            print("─".ljust(60, "─"))

            if user_input.strip() == "/exit":
                print("\n👋 再见！")
                break

            print(f"\n✅ 你输入了: {repr(user_input)}")

            if first_input and user_input.strip():
                first_input = False

    except (EOFError, KeyboardInterrupt):
        print("\n\n⚠️  程序被中断。")
        sys.exit(0)

if __name__ == "__main__":
    main()