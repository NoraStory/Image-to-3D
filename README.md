# Image-to-3D

基于豆包 Seed3D-2.0 的图片转 3D 模型工具，提供命令行、Web 界面和 Python SDK 三种使用方式。

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-000000?logo=flask)](https://flask.palletsprojects.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 功能

- 上传图片自动生成带纹理的 3D 模型，支持 1-4 张多视图输入
- 输出 GLB / OBJ / USD / USDZ 四种格式
- 三档网格质量：低（10 万面）、中（50 万面，默认）、高（100 万面）
- CLI 命令行工具与 Flask Web 界面，支持在线预览 GLB / OBJ
- 任务管理：创建、查询、列表、删除、批量转换
- `--auto-process` 自动缩放/裁剪/压缩不合格图片
- 生成完成后自动下载模型文件
- Web 对外监听时强制 Token 鉴权，API Key 脱敏显示

## 图片要求

| 项目 | 要求 |
|------|------|
| 分辨率 | ≤ 4096×4096 |
| 文件大小 | ≤ 10 MB |
| 宽高比 | 0.4 ~ 2.5 |
| 格式 | JPG / JPEG / PNG / WebP / BMP |

## 安装

```bash
git clone https://github.com/NoraStory/Image-to-3D.git
cd Image-to-3D

# 用 uv 安装（推荐）
pip install uv
uv venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv pip install -e .

# 或用 pip
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

## 配置

复制 `.env.example` 为 `.env`，填入你的 API Key：

```ini
ARK_API_KEY=your-api-key-here
FLASK_SECRET_KEY=  # python -c "import secrets; print(secrets.token_hex(32))" 生成
```

也可以通过环境变量 `ARK_API_KEY` 或 `imageto3d config set-key <key>` 设置。

API Key 在 [火山引擎控制台](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey) 获取。

## 使用

### Web 界面

```bash
imageto3d web
```

浏览器打开 http://127.0.0.1:5000 即可。

对外监听需要先设置 `WEB_TOKEN`，否则服务会拒绝启动：

```bash
export WEB_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
imageto3d web --host 0.0.0.0 --port 8080
```

### 命令行

```bash
# 单张转换并下载
imageto3d create --image-file image.jpg --wait --output model.glb

# 用图片 URL
imageto3d create --image-url https://example.com/image.jpg

# 指定质量和格式
imageto3d create --image-file image.jpg --subdivision-level high --file-format obj

# 查询任务
imageto3d get <task_id>
imageto3d get <task_id> --output model.glb

# 列出任务
imageto3d list
imageto3d list --status succeeded --page 2 --size 20

# 删除任务
imageto3d delete <task_id>

# 批量转换
imageto3d batch ./images --output-dir outputs --concurrency 2 --auto-process --wait
```

### Python SDK

```python
from imageto3d import Seed3DClient

client = Seed3DClient(api_key="your-api-key")

result = client.create_task(
    image_url="https://example.com/image.jpg",
    subdivision_level="high",
    file_format="glb",
)

task = client.wait_for_completion(task_id=result.id, timeout=300, poll_interval=5)
print(task.content.file_url)
```

## 参数

### `--subdivision-level`

| 值 | 面数 | 说明 |
|----|------|------|
| `low` | 100,000 | 快速预览 |
| `medium` | 500,000 | 默认 |
| `high` | 1,000,000 | 高精度 |

### `--file-format`

| 值 | 说明 |
|----|------|
| `glb` | 默认 |
| `obj` | Wavefront OBJ |
| `usd` | Universal Scene Description |
| `usdz` | iOS / visionOS 预览 |

## 项目结构

```
imageto3d/
├── cli.py            # 命令行入口
├── client.py         # API 客户端
├── config.py         # 配置与密钥管理
├── storage.py        # 本地任务存储
├── utils.py          # 图片校验、下载等工具函数
├── web.py            # Flask Web 应用
├── static/
│   └── viewer.js     # 3D 预览
└── templates/
    └── index.html
examples/             # 示例代码
tests/                # 测试
```

## 安全

- 密钥通过环境变量或 `~/.imageto3d/config.json`（0600 权限）管理，`.env` 不进入版本控制
- CLI 输出对 API Key 做掩码处理，仅显示首尾几位
- Web 对外监听强制 `WEB_TOKEN` 鉴权，用 `hmac.compare_digest` 做常量时间比较
- 未启用 Token 时通过自定义请求头校验防 CSRF
- 非回环地址且无 Token 时拒绝启动
- 处理图片 URL 时剥离 `user:pass@` 凭据

## 开发

```bash
pip install -e ".[dev]"
pytest
ruff check imageto3d/
ruff format imageto3d/
```

## 相关文档

- [豆包 Seed3D 模型文档](https://www.volcengine.com/docs/82379/1856293)
- [火山引擎 API 控制台](https://console.volcengine.com/ark/)
- [获取 API Key](https://console.volcengine.com/ark/region:ark+cn-beijing/apiKey)

## 许可证

[MIT](LICENSE)
