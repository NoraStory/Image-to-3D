# 更新日志

本项目的所有重要更改都将记录在此文件中。

## [0.3.0] - 2026-08-15

### 安全修复
- 🔐 清理示例/文档/测试脚本中的硬编码 API Key
- 🔐 Web 非本机监听强制要求 `WEB_TOKEN`；无令牌时增加 CSRF 头校验
- 🔐 远程图片 URL 预检增加 SSRF 防护（仅允许公共 http/https 地址）
- 🔐 `/api/tasks` 不再暴露服务器内部绝对路径
- 🔐 Web 任务状态/删除/回调仅允许操作本地任务库中已有的任务
- 🔐 用户配置文件以 0600 权限保存，前端 HTML 动态内容全部转义

### 功能升级
- ✅ 修复 `.env` 加载链路：`Seed3DClient` 现在支持 `.env` / 环境变量 / 用户配置
- ✅ `--auto-process` 真正生效，支持缩放、裁剪与超限压缩
- ✅ CLI 增加 `--model`、`--no-draft`、`--no-auto-process` 与参数范围校验
- ✅ `batch` 输出文件名防冲突、并发/超时校验、自动修复支持
- ✅ Web 前端支持多图、拖拽、令牌输入、本地缓存下载链接、任务删除
- ✅ Web 内嵌 3D 预览（GLB/OBJ，USDZ 在 iOS 上预览）
- ✅ 自动解包 Seed3D 返回的 ZIP 容器（修复 Blender 报 `jsonerror: utf-8` 的问题）
- ✅ `python -m imageto3d` 可用，版本号统一为 0.3.0
- ✅ SQLite 增加 WAL / busy_timeout / 简单迁移

### 修复
- 🐛 修复 `examples/basic_usage.py` 使用 `items` 字段
- 🐛 修复 `start_web.sh` 在 Linux/macOS 上的虚拟环境路径
- 🐛 修复单测大小写匹配失败问题

## [0.1.0] - 2026-08-13

### 新增功能
- ✨ 初始版本发布
- 🎨 现代化 Web 界面，深色主题设计
- 💻 完整的命令行工具支持
- 🔄 图片转 3D 模型核心功能
- 📦 支持多种输出格式（GLB, OBJ, USD, USDZ）
- ⚙️ 三档网格质量控制（低/中/高）
- 🖼️ 支持本地图片和 URL 两种输入方式
- ✅ 自动图片验证（分辨率、大小、宽高比）
- 📊 实时任务状态跟踪
- 📥 自动下载完成的 3D 模型
- 🔍 任务管理功能（创建、查询、列出、删除）

### API 功能
- `create_task()` - 创建 3D 生成任务
- `get_task()` - 查询任务状态
- `list_tasks()` - 列出任务列表
- `delete_task()` - 删除任务
- `wait_for_completion()` - 等待任务完成

### 命令行工具
- `imageto3d create` - 创建新任务
- `imageto3d get` - 查询任务详情
- `imageto3d list` - 列出任务
- `imageto3d delete` - 删除任务
- `imageto3d web` - 启动 Web 服务器

### Web 界面功能
- 📤 拖拽上传支持
- 🎯 参数配置界面
- 📱 响应式设计
- 🔄 自动刷新任务列表
- 💾 一键下载 3D 模型

### 文档
- 📖 完整的 README.md
- 📚 详细的使用指南 (GUIDE.md)
- 🏗️ 项目结构说明 (STRUCTURE.md)
- 💡 丰富的示例代码
  - 快速开始示例
  - 基本功能演示
  - 本地图片处理
  - 批量转换脚本

### 工具和脚本
- 🚀 快速启动脚本（Windows/Linux/Mac）
- 🧪 单元测试框架
- 📝 示例代码集合

### 技术栈
- Python 3.9+
- Flask 3.x (Web 框架)
- Pillow (图片处理)
- Volcengine SDK (API 客户端)
- uv (包管理)

### 支持的功能
- ✅ Doubao-Seed3D-2.0 模型
- ✅ 图片格式：JPG, JPEG, PNG, WebP, BMP
- ✅ 最大分辨率：4096×4096
- ✅ 最大文件大小：10MB
- ✅ 宽高比范围：0.4 ~ 2.5

### 已知限制
- 单次只能处理一张图片
- 处理时间依赖于图片复杂度（通常 2-5 分钟）
- API 调用受配额限制

## 未来计划

### [0.2.0] - 计划中
- [ ] 添加进度条显示
- [ ] 支持批量上传
- [ ] 添加模型预览功能
- [ ] 支持更多输入格式
- [ ] 优化大文件处理
- [ ] 添加历史记录功能
- [ ] 支持模型缓存

### [0.3.0] - 计划中
- [ ] 添加用户认证
- [ ] 数据库存储任务
- [ ] RESTful API 文档
- [ ] Docker 支持
- [ ] 生产环境部署指南
- [ ] 性能监控

## 贡献

欢迎提交 Issue 和 Pull Request！

## 版权

MIT License
