# -*- coding: utf-8 -*-
"""命令行参数处理模块"""

import sys
from typing import Optional


class ArgumentHandler:
    """命令行参数处理器"""
    
    def __init__(self):
        """初始化参数处理器"""
        self.args = sys.argv[1:]
    
    def handle(self) -> Optional[bool]:
        """
        处理命令行参数
        
        Returns:
            如果需要退出程序返回 True，如果继续运行返回 False，如果无参数返回 None
        """
        if not self.args:
            return None
        
        arg = self.args[0].lower()
        
        handlers = {
            ("--update", "update", "-u"): self._handle_update,
            ("--version", "-v", "version"): self._handle_version,
            ("--check-update", "check-update"): self._handle_check_update,
            ("--help", "-h", "help"): self._handle_help,
        }
        
        for keys, handler in handlers.items():
            if arg in keys:
                handler()
                return True
        
        return None
    
    def _handle_update(self) -> None:
        """处理更新命令"""
        from update import Updater
        
        updater = Updater()
        success, message = updater.update()
        print(message)
        sys.exit(0 if success else 1)
    
    def _handle_version(self) -> None:
        """处理版本命令"""
        from __init__ import __version__
        
        print(f"ask version {__version__}")
        sys.exit(0)
    
    def _handle_check_update(self) -> None:
        """处理检查更新命令"""
        from update import Updater
        
        updater = Updater()
        latest = updater.get_latest_version()
        
        if latest:
            comparison = updater.compare_versions(updater.current_version, latest)
            if comparison < 0:
                print(f"发现新版本: {latest} (当前: {updater.current_version})")
                print(f"运行 'ask --update' 进行更新")
            else:
                print(f"当前已是最新版本: {updater.current_version}")
        else:
            print("无法检查更新，请检查网络连接")
        
        sys.exit(0)
    
    def _handle_help(self) -> None:
        """处理帮助命令"""
        print("ReAct Agent - 智能代理工具")
        print("\n用法:")
        print("  ask                   启动交互式会话")
        print("  ask --version         显示版本号")
        print("  ask --update          更新到最新版本")
        print("  ask --check-update    检查是否有新版本")
        print("  ask --help            显示帮助信息")
        sys.exit(0)

