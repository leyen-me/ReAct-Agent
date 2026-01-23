# -*- coding: utf-8 -*-
"""文件操作工具"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from tools.base import Tool
from utils import load_gitignore, should_ignore, filter_dirs


def _check_dependency_files(path: str) -> str:
    """
    检查目录中是否存在依赖配置文件，如果存在则返回提示信息
    
    Args:
        path: 目录路径
        
    Returns:
        提示信息字符串，如果没有依赖文件则返回空字符串
    """
    dependency_hints = []
    
    # 常见的依赖配置文件
    dependency_files = {
        'package.json': 'Node.js 项目（依赖可能已安装在 node_modules 中，但该目录被隐藏）',
        'package-lock.json': 'Node.js 项目（依赖可能已安装在 node_modules 中，但该目录被隐藏）',
        'yarn.lock': 'Yarn 项目（依赖可能已安装在 node_modules 中，但该目录被隐藏）',
        'pnpm-lock.yaml': 'pnpm 项目（依赖可能已安装在 node_modules 中，但该目录被隐藏）',
        'requirements.txt': 'Python 项目（依赖可能已安装在 venv/env 中，但该目录被隐藏）',
        'pyproject.toml': 'Python 项目（依赖可能已安装在 venv/env 中，但该目录被隐藏）',
        'Pipfile': 'Python pipenv 项目（依赖可能已安装在虚拟环境中，但该目录被隐藏）',
        'go.mod': 'Go 项目（依赖可能已安装在 vendor 中，但该目录被隐藏）',
        'pom.xml': 'Java Maven 项目（依赖可能已安装在 target 中，但该目录被隐藏）',
        'build.gradle': 'Java Gradle 项目（依赖可能已安装在 build 中，但该目录被隐藏）',
        'Cargo.toml': 'Rust 项目（依赖可能已安装在 target 中，但该目录被隐藏）',
    }
    
    for dep_file, hint in dependency_files.items():
        dep_path = os.path.join(path, dep_file)
        if os.path.exists(dep_path) and os.path.isfile(dep_path):
            dependency_hints.append(hint)
            break  # 每个项目类型只提示一次
    
    if dependency_hints:
        return f"\n\n注意：{dependency_hints[0]}"
    
    return ""


class ReadFileTool(Tool):
    """读取文件内容（带行号）"""
    
    def _get_description(self) -> str:
        return "读取文件内容，返回的内容包含行号信息，格式为 '行号 | 内容'。这对于后续使用 EditFileByLineTool 进行基于行号的编辑非常有用。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                lines = file.readlines()
            
            # 格式化输出，每行包含行号
            result_lines = []
            for i, line in enumerate(lines, start=1):
                # 保持原有内容，但添加行号前缀
                result_lines.append(f"{i:4d} | {line.rstrip()}")
            
            return "\n".join(result_lines)
        except Exception as e:
            return f"读取文件失败: {e}"


class WriteFileTool(Tool):
    """写入文件内容"""
    
    def _get_description(self) -> str:
        return "写入文件内容"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["path", "content"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                file.write(parameters["content"])
            return f"文件 {path} 写入成功"
        except Exception as e:
            return f"写入文件失败: {e}"


class DeleteFileTool(Tool):
    """删除文件"""
    
    def _get_description(self) -> str:
        return "删除文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            os.remove(path)
            return f"文件 {path} 删除成功"
        except Exception as e:
            return f"删除文件失败: {e}"


class CreateFileTool(Tool):
    """创建文件"""
    
    def _get_description(self) -> str:
        return "创建文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if os.path.exists(path):
            return f"文件 {path} 已存在"
        
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as file:
                file.write("")
            return f"文件 {path} 创建成功"
        except Exception as e:
            return f"创建文件失败: {e}"


class RenameFileTool(Tool):
    """重命名文件"""
    
    def _get_description(self) -> str:
        return "重命名文件"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "new_name": {"type": "string", "description": "新文件名"},
            },
            "required": ["path", "new_name"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        new_name = parameters["new_name"]
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        # 处理新路径
        if os.path.isabs(new_name):
            new_path = new_name
        else:
            dir_name = os.path.dirname(path)
            new_path = os.path.join(dir_name, new_name)
        
        is_valid, error = self.validate_path(new_path)
        if not is_valid:
            return f"新文件路径错误: {error}"
        
        if os.path.exists(new_path):
            return f"目标文件 {new_path} 已存在"
        
        try:
            os.rename(path, new_path)
            return f"文件 {path} 重命名成功为 {new_path}"
        except Exception as e:
            return f"重命名文件失败: {e}"


class ListFilesTool(Tool):
    """列出文件列表"""
    
    def _get_description(self) -> str:
        return "列出文件列表。注意：此工具会自动忽略一些常见目录（如 node_modules、venv、.git 等）和 .gitignore 中指定的文件，以避免输出过多无关内容。如果看不到依赖安装目录但存在依赖配置文件（如 package.json、requirements.txt），说明依赖已安装但目录被隐藏。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        
        if not os.path.exists(path):
            return f"目录 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是目录"
        
        # 加载 .gitignore 规则
        gitignore_spec = load_gitignore(path)
        
        try:
            items = []
            for f in os.listdir(path):
                full_path = os.path.join(path, f)
                is_dir = os.path.isdir(full_path)
                
                # 检查 gitignore 规则
                if should_ignore(full_path, path, gitignore_spec, is_dir=is_dir):
                    continue
                
                # 添加标识以区分文件和目录
                if is_dir:
                    items.append(f"{full_path} [DIR]")
                else:
                    items.append(full_path)
            
            result = "\n".join(items) if items else "目录为空"
            # 添加依赖文件检测提示
            hint = _check_dependency_files(path)
            return result + hint
        except Exception as e:
            return f"列出文件失败: {e}"


class TreeFilesTool(Tool):
    """显示目录树结构"""
    
    def _get_description(self) -> str:
        return "显示目录树结构。注意：此工具会自动忽略一些常见目录（如 node_modules、venv、.git 等）和 .gitignore 中指定的文件，以避免输出过多无关内容。如果看不到依赖安装目录但存在依赖配置文件（如 package.json、requirements.txt），说明依赖已安装但目录被隐藏。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"},
                "max_depth": {"type": "number", "description": "最大深度（默认：3）", "default": 3}
            },
            "required": ["path"],
        }
    
    def _build_tree(self, path: str, root_dir: str, prefix: str = "", depth: int = 0, max_depth: int = 3, 
                    gitignore_spec: Optional[Any] = None) -> str:
        """构建目录树结构"""
        if depth >= max_depth:
            return ""
        
        if not os.path.exists(path) or not os.path.isdir(path):
            return ""
        
        try:
            items = []
            
            # 获取所有文件和目录
            all_items = sorted(os.listdir(path))
            
            # 过滤文件和目录（使用 gitignore 规则）
            for item in all_items:
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                
                # 检查 gitignore 规则
                if should_ignore(full_path, root_dir, gitignore_spec, is_dir=is_dir):
                    continue
                
                items.append(item)
            
            tree_lines = []
            for i, item in enumerate(items):
                full_path = os.path.join(path, item)
                is_last = i == len(items) - 1
                
                connector = "└── " if is_last else "├── "
                tree_lines.append(f"{prefix}{connector}{item}")
                
                if os.path.isdir(full_path):
                    new_prefix = prefix + ("    " if is_last else "│   ")
                    subtree = self._build_tree(full_path, root_dir, new_prefix, depth + 1, max_depth, 
                                             gitignore_spec)
                    if subtree:
                        tree_lines.append(subtree)
            
            return "\n".join(tree_lines)
        except Exception:
            return ""
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        max_depth = parameters.get("max_depth", 3)
        
        if not os.path.exists(path):
            return f"目录 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是目录"
        
        # 加载 .gitignore 规则
        gitignore_spec = load_gitignore(path)
        
        try:
            tree = self._build_tree(path, path, max_depth=max_depth, gitignore_spec=gitignore_spec)
            if not tree:
                result = "目录为空或所有内容都被忽略"
            else:
                result = f"{path}\n{tree}"
            
            # 添加依赖文件检测提示
            hint = _check_dependency_files(path)
            return result + hint
        except Exception as e:
            return f"显示目录树失败: {e}"


class EditFileTool(Tool):
    """编辑文件内容（部分替换）"""
    
    def _get_description(self) -> str:
        return "编辑文件内容（部分替换），只替换匹配的文本部分，保留文件其他内容不变。这是推荐的文件编辑方式，类似于 Cursor 的部分替换功能。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "old_string": {"type": "string", "description": "要替换的原始文本（必须精确匹配，包括空格、换行等）"},
                "new_string": {"type": "string", "description": "替换后的新文本"},
                "replace_all": {"type": "boolean", "description": "是否替换所有匹配项（默认 false，只替换第一个匹配项）", "default": False},
            },
            "required": ["path", "old_string", "new_string"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            old_string = parameters["old_string"]
            new_string = parameters["new_string"]
            replace_all = parameters.get("replace_all", False)
            
            if old_string not in content:
                return "错误：文件中未找到要替换的文本。请确保 old_string 与文件中的内容完全匹配（包括空格、换行、缩进等）。"
            
            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1
            
            with open(path, "w", encoding="utf-8") as file:
                file.write(new_content)
            
            return f"文件 {path} 编辑成功，已替换 {count} 处匹配的文本"
        except Exception as e:
            return f"编辑文件失败: {e}"


class EditFileByLineTool(Tool):
    """根据行号编辑文件内容"""
    
    def _get_description(self) -> str:
        return "根据行号编辑文件内容，替换指定行范围的内容。这比 EditFileTool 更方便，因为不需要提供完整的 old_string，只需要指定起始行号和结束行号即可。建议先使用 ReadFileTool 查看文件内容（带行号），然后使用此工具进行编辑。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "start_line": {"type": "number", "description": "起始行号（从1开始，包含此行）"},
                "end_line": {"type": "number", "description": "结束行号（从1开始，包含此行）。如果只替换单行，则 end_line 等于 start_line"},
                "new_string": {"type": "string", "description": "替换后的新文本内容。如果替换多行，可以包含换行符"},
            },
            "required": ["path", "start_line", "end_line", "new_string"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        start_line = parameters["start_line"]
        end_line = parameters["end_line"]
        new_string = parameters["new_string"]
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                lines = file.readlines()
            
            total_lines = len(lines)
            
            # 验证行号
            if start_line < 1 or start_line > total_lines:
                return f"起始行号 {start_line} 超出范围（文件共有 {total_lines} 行）"
            
            if end_line < 1 or end_line > total_lines:
                return f"结束行号 {end_line} 超出范围（文件共有 {total_lines} 行）"
            
            if start_line > end_line:
                return f"起始行号 {start_line} 不能大于结束行号 {end_line}"
            
            # 构建新内容
            # 保留 start_line 之前的行
            new_lines = lines[:start_line - 1]
            
            # 处理新内容
            if new_string:
                # 将 new_string 按行分割
                new_content_lines = new_string.split('\n')
                
                # 如果 new_string 以换行符结尾，split 后最后会有一个空字符串
                # 这表示新内容最后一行是空行，需要保留
                has_trailing_newline = new_string.endswith('\n')
                
                # 添加新行
                for i, line in enumerate(new_content_lines):
                    # 判断是否是最后一行
                    is_last_line = (i == len(new_content_lines) - 1)
                    
                    if is_last_line:
                        # 最后一行：需要判断是否添加换行符
                        # 如果 end_line 之后还有内容，则必须添加换行符
                        # 如果 end_line 是文件最后一行，则根据原文件最后一行是否有换行符来决定
                        if end_line < total_lines:
                            # end_line 之后还有内容，必须添加换行符
                            new_lines.append(line + '\n')
                        else:
                            # end_line 是文件最后一行
                            # 如果原文件最后一行有换行符，或者 new_string 以换行符结尾，则添加换行符
                            if total_lines > 0 and lines[-1].endswith('\n'):
                                new_lines.append(line + '\n')
                            elif has_trailing_newline:
                                new_lines.append(line + '\n')
                            else:
                                new_lines.append(line)
                    else:
                        # 不是最后一行，必须添加换行符
                        new_lines.append(line + '\n')
            
            # 保留 end_line 之后的行
            if end_line < total_lines:
                new_lines.extend(lines[end_line:])
            
            # 写入文件
            with open(path, "w", encoding="utf-8") as file:
                file.writelines(new_lines)
            
            replaced_lines = end_line - start_line + 1
            return f"文件 {path} 编辑成功，已替换第 {start_line}-{end_line} 行（共 {replaced_lines} 行）"
        except Exception as e:
            return f"编辑文件失败: {e}"


class EditFileByPositionTool(Tool):
    """根据字符位置编辑文件内容（精确到游标位置）"""
    
    def _get_description(self) -> str:
        return "根据字符偏移量精确编辑文件内容，支持在任意字符位置插入、删除或替换。这是最精确的编辑方式，可以精确到单个字符位置。字符位置从0开始计数（文件第一个字符的位置是0）。如果 start_position == end_position，则是在该位置插入；如果 new_string 为空，则是删除指定范围的内容；否则是替换指定范围的内容。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "start_position": {"type": "number", "description": "起始字符位置（从0开始，包含此位置）。文件第一个字符的位置是0"},
                "end_position": {"type": "number", "description": "结束字符位置（从0开始，不包含此位置）。如果 start_position == end_position，则是在该位置插入内容；如果 start_position < end_position，则是替换或删除该范围的内容"},
                "new_string": {"type": "string", "description": "新文本内容。如果为空字符串，则删除指定范围的内容；如果不为空，则替换或插入该内容"},
            },
            "required": ["path", "start_position", "end_position", "new_string"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        start_position = int(parameters["start_position"])
        end_position = int(parameters["end_position"])
        new_string = parameters["new_string"]
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        if start_position < 0:
            return f"起始位置 {start_position} 不能为负数"
        
        if end_position < start_position:
            return f"结束位置 {end_position} 不能小于起始位置 {start_position}"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            total_chars = len(content)
            
            # 验证位置范围
            if start_position > total_chars:
                return f"起始位置 {start_position} 超出范围（文件共有 {total_chars} 个字符）"
            
            if end_position > total_chars:
                return f"结束位置 {end_position} 超出范围（文件共有 {total_chars} 个字符）"
            
            # 执行编辑操作
            if start_position == end_position:
                # 插入操作
                new_content = content[:start_position] + new_string + content[start_position:]
                operation = "插入"
                details = f"在位置 {start_position} 插入了 {len(new_string)} 个字符"
            elif not new_string:
                # 删除操作
                deleted_text = content[start_position:end_position]
                new_content = content[:start_position] + content[end_position:]
                operation = "删除"
                deleted_chars = end_position - start_position
                details = f"删除了位置 {start_position}-{end_position} 的 {deleted_chars} 个字符"
            else:
                # 替换操作
                new_content = content[:start_position] + new_string + content[end_position:]
                operation = "替换"
                replaced_chars = end_position - start_position
                details = f"替换了位置 {start_position}-{end_position} 的 {replaced_chars} 个字符为 {len(new_string)} 个字符"
            
            # 写入文件
            with open(path, "w", encoding="utf-8") as file:
                file.write(new_content)
            
            return f"文件 {path} 编辑成功，{operation}操作：{details}"
        except Exception as e:
            return f"编辑文件失败: {e}"


class CreateFolderTool(Tool):
    """创建文件夹"""
    
    def _get_description(self) -> str:
        return "创建文件夹"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件夹路径错误: {error}"
        
        if os.path.exists(path):
            return f"文件夹 {path} 已存在"
        
        try:
            os.makedirs(path, exist_ok=True)
            return f"文件夹 {path} 创建成功"
        except Exception as e:
            return f"创建文件夹失败: {e}"


class DeleteFolderTool(Tool):
    """删除文件夹及其所有内容（递归删除）"""
    
    def _get_description(self) -> str:
        return "删除文件夹及其所有内容（递归删除）"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件夹路径"}
            },
            "required": ["path"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件夹路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件夹 {path} 不存在"
        
        if not os.path.isdir(path):
            return f"{path} 不是文件夹"
        
        try:
            shutil.rmtree(path)
            return f"文件夹 {path} 删除成功"
        except Exception as e:
            return f"删除文件夹失败: {e}"


class MoveFileTool(Tool):
    """移动文件或文件夹到新位置"""
    
    def _get_description(self) -> str:
        return "移动文件或文件夹到新位置"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        source = parameters["source"]
        destination = parameters["destination"]
        
        is_valid, error = self.validate_path(source)
        if not is_valid:
            return f"源路径错误: {error}"
        
        is_valid, error = self.validate_path(destination)
        if not is_valid:
            return f"目标路径错误: {error}"
        
        if not os.path.exists(source):
            return f"源路径 {source} 不存在"
        
        try:
            shutil.move(source, destination)
            return f"成功将 {source} 移动到 {destination}"
        except Exception as e:
            return f"移动文件失败: {e}"


class CopyFileTool(Tool):
    """复制文件或文件夹到新位置"""
    
    def _get_description(self) -> str:
        return "复制文件或文件夹到新位置"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "源文件或文件夹路径"},
                "destination": {"type": "string", "description": "目标路径"},
            },
            "required": ["source", "destination"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        source = parameters["source"]
        destination = parameters["destination"]
        
        is_valid, error = self.validate_path(source)
        if not is_valid:
            return f"源路径错误: {error}"
        
        is_valid, error = self.validate_path(destination)
        if not is_valid:
            return f"目标路径错误: {error}"
        
        if not os.path.exists(source):
            return f"源路径 {source} 不存在"
        
        try:
            if os.path.isdir(source):
                shutil.copytree(source, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(source, destination)
            return f"成功将 {source} 复制到 {destination}"
        except Exception as e:
            return f"复制文件失败: {e}"


class ReadCodeBlockTool(Tool):
    """读取文件指定行周围的代码块"""
    
    def _get_description(self) -> str:
        return "读取文件指定行周围的代码块（包含前后上下文）。这对于查看搜索结果中特定行的代码上下文非常有用，可以避免读取整个文件，节省上下文空间。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件绝对路径"},
                "line": {"type": "number", "description": "目标行号（从1开始）"},
                "context_lines": {"type": "number", "description": "前后各包含多少行上下文（默认：10行）", "default": 10},
            },
            "required": ["path", "line"],
        }
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        line_num = parameters["line"]
        context_lines = parameters.get("context_lines", 10)
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        if not os.path.isfile(path):
            return f"{path} 不是文件"
        
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                lines = file.readlines()
            
            total_lines = len(lines)
            
            # 验证行号
            if line_num < 1 or line_num > total_lines:
                return f"行号 {line_num} 超出范围（文件共有 {total_lines} 行）"
            
            # 计算起始和结束行号（从0开始索引）
            start_line = max(0, line_num - 1 - context_lines)
            end_line = min(total_lines, line_num + context_lines)
            
            # 提取代码块
            code_block = lines[start_line:end_line]
            
            # 格式化输出
            result_lines = [f"文件: {path}"]
            result_lines.append(f"行号范围: {start_line + 1}-{end_line} (目标行: {line_num})")
            result_lines.append("")
            
            # 添加代码行，带行号
            for i, line_content in enumerate(code_block, start=start_line + 1):
                # 标记目标行
                marker = ">>> " if i == line_num else "    "
                result_lines.append(f"{marker}{i:4d} | {line_content.rstrip()}")
            
            return "\n".join(result_lines)
        except Exception as e:
            return f"读取代码块失败: {e}"
