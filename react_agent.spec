# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件
用于将 ReAct Agent 打包成独立的可执行文件
"""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

# 获取当前脚本所在目录（spec 文件所在目录）
# 如果 SPEC 变量存在则使用它，否则使用当前工作目录
try:
    current_dir = os.path.dirname(os.path.abspath(SPEC))
except NameError:
    # 如果 SPEC 变量不存在，使用当前工作目录
    current_dir = os.getcwd()

# 收集所有需要的数据文件
datas = []

# 收集隐藏导入（PyInstaller 可能无法自动检测的模块）
hiddenimports = [
    # OpenAI 相关模块
    'openai',
    'openai.types',
    'openai.types.chat',
    'openai.resources',
    'openai.resources.chat',
    'openai._client',
    'openai._streaming',
    # 本地模块
    'config',
    'logger_config',
    'agent',
    'update',
    '__init__',
    'tool_executor',
    'utils',
    # tools 模块及其子模块
    'tools',
    'tools.base',
    'tools.code_execution_tools',
    'tools.file_tools',
    'tools.system_tools',
    'tools.context_tools',
]

# 收集所有 tools 子模块
hiddenimports += collect_submodules('tools')

a = Analysis(
    ['main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ask',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 控制台应用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

