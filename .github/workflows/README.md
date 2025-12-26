# GitHub Actions 打包说明

本项目使用 GitHub Actions 自动为多个平台打包二进制文件。

## 🚀 快速开始

### 方式一：推送版本标签（推荐）

```bash
# 1. 创建版本标签
git tag v1.0.0

# 2. 推送标签到 GitHub
git push origin v1.0.0
```

推送标签后，GitHub Actions 会自动：
- 为 Windows、macOS、Linux 三个平台打包
- 创建 GitHub Release
- 上传可执行文件到 Release

### 方式二：手动触发

1. 打开 GitHub 仓库页面
2. 点击 "Actions" 标签
3. 选择左侧的 "Build Binaries" 工作流
4. 点击右上角 "Run workflow"
5. 输入版本号（如 `1.0.0`）
6. 点击 "Run workflow" 按钮

## 📦 下载打包结果

### 从 Artifacts 下载

1. 在 Actions 页面找到对应的运行记录
2. 点击进入详情页
3. 滚动到底部，在 "Artifacts" 部分下载：
   - `react-agent-linux-1.0.0` - Linux 版本
   - `react-agent-windows-1.0.0` - Windows 版本
   - `react-agent-macos-1.0.0` - macOS 版本

### 从 Releases 下载（使用标签触发时）

1. 在仓库页面点击 "Releases"
2. 找到对应的版本（如 `v1.0.0`）
3. 直接下载对应平台的可执行文件

## 🔧 工作流配置

工作流文件位于 `.github/workflows/build.yml`，主要配置：

- **触发条件**：
  - 推送版本标签（`v*` 格式）
  - 手动触发（workflow_dispatch）

- **支持平台**：
  - Ubuntu (Linux)
  - Windows
  - macOS

- **Python 版本**：3.10

- **打包工具**：PyInstaller

## 📝 版本号规范

建议使用语义化版本号：
- `v1.0.0` - 主版本.次版本.修订版本
- `v1.0.1` - 修复版本
- `v1.1.0` - 功能更新
- `v2.0.0` - 重大更新

## ⚠️ 注意事项

1. **首次运行**：如果仓库是私有的，需要确保 GitHub Actions 已启用
2. **构建时间**：三个平台并行构建，通常需要 5-10 分钟
3. **文件大小**：每个二进制文件约 20-50MB
4. **Artifacts 保留**：默认保留 30 天
5. **Release 创建**：只有使用标签触发时才会自动创建 Release

## 🐛 故障排除

### 构建失败

1. 检查 Actions 日志，查看具体错误信息
2. 确认 `requirements.txt` 中的依赖是否正确
3. 确认 `react_agent.spec` 配置是否正确

### 找不到 Artifacts

1. 确认构建是否成功完成
2. 检查 Artifacts 是否已过期（超过 30 天）
3. 尝试重新触发构建

### Release 未创建

1. 确认是否使用标签触发（不是手动触发）
2. 确认标签格式是否正确（`v*` 格式）
3. 检查是否有权限创建 Release

## 📚 相关资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [PyInstaller 文档](https://pyinstaller.org/)
- [语义化版本](https://semver.org/)

