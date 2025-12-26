# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置文件
用于将 ReAct Agent 打包成独立的可执行文件
"""

block_cipher = None

# 收集所有需要的数据文件
datas = []

# 收集隐藏导入（PyInstaller 可能无法自动检测的模块）
hiddenimports = [
    'openai',
    'openai.types',
    'openai.types.chat',
    'openai.resources',
    'openai.resources.chat',
    'openai._client',
    'openai._streaming',
]

a = Analysis(
    ['main.py'],
    pathex=[],
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
    name='react-agent',
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

