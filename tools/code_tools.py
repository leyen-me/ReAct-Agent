# -*- coding: utf-8 -*-
"""代码智能补全和重构工具"""

import os
import re
import ast
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from textwrap import dedent

from tools.base import Tool


class FormatCodeTool(Tool):
    """代码格式化工具"""
    
    def _get_description(self) -> str:
        return "格式化代码文件，支持 Python、JavaScript、TypeScript 等。对于 Python，优先使用 black 或 autopep8；对于其他语言，使用基本的格式化规则。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要格式化的文件路径"},
                "language": {"type": "string", "description": "编程语言（python/javascript/typescript），如果不指定则根据文件扩展名自动检测", "default": None},
            },
            "required": ["path"],
        }
    
    def _detect_language(self, path: str) -> str:
        """根据文件扩展名检测语言"""
        ext = Path(path).suffix.lower()
        lang_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
        }
        return lang_map.get(ext, "python")
    
    def _format_python(self, content: str, path: str) -> Tuple[str, str]:
        """格式化 Python 代码"""
        # 尝试使用 black
        try:
            result = subprocess.run(
                ["black", "--stdin-filename", path, "-"],
                input=content.encode("utf-8"),
                capture_output=True,
                timeout=10,
                check=True
            )
            return result.stdout.decode("utf-8"), "使用 black 格式化成功"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # 尝试使用 autopep8
        try:
            result = subprocess.run(
                ["autopep8", "--in-place", "--stdout", "-"],
                input=content.encode("utf-8"),
                capture_output=True,
                timeout=10,
                check=True
            )
            return result.stdout.decode("utf-8"), "使用 autopep8 格式化成功"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # 基本格式化：规范化缩进和空行
        lines = content.split("\n")
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                formatted_lines.append("")
                continue
            
            # 减少缩进级别
            if stripped.startswith(("elif ", "else:", "except", "finally:")):
                indent_level = max(0, indent_level - 1)
            
            formatted_lines.append("    " * indent_level + stripped)
            
            # 增加缩进级别
            if stripped.endswith(":") and not stripped.startswith("#"):
                indent_level += 1
        
        formatted_content = "\n".join(formatted_lines)
        return formatted_content, "使用基本格式化规则格式化成功（建议安装 black 或 autopep8 以获得更好的效果）"
    
    def _format_javascript(self, content: str) -> Tuple[str, str]:
        """格式化 JavaScript/TypeScript 代码"""
        # 尝试使用 prettier
        try:
            result = subprocess.run(
                ["prettier", "--stdin-filepath", "file.js"],
                input=content.encode("utf-8"),
                capture_output=True,
                timeout=10,
                check=True
            )
            return result.stdout.decode("utf-8"), "使用 prettier 格式化成功"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # 基本格式化：规范化缩进
        lines = content.split("\n")
        formatted_lines = []
        indent_level = 0
        indent_size = 2
        
        for line in lines:
            stripped = line.lstrip()
            if not stripped:
                formatted_lines.append("")
                continue
            
            # 减少缩进级别
            if stripped.startswith(("}", "});", ");")):
                indent_level = max(0, indent_level - 1)
            
            formatted_lines.append(" " * (indent_level * indent_size) + stripped)
            
            # 增加缩进级别
            if stripped.endswith(("{", "(")) and not stripped.startswith("//"):
                indent_level += 1
        
        formatted_content = "\n".join(formatted_lines)
        return formatted_content, "使用基本格式化规则格式化成功（建议安装 prettier 以获得更好的效果）"
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        language = parameters.get("language")
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            if not language:
                language = self._detect_language(path)
            
            if language == "python":
                formatted_content, message = self._format_python(content, path)
            elif language in ("javascript", "typescript"):
                formatted_content, message = self._format_javascript(content)
            else:
                return f"不支持的语言: {language}"
            
            with open(path, "w", encoding="utf-8") as file:
                file.write(formatted_content)
            
            return f"{message}\n文件 {path} 已格式化"
        except Exception as e:
            return f"格式化文件失败: {e}"


class RefactorTool(Tool):
    """代码重构工具"""
    
    def _get_description(self) -> str:
        return "重构代码，支持提取变量、简化表达式、优化代码结构等。主要用于 Python 代码的重构。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "要重构的文件路径"},
                "refactor_type": {"type": "string", "description": "重构类型：extract_variable（提取变量）、simplify_expression（简化表达式）、optimize_imports（优化导入）", "enum": ["extract_variable", "simplify_expression", "optimize_imports"]},
                "old_code": {"type": "string", "description": "要重构的旧代码片段（必须精确匹配）"},
                "new_code": {"type": "string", "description": "重构后的新代码"},
            },
            "required": ["path", "refactor_type", "old_code", "new_code"],
        }
    
    def _optimize_imports(self, content: str) -> str:
        """优化导入语句"""
        lines = content.split("\n")
        import_lines = []
        other_lines = []
        in_imports = True
        
        for line in lines:
            stripped = line.strip()
            if in_imports and (stripped.startswith("import ") or stripped.startswith("from ")):
                import_lines.append(line)
            else:
                in_imports = False
                other_lines.append(line)
        
        # 排序导入语句
        import_lines.sort()
        
        # 合并连续的导入
        optimized_imports = []
        for line in import_lines:
            if optimized_imports and optimized_imports[-1].strip().startswith("import ") and line.strip().startswith("import "):
                optimized_imports[-1] = optimized_imports[-1].rstrip() + ", " + line.strip().replace("import ", "")
            else:
                optimized_imports.append(line)
        
        # 在导入和其他代码之间添加空行
        result = "\n".join(optimized_imports)
        if optimized_imports and other_lines and other_lines[0].strip():
            result += "\n"
        
        result += "\n".join(other_lines)
        return result
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        refactor_type = parameters["refactor_type"]
        old_code = parameters["old_code"]
        new_code = parameters["new_code"]
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                content = file.read()
            
            if refactor_type == "optimize_imports":
                new_content = self._optimize_imports(content)
            else:
                # 对于其他重构类型，直接替换代码
                if old_code not in content:
                    return "错误：文件中未找到要重构的代码片段。请确保 old_code 与文件中的内容完全匹配。"
                new_content = content.replace(old_code, new_code)
            
            with open(path, "w", encoding="utf-8") as file:
                file.write(new_content)
            
            return f"文件 {path} 重构成功（类型: {refactor_type}）"
        except Exception as e:
            return f"重构文件失败: {e}"


class ExtractFunctionTool(Tool):
    """提取函数工具"""
    
    def _get_description(self) -> str:
        return "将选定的代码块提取为一个新函数。主要用于 Python 代码。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "start_line": {"type": "integer", "description": "要提取的代码起始行号（从1开始）"},
                "end_line": {"type": "integer", "description": "要提取的代码结束行号（从1开始）"},
                "function_name": {"type": "string", "description": "新函数名称"},
                "parameters": {"type": "string", "description": "函数参数列表，例如 'x, y' 或 'data: dict'", "default": ""},
            },
            "required": ["path", "start_line", "end_line", "function_name"],
        }
    
    def _extract_variables(self, code: str) -> List[str]:
        """提取代码中使用的变量名（简单实现）"""
        # 查找赋值语句左侧的变量
        variables = set()
        for line in code.split("\n"):
            if "=" in line and not line.strip().startswith("#"):
                left_side = line.split("=")[0].strip()
                # 移除可能的类型注解
                if ":" in left_side:
                    left_side = left_side.split(":")[0].strip()
                variables.add(left_side)
        return list(variables)
    
    def run(self, parameters: Dict[str, Any]) -> str:
        path = parameters["path"]
        start_line = parameters["start_line"]
        end_line = parameters["end_line"]
        function_name = parameters["function_name"]
        parameters_str = parameters.get("parameters", "")
        
        is_valid, error = self.validate_path(path)
        if not is_valid:
            return f"文件路径错误: {error}"
        
        if not os.path.exists(path):
            return f"文件 {path} 不存在"
        
        try:
            with open(path, "r", encoding="utf-8") as file:
                lines = file.readlines()
            
            if start_line < 1 or end_line > len(lines) or start_line > end_line:
                return f"行号范围错误：文件共有 {len(lines)} 行，请确保 1 <= start_line <= end_line <= {len(lines)}"
            
            # 提取代码块（转换为0-based索引）
            code_block = "".join(lines[start_line - 1:end_line])
            code_block_stripped = code_block.strip()
            
            # 计算缩进
            first_line = lines[start_line - 1]
            base_indent = len(first_line) - len(first_line.lstrip())
            
            # 移除代码块的缩进
            dedented_lines = []
            for line in code_block.split("\n"):
                if line.strip():
                    if len(line) - len(line.lstrip()) < base_indent:
                        dedented_lines.append(line)
                    else:
                        dedented_lines.append(line[base_indent:])
                else:
                    dedented_lines.append("")
            dedented_code = "\n".join(dedented_lines).strip()
            
            # 如果没有提供参数，尝试自动检测
            if not parameters_str:
                # 简单检测：查找代码中使用的变量
                variables = self._extract_variables(dedented_code)
                parameters_str = ", ".join(variables) if variables else ""
            
            # 解析参数名（去除类型注解）
            param_names = []
            if parameters_str:
                for param in parameters_str.split(","):
                    param = param.strip()
                    if ":" in param:
                        param = param.split(":")[0].strip()
                    param_names.append(param)
            
            # 生成函数定义
            if parameters_str:
                function_def = f"def {function_name}({parameters_str}):\n"
            else:
                function_def = f"def {function_name}():\n"
            
            # 为函数体添加缩进
            function_body = "\n".join("    " + line if line else "" for line in dedented_code.split("\n"))
            new_function = function_def + function_body
            
            # 生成函数调用：使用原代码块中的变量名（如果参数名匹配）
            if param_names:
                # 尝试从原代码块的第一行提取变量值
                # 这是一个简化实现，实际应该更智能地分析代码
                call_params = ", ".join(param_names)  # 默认使用参数名
                function_call = f"{function_name}({call_params})"
            else:
                function_call = f"{function_name}()"
            
            # 替换原代码块
            replacement = function_call
            if base_indent > 0:
                replacement = " " * base_indent + replacement
            
            # 构建新内容
            new_lines = lines[:start_line - 1]  # 保留之前的行
            new_lines.append(new_function + "\n\n")  # 添加新函数
            new_lines.append(replacement + "\n")  # 添加函数调用
            new_lines.extend(lines[end_line:])  # 保留之后的行
            
            with open(path, "w", encoding="utf-8") as file:
                file.write("".join(new_lines))
            
            return f"成功提取函数 {function_name}。\n新函数定义：\n{new_function}\n\n函数调用：\n{replacement}"
        except Exception as e:
            return f"提取函数失败: {e}"


class RenameSymbolTool(Tool):
    """重命名符号工具（跨文件）"""
    
    def _get_description(self) -> str:
        return "重命名代码中的符号（变量、函数、类等），支持跨文件重命名。会搜索工作目录下的所有相关文件并进行替换。"
    
    def _get_parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "old_name": {"type": "string", "description": "旧的符号名称"},
                "new_name": {"type": "string", "description": "新的符号名称"},
                "symbol_type": {"type": "string", "description": "符号类型：function（函数）、class（类）、variable（变量）、all（全部）", "enum": ["function", "class", "variable", "all"], "default": "all"},
                "file_extensions": {"type": "array", "items": {"type": "string"}, "description": "要搜索的文件扩展名列表，例如 ['py', 'js']。如果不指定，则搜索所有代码文件", "default": None},
            },
            "required": ["old_name", "new_name"],
        }
    
    def _is_code_file(self, path: str, extensions: Optional[List[str]]) -> bool:
        """判断是否为代码文件"""
        if extensions:
            return any(path.endswith(f".{ext}") for ext in extensions)
        
        code_extensions = [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".hpp"]
        return any(path.endswith(ext) for ext in code_extensions)
    
    def _should_replace(self, line: str, old_name: str, symbol_type: str) -> bool:
        """判断是否应该替换这一行"""
        # 避免替换字符串中的内容（简单实现）
        if f'"{old_name}"' in line or f"'{old_name}'" in line:
            return False
        
        if symbol_type == "function":
            # 函数定义或调用
            patterns = [
                rf"def\s+{old_name}\s*\(",
                rf"{old_name}\s*\(",
            ]
            return any(re.search(pattern, line) for pattern in patterns)
        elif symbol_type == "class":
            # 类定义或使用
            patterns = [
                rf"class\s+{old_name}\s*[(:]",
                rf"{old_name}\s*\(",
            ]
            return any(re.search(pattern, line) for pattern in patterns)
        elif symbol_type == "variable":
            # 变量赋值或使用
            patterns = [
                rf"\b{old_name}\s*=",
                rf"\b{old_name}\b",
            ]
            return any(re.search(pattern, line) for pattern in patterns)
        else:  # all
            # 匹配所有符号
            return re.search(rf"\b{old_name}\b", line) is not None
    
    def run(self, parameters: Dict[str, Any]) -> str:
        old_name = parameters["old_name"]
        new_name = parameters["new_name"]
        symbol_type = parameters.get("symbol_type", "all")
        file_extensions = parameters.get("file_extensions")
        
        if old_name == new_name:
            return "旧名称和新名称相同，无需重命名"
        
        try:
            modified_files = []
            total_replacements = 0
            
            # 遍历工作目录下的所有文件
            for root, dirs, files in os.walk(self.work_dir):
                # 跳过隐藏目录和常见的不需要搜索的目录
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("__pycache__", "node_modules", ".git")]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    if not self._is_code_file(file_path, file_extensions):
                        continue
                    
                    is_valid, error = self.validate_path(file_path)
                    if not is_valid:
                        continue
                    
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        
                        modified = False
                        new_lines = []
                        
                        for line in lines:
                            if self._should_replace(line, old_name, symbol_type):
                                # 使用单词边界替换
                                new_line = re.sub(rf"\b{old_name}\b", new_name, line)
                                if new_line != line:
                                    modified = True
                                    total_replacements += line.count(old_name) - (line.count(old_name) - new_line.count(new_name))
                                    new_lines.append(new_line)
                                else:
                                    new_lines.append(line)
                            else:
                                new_lines.append(line)
                        
                        if modified:
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write("".join(new_lines))
                            modified_files.append(file_path)
                    except Exception as e:
                        # 跳过无法读取的文件
                        continue
            
            if modified_files:
                return f"成功重命名符号：{old_name} -> {new_name}\n修改了 {len(modified_files)} 个文件，共 {total_replacements} 处替换：\n" + "\n".join(f"  - {f}" for f in modified_files)
            else:
                return f"未找到符号 {old_name}，未进行任何替换"
        except Exception as e:
            return f"重命名符号失败: {e}"

