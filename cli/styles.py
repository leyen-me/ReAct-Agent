# -*- coding: utf-8 -*-
"""命令行界面样式配置模块"""

from prompt_toolkit.styles import Style


def get_custom_style() -> Style:
    """
    获取自定义样式配置
    
    Returns:
        Style: prompt_toolkit 样式对象
    """
    return Style.from_dict({
        # 输入区域样式
        "ansicyan": "#00ffcc",
        "ansigray": "#888888",
        
        # 补全菜单样式（列表风格）
        "completion-menu": "bg:#1a1a1a #ffffff",  # 菜单背景：深灰色，文字：白色
        "completion-menu.completion": "bg:#2a2a2a #cccccc",  # 补全项背景：中灰色
        "completion-menu.completion.current": "bg:#00ffcc #ffffff bold",  # 当前选中项：青色背景，白色粗体
        "completion-menu.completion.selected": "bg:#00ffcc #ffffff bold",  # 选中项：青色背景，白色粗体
        
        # 滚动条样式
        "scrollbar.background": "bg:#333333",
        "scrollbar.button": "bg:#00ffcc",
        "scrollbar.arrow": "#ffffff",
    })

