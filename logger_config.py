# -*- coding: utf-8 -*-
"""日志配置模块"""

import logging
import sys
from typing import Optional


class NoNewlineFormatter(logging.Formatter):
    """不添加换行符的格式化器（用于流式输出）"""
    
    def format(self, record):
        # 检查 extra 中的 no_newline 属性
        no_newline = getattr(record, 'no_newline', False)
        if no_newline:
            # 移除默认的换行符
            original_fmt = self._style._fmt
            if original_fmt and original_fmt.endswith('\n'):
                self._style._fmt = original_fmt[:-1]
            result = super().format(record)
            self._style._fmt = original_fmt
            return result
        return super().format(record)


def setup_logging(debug_mode: bool = False, log_file: Optional[str] = None) -> None:
    """
    配置日志系统
    
    Args:
        debug_mode: 是否启用调试模式
        log_file: 日志文件路径（可选）
    """
    # 设置日志级别
    level = logging.DEBUG if debug_mode else logging.INFO
    
    # 创建根 logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除已有的处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # 格式化器
    if debug_mode:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        formatter = NoNewlineFormatter('%(message)s')
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器（如果指定）
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

