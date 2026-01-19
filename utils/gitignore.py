# -*- coding: utf-8 -*-
"""GitIgnore 工具模块"""

import os
from pathlib import Path
from typing import Optional

from pathspec import GitIgnoreSpec

# 默认忽略的目录列表（当没有 .gitignore 时使用）
DEFAULT_IGNORE_DIRS = {
    # Python 相关
    '__pycache__', '.pytest_cache', '.mypy_cache', '.coverage', 'htmlcov',
    '.tox', '.nox', '.hypothesis', '.ruff_cache',
    'venv', 'env', '.venv', 'ENV', 'virtualenv',
    
    # Node.js 相关
    'node_modules', '.npm', '.yarn', '.pnp', '.pnp.js',
    '.next', '.nuxt', '.cache', '.parcel-cache', '.turbo',
    '.sass-cache', '.eslintcache', '.pnpm-store', '.lerna',
    '.rollup.cache', '.vite', '.swc', '.rpt2_cache',
    '.jest-cache', '.storybook-static', '.storybook-out',
    '.output', '.vercel', '.netlify',
    
    # Java 相关
    'target', 'bin', 'out', '.gradle', '.mvn', '.classpath',
    '.settings', '.project',
    
    # C/C++ 相关
    'build', 'dist', 'obj', 'Debug', 'Release', '.vs',
    'CMakeFiles',
    
    # Rust 相关
    # 'target',  # 已在 Java 中
    
    # Go 相关
    'vendor',
    
    # 版本控制
    '.git', '.svn', '.hg', '.bzr',
    
    # IDE/编辑器
    '.idea', '.vscode', '.vs', '.fleet',
    '.eclipse', '.metadata', '.recommenders',
    '.sublime-workspace', '.sublime-project',
    
    # 构建和编译产物
    # 'build', 'dist', 'out', 'target', 'bin', 'obj',  # 已在上面
    
    # 测试覆盖率
    'coverage', '.nyc_output',
    
    # 日志和临时文件
    'logs', 'tmp', 'temp', '.cache', '.tmp',
    
    # 操作系统文件
    '.DS_Store', 'Thumbs.db', 'Desktop.ini', '.AppleDouble',
    
    # 环境变量和配置
    '.env.local',
    
    # 其他框架和工具
    '.serverless', '.terraform', '.vagrant', '.firebase',
    '.bundle',  # Ruby
    
    # 项目特定
    '.agent_history', '.agent_config', '.agent_logs',
    
    # 其他常见目录
    '.deps', '.libs', '.dirstamp', '.stamp',
    '.eggs',
}


def load_gitignore(root_dir: str) -> Optional[GitIgnoreSpec]:
    """
    加载并解析 .gitignore 文件
    
    Args:
        root_dir: 根目录路径
        
    Returns:
        GitIgnoreSpec 对象，如果加载失败则返回 None
    """
    try:
        gitignore_path = os.path.join(root_dir, '.gitignore')
        if not os.path.exists(gitignore_path):
            return None
        
        with open(gitignore_path, 'r', encoding='utf-8', errors='ignore') as f:
            # GitIgnoreSpec.from_lines 可以直接接受文件对象
            return GitIgnoreSpec.from_lines(f)
    except Exception:
        # 如果加载失败，返回 None，使用默认忽略列表
        return None


def should_ignore(
    path: str, 
    root_dir: str, 
    gitignore_spec: Optional[GitIgnoreSpec] = None,
    is_dir: bool = False
) -> bool:
    """
    检查路径是否应该被忽略
    
    Args:
        path: 要检查的路径（绝对路径或相对路径）
        root_dir: 根目录路径
        gitignore_spec: GitIgnoreSpec 对象（可选，如果不提供会自动加载）
        is_dir: 是否为目录
        
    Returns:
        如果应该忽略则返回 True
    """
    # 如果路径不在根目录下，不忽略
    try:
        rel_path = os.path.relpath(path, root_dir)
        if rel_path.startswith('..'):
            return False
    except ValueError:
        # 如果路径无法转换为相对路径，不忽略
        return False
    
    # 如果没有提供 gitignore_spec，尝试加载
    if gitignore_spec is None:
        gitignore_spec = load_gitignore(root_dir)
    
    # 使用 .gitignore 规则（如果可用）
    if gitignore_spec:
        try:
            # pathspec 使用正斜杠作为路径分隔符
            normalized_path = rel_path.replace(os.sep, '/')
            if is_dir:
                normalized_path += '/'
            return gitignore_spec.match_file(normalized_path)
        except Exception:
            pass
    
    # 如果没有 .gitignore 或解析失败，使用默认忽略列表
    path_parts = Path(rel_path).parts
    if path_parts:
        first_part = path_parts[0]
        if first_part in DEFAULT_IGNORE_DIRS:
            return True
    
    return False


def filter_dirs(dirs: list, root: str, root_dir: str, gitignore_spec: Optional[GitIgnoreSpec] = None) -> list:
    """
    过滤目录列表，排除被 .gitignore 忽略的目录
    
    用于在 os.walk() 中修改 dirs 列表，避免遍历被忽略的目录
    
    Args:
        dirs: 目录名列表
        root: 当前遍历的根目录
        root_dir: 搜索的根目录
        gitignore_spec: GitIgnoreSpec 对象（可选）
        
    Returns:
        过滤后的目录列表
    """
    return [
        d for d in dirs 
        if not should_ignore(os.path.join(root, d), root_dir, gitignore_spec, is_dir=True)
    ]


def filter_files(files: list, root: str, root_dir: str, gitignore_spec: Optional[GitIgnoreSpec] = None) -> list:
    """
    过滤文件列表，排除被 .gitignore 忽略的文件
    
    Args:
        files: 文件名列表
        root: 当前遍历的根目录
        root_dir: 搜索的根目录
        gitignore_spec: GitIgnoreSpec 对象（可选）
        
    Returns:
        过滤后的文件列表
    """
    return [
        f for f in files
        if not should_ignore(os.path.join(root, f), root_dir, gitignore_spec, is_dir=False)
    ]

