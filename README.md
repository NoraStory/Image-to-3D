<div align="center">

# 🖼️ → 🧊 Image-to-3D

**基于豆包 Seed3D-2.0 的图片转 3D 模型工具**
CLI · Web UI · Python SDK 三合一

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-261230?logo=ruff)](https://docs.astral.sh/ruff/)

</div>

---

## ✨ 功能特性

| 特性 | 说明 |
|------|------|
| 📷 **图片转 3D** | 上传图片，自动生成带纹理的 3D 模型 |
| 🖼️ **多视图输入** | 支持 1–4 张图片（CLI / Web / Python API） |
| 🎨 **多格式输出** | GLB · OBJ · USD · USDZ |
| ⚙️ **网格质量控制** | 三档可选：低（10 万面）/ 中（50 万面）/ 高（100 万面） |
| 💻 **双模式** | 命令行工具 + Web 界面，开箱即用 |
| 🔄 **任务管理** | 创建 · 查询 · 列出 · 删除 · 批量转换 |
| 🩹 **自动修复** | `--auto-process` 自动缩放 / 裁剪 / 压缩不合格图片 |
| 📦 **自动下载** | 生成完成后自动下载模型文件 |
| 🖥️ **在线预览** | Web 界面直接预览 GLB / OBJ；USDZ 支持 iOS 预览 |
| 🔐 **安全优先** | Token 鉴权 · 非回环地址强制校验 · 密钥脱敏显示 |

## 📋 图片要求

| 项目 | 要求 |
|------|------|
| 分辨率 | ≤ 4096 × 4096 像素 |
| 文件大小 | ≤ 10 MB |
| 宽高比 | 0.4 ~ 2.5 |
| 支持格式 | JPG · JPEG · PNG · WebP · BMP |

## 🚀 快速开始

### 前置要求

- **Python** 3.9+
- **[uv](https://github.com/astral-sh/uv)**（推荐）或 pip
- **豆包 / 火山引擎 ARK API Key** — [在此获取](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)

### 安装

```bash
git clone https://github.com/NoraStory/Image-to-3D.git
cd Image-to-3D

# 使用 uv（推荐）
pip install uv
uv venv
# 激活虚拟环境
#   Linux / macOS:
source .venv/bin/activate
#   Windows PowerShell:
.venv\Scripts\Activate.ps1
uv pip install -e .

# 或使用 pip
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

### 配置 API Key

复制环境变量模板并填入你的 API Key：

```bash
cp .env.example .env
```

编辑 `.env`：

```ini
ARK_API_KEY=your-api-key-here
FLASK_SECRET_KEY=  # 用 python -c "import secrets; print(secrets.token_hex(32))" 生成
```

> 💡 也可以通过环境变量或 `imageto3d config set-key <key>` 设置，Key 会存储在 `~/.imageto3d/config.json`（仅文件所有者可读）。

### 启动 Web 界面

```bash
imageto3d web
```

浏览器访问 **http://127.0.0.1:5000** 即可使用。

> ⚠️ **对外监听安全提示**：以 `--host 0.0.0.0` 监听时，**必须**先设置 `WEB_TOKEN`，否则服务拒绝启动：
> ```bash
> export WEB_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
> imageto3d web --host 0.0.0.0 --port 8080
> ```

### 命令行使用

```bash
# 创建转换任务（本地图片）
imageto3d create --image-file path/to/image.jpg

# 等待完成并下载
imageto3d create --image-file image.jpg --wait --output model.glb

# 查询任务状态
imageto3d get <task_id>

# 列出任务
imageto3d list --status succeeded

# 删除任务
imageto3d delete <task_id>

# 批量转换目录下所有图片
imageto3d batch ./images --output-dir outputs --concurrency 2 --auto-process --wait
```

### Python SDK

```python
from imageto3d import Seed3DClient

client = Seed3DClient(api_key="your-api-key")

# 创建任务
result = client.create_task(
    image_url="https://example.com/image.jpg",
    subdivision_level="high",
    file_format="glb",
)
print(f"Task ID: {result.id}")

# 等待完成
task = client.wait_for_completion(task_id=result.id, timeout=300, poll_interval=5)
print(f"Output URL: {task.content.file_url}")
```

## 📖 参数说明

### 网格质量 (`--subdivision-level`)

| 等级 | 面数 | 适用场景 |
|------|------|----------|
| `low` | 100,000 | 快速预览、移动端 |
| `medium` | 500,000 | 通用场景（默认） |
| `high` | 1,000,000 | 高精度渲染、3D 打印 |

### 输出格式 (`--file-format`)

| 格式 | 说明 |
|------|------|
| `glb` | GL Transmission Binary（默认） |
| `obj` | Wavefront OBJ |
| `usd` | Universal Scene Description |
| `usdz` | USD ZIP Archive（iOS / visionOS 预览） |

## 📁 项目结构

```
Image-to-3D/
├── imageto3d/                # 核心 Python 包
│   ├── __init__.py
│   ├── __main__.py           # python -m imageto3d 入口
│   ├── cli.py                # 命令行接口
│   ├── client.py             # API 客户端
│   ├── config.py             # 配置与密钥管理
│   ├── storage.py            # 本地任务存储
│   ├── utils.py              # 工具函数（图片校验、下载等）
│   ├── web.py                # Flask Web 应用
│   ├── static/
│   │   └── viewer.js         # 3D 模型预览脚本
│   └── templates/
│       └── index.html        # Web 界面
├── examples/                 # 使用示例
├── tests/                    # 测试
├── .env.example              # 环境变量模板
├── pyproject.toml            # 项目配置
├── start_web.sh              # Linux/macOS 启动脚本
├── start_web.bat             # Windows 启动脚本
└── README.md
```

## 🔒 安全与隐私

本项目高度重视安全与隐私：

- **密钥隔离**：所有密钥通过环境变量或本地配置文件管理，`.env` 已在 `.gitignore` 中排除，**不会**进入版本控制。
- **密钥脱敏**：CLI 输出中对 API Key 做掩码处理，仅显示前 6 位和末 4 位。
- **Token 鉴权**：Web 服务对外监听时强制要求 `WEB_TOKEN`，并使用 `hmac.compare_digest` 进行常量时间比较，防止时序攻击。
- **CSRF 防护**：未启用 Token 时自动要求自定义请求头校验，防止跨站请求伪造。
- **非回环地址保护**：检测到 `0.0.0.0` 等非回环监听且未设置 Token 时，服务拒绝启动。
- **配置文件权限**：`~/.imageto3d/config.json` 写入时自动设置 `0600` 权限（仅文件所有者可读写）。
- **URL 凭据清理**：处理图片 URL 时自动剥离 `userinfo`（`user:pass@`）部分。

## 🛠️ 开发

```bash
# 安装开发依赖
uv pip install -e ".[dev]"
# 或 pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check imageto3d/

# 格式化
ruff format imageto3d/
```

## 📜 许可证

[MIT License](LICENSE) © 2026 NoraStory

## 📚 相关链接

- [豆包 Seed3D 模型文档](https://www.volcengine.com/docs/82379/1856293)
- [火山引擎 API 控制台](https://console.volcengine.com/ark/)
- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request
