# -*- coding: utf-8 -*-
"""自动更新模块"""

import os
import sys
import platform
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import urllib.request
import urllib.error

from __init__ import __version__


class Updater:
    """自动更新器"""
    
    # GitHub 仓库信息
    GITHUB_REPO = "leyen-me/ReAct-Agent"
    GITHUB_API_BASE = "https://api.github.com/repos"
    
    def __init__(self):
        self.current_version = __version__
        self.platform = self._detect_platform()
        self.binary_name = self._get_binary_name()
    
    def _detect_platform(self) -> str:
        """检测当前平台"""
        system = platform.system().lower()
        if system == "darwin":
            return "macos"
        elif system == "linux":
            return "linux"
        elif system == "windows":
            return "windows"
        else:
            raise ValueError(f"不支持的平台: {system}")
    
    def _get_binary_name(self) -> str:
        """获取当前平台的二进制文件名"""
        if self.platform == "windows":
            return "ask.exe"
        return "ask"
    
    def get_latest_version(self) -> Optional[str]:
        """从 GitHub Releases 获取最新版本号"""
        try:
            url = f"{self.GITHUB_API_BASE}/{self.GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "ReAct-Agent-Updater")
            
            # 创建 SSL 上下文（处理证书验证问题）
            import ssl
            ctx = ssl.create_default_context()
            # 如果是开发环境，可以跳过证书验证（仅用于测试）
            if not getattr(sys, 'frozen', False):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                data = json.loads(response.read())
                # 移除 'v' 前缀（如果有）
                tag_name = data.get("tag_name", "")
                return tag_name.lstrip("v")
        except urllib.error.URLError as e:
            if "SSL" in str(e) or "certificate" in str(e).lower():
                print(f"SSL 证书验证失败，请检查网络连接或系统证书配置")
            else:
                print(f"网络错误: {e}")
            return None
        except Exception as e:
            print(f"获取最新版本失败: {e}")
            return None
    
    def compare_versions(self, version1: str, version2: str) -> int:
        """比较两个版本号
        返回: -1 (v1 < v2), 0 (v1 == v2), 1 (v1 > v2)
        """
        def version_tuple(v):
            # 处理版本号，支持 1.0.0 格式
            parts = v.split(".")
            return tuple(map(int, parts))
        
        try:
            v1_tuple = version_tuple(version1)
            v2_tuple = version_tuple(version2)
            
            if v1_tuple < v2_tuple:
                return -1
            elif v1_tuple > v2_tuple:
                return 1
            return 0
        except Exception as e:
            print(f"版本比较失败: {e}")
            return 0
    
    def get_download_url(self, version: str) -> Optional[str]:
        """获取指定版本的下载 URL"""
        try:
            url = f"{self.GITHUB_API_BASE}/{self.GITHUB_REPO}/releases/tags/v{version}"
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/vnd.github.v3+json")
            req.add_header("User-Agent", "ReAct-Agent-Updater")
            
            # 创建 SSL 上下文
            import ssl
            ctx = ssl.create_default_context()
            if not getattr(sys, 'frozen', False):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
                data = json.loads(response.read())
                assets = data.get("assets", [])
                
                # 根据平台查找对应的二进制文件
                # GitHub Actions 打包的文件名格式: ask-{version} 或 ask-{version}.exe
                target_suffix = ".exe" if self.platform == "windows" else ""
                platform_keywords = {
                    "windows": ["windows", "win"],
                    "macos": ["macos", "mac", "darwin"],
                    "linux": ["linux", "ubuntu"]
                }
                
                keywords = platform_keywords.get(self.platform, [])
                
                # 优先查找包含平台关键词的文件
                for asset in assets:
                    name = asset.get("name", "").lower()
                    if any(kw in name for kw in keywords):
                        if self.platform == "windows" and name.endswith(".exe"):
                            return asset.get("browser_download_url")
                        elif self.platform != "windows" and not name.endswith(".exe"):
                            return asset.get("browser_download_url")
                
                # 如果没找到，尝试匹配 ask-{version} 格式
                for asset in assets:
                    name = asset.get("name", "")
                    if f"ask-{version}" in name or f"ask-{version}.exe" in name:
                        # 排除其他平台的文件
                        if self.platform == "windows":
                            # Windows: 匹配 .exe 文件，优先包含 windows 关键词的，但如果没有也接受
                            if name.endswith(".exe"):
                                # 如果文件名就是 ask-{version}.exe 格式，直接匹配
                                if name == f"ask-{version}.exe":
                                    return asset.get("browser_download_url")
                                # 或者包含 windows 关键词
                                elif "windows" in name.lower() or "win" in name.lower():
                                    return asset.get("browser_download_url")
                        else:
                            if not name.endswith(".exe"):
                                if self.platform == "macos" and ("macos" in name.lower() or "mac" in name.lower()):
                                    return asset.get("browser_download_url")
                                elif self.platform == "linux" and "linux" in name.lower():
                                    return asset.get("browser_download_url")
                
                # 最后尝试：根据平台选择合适的文件
                matching_assets = [a for a in assets if f"ask-{version}" in a.get("name", "")]
                if len(matching_assets) == 1:
                    return matching_assets[0].get("browser_download_url")
                elif len(matching_assets) > 1:
                    # 如果有多个文件，根据平台选择
                    if self.platform == "windows":
                        # 优先选择 .exe 文件
                        exe_assets = [a for a in matching_assets if a.get("name", "").endswith(".exe")]
                        if exe_assets:
                            # 优先选择包含 windows 关键词的，否则选择第一个
                            windows_asset = next((a for a in exe_assets if "windows" in a.get("name", "").lower() or "win" in a.get("name", "").lower()), None)
                            if windows_asset:
                                return windows_asset.get("browser_download_url")
                            # 如果文件名就是 ask-{version}.exe，也使用它
                            exact_match = next((a for a in exe_assets if a.get("name", "") == f"ask-{version}.exe"), None)
                            if exact_match:
                                return exact_match.get("browser_download_url")
                            # 否则使用第一个 .exe 文件
                            return exe_assets[0].get("browser_download_url")
                    else:
                        # 非 Windows 平台，排除 .exe 文件
                        non_exe_assets = [a for a in matching_assets if not a.get("name", "").endswith(".exe")]
                        if non_exe_assets:
                            return non_exe_assets[0].get("browser_download_url")
                    
        except urllib.error.URLError as e:
            print(f"网络错误: {e}")
        except Exception as e:
            print(f"获取下载链接失败: {e}")
        return None
    
    def download_file(self, url: str, dest_path: Path) -> bool:
        """下载文件"""
        try:
            print(f"正在下载: {url}")
            req = urllib.request.Request(url)
            req.add_header("Accept", "application/octet-stream")
            req.add_header("User-Agent", "ReAct-Agent-Updater")
            
            # 创建 SSL 上下文
            import ssl
            ctx = ssl.create_default_context()
            if not getattr(sys, 'frozen', False):
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded = 0
                
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            percent = (downloaded / total_size) * 100
                            print(f"\r下载进度: {percent:.1f}% ({downloaded // 1024 // 1024}MB/{total_size // 1024 // 1024}MB)", end="", flush=True)
                print()  # 换行
                return True
        except Exception as e:
            print(f"\n下载失败: {e}")
            return False
    
    def get_binary_path(self) -> Optional[Path]:
        """获取当前二进制文件的路径"""
        # 如果是打包后的二进制，获取可执行文件路径
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后的路径
            return Path(sys.executable)
        else:
            # 开发环境，尝试从 PATH 中找到
            import shutil
            binary_path = shutil.which(self.binary_name)
            if binary_path:
                return Path(binary_path)
            # 如果找不到，返回当前脚本所在目录
            return Path(__file__).parent / self.binary_name
        return None
    
    def update(self, force: bool = False) -> Tuple[bool, str]:
        """执行更新
        
        Args:
            force: 是否强制更新（即使版本相同）
            
        Returns:
            (是否成功, 消息)
        """
        print(f"当前版本: {self.current_version}")
        print(f"平台: {self.platform}")
        
        latest_version = self.get_latest_version()
        if not latest_version:
            return False, "无法获取最新版本信息，请检查网络连接"
        
        print(f"最新版本: {latest_version}")
        
        # 比较版本
        if not force:
            comparison = self.compare_versions(self.current_version, latest_version)
            if comparison >= 0:
                return False, f"当前已是最新版本 ({self.current_version})"
        
        # 获取下载链接
        download_url = self.get_download_url(latest_version)
        if not download_url:
            return False, f"无法找到版本 {latest_version} 的下载链接，请检查 GitHub Releases"
        
        print(f"下载链接: {download_url}")
        
        # 获取当前二进制路径
        current_binary = self.get_binary_path()
        if not current_binary:
            return False, "无法确定当前二进制文件路径"
        
        print(f"当前二进制路径: {current_binary}")
        
        # 如果是开发环境，提示用户
        if not getattr(sys, 'frozen', False):
            print("⚠️  检测到开发环境，无法自动更新二进制文件")
            print(f"请手动下载: {download_url}")
            return False, "开发环境不支持自动更新"
        
        # 下载到当前二进制文件所在目录
        download_dir = current_binary.parent
        temp_file = download_dir / f"ask-{latest_version}.tmp"
        
        if not self.download_file(download_url, temp_file):
            return False, "下载失败"
        
        # 设置执行权限（Linux/macOS）
        if self.platform != "windows":
            os.chmod(temp_file, 0o755)
        
        # 备份当前文件
        backup_path = current_binary.parent / f"{current_binary.name}.backup"
        try:
            if current_binary.exists():
                shutil.copy2(current_binary, backup_path)
                print(f"已备份当前版本到: {backup_path}")
        except Exception as e:
            return False, f"备份失败: {e}"
        
        # 替换文件
        try:
            # Windows 需要先删除原文件
            if self.platform == "windows":
                if current_binary.exists():
                    current_binary.unlink()
            shutil.move(temp_file, current_binary)
            print(f"✅ 更新成功！新版本: {latest_version}")
            print(f"   备份文件: {backup_path}")
            return True, f"已更新到版本 {latest_version}"
        except PermissionError:
            # 权限不足，保留临时文件让用户手动处理
            print(f"\n⚠️  权限不足，无法自动替换")
            print(f"✅ 新版本已下载完成！")
            print(f"\n📥 下载位置: {temp_file}")
            print(f"📁 当前 ask.exe 位置: {current_binary}")
            print(f"\n📝 请按以下步骤手动更新:")
            print(f"   1. 以管理员身份运行 PowerShell 或 CMD")
            print(f"   2. 将下载的文件重命名为: ask.exe")
            if self.platform == "windows":
                print(f"   3. 替换 {current_binary} 文件")
            else:
                print(f"   3. 替换 {current_binary} 文件并设置执行权限: chmod +x ask")
            print(f"\n💡 提示: 也可以直接复制下载的文件到 {current_binary.parent} 目录并重命名为 ask.exe")
            return True, f"新版本已下载到 {temp_file}，请手动替换"
        except OSError as e:
            # 检查是否是文件被占用错误
            error_msg = str(e).lower()
            if "被另一个进程使用" in str(e) or "being used by another process" in error_msg or "cannot access" in error_msg:
                # 文件被占用，保留临时文件让用户手动处理
                print(f"\n⚠️  检测到文件被占用，无法自动替换")
                print(f"✅ 新版本已下载完成！")
                print(f"\n📥 下载位置: {temp_file}")
                print(f"📁 当前 ask.exe 位置: {current_binary}")
                print(f"\n📝 请按以下步骤手动更新:")
                print(f"   1. 关闭所有正在运行的 ask.exe 程序")
                print(f"   2. 将下载的文件重命名为: ask.exe")
                if self.platform == "windows":
                    print(f"   3. 替换 {current_binary} 文件")
                else:
                    print(f"   3. 替换 {current_binary} 文件并设置执行权限: chmod +x ask")
                print(f"\n💡 提示: 也可以直接复制下载的文件到 {current_binary.parent} 目录并重命名为 ask.exe")
                
                return True, f"新版本已下载到 {temp_file}，请手动替换"
            else:
                # 其他错误，恢复备份
                try:
                    if backup_path.exists() and not current_binary.exists():
                        shutil.move(backup_path, current_binary)
                        print("已恢复备份文件")
                except:
                    pass
                return False, f"更新失败: {e}"
        except Exception as e:
            # 恢复备份
            try:
                if backup_path.exists() and not current_binary.exists():
                    shutil.move(backup_path, current_binary)
                    print("已恢复备份文件")
            except:
                pass
            return False, f"更新失败: {e}"


def check_update() -> None:
    """检查更新（非阻塞）"""
    try:
        updater = Updater()
        latest_version = updater.get_latest_version()
        
        if latest_version:
            comparison = updater.compare_versions(updater.current_version, latest_version)
            if comparison < 0:
                print(f"\n⚠️  发现新版本: {latest_version} (当前: {updater.current_version})")
                print(f"   运行 'ask --update' 或 'ask update' 进行更新\n")
    except:
        pass  # 更新检查失败不影响主程序运行


if __name__ == "__main__":
    updater = Updater()
    success, message = updater.update()
    print(message)
    sys.exit(0 if success else 1)

