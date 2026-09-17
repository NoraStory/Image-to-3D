# 项目结构说明

```
Imageto3D/
├── imageto3d/              # 主应用包
│   ├── __init__.py         # 包初始化
│   ├── client.py           # Doubao-Seed3D API 客户端
│   ├── cli.py              # 命令行接口实现
│   ├── web.py              # Flask Web 应用
│   ├── utils.py            # 工具函数（图片验证、文件下载）
│   ├── templates/          # Web 模板
│   │   └── index.html      # Web 界面主页
│   └── static/             # 静态资源（可扩展）
│
├── examples/               # 示例脚本
│   ├── quickstart.py       # 快速开始示例
│   ├── basic_usage.py      # 基本功能演示
│   ├── local_image.py      # 本地图片转换示例
│   └── batch_conversion.py # 批量转换示例
│
├── tests/                  # 测试文件
│   ├── __init__.py
│   └── test_client.py      # 客户端单元测试
│
├── .env                    # 环境变量（包含API Key，已配置）
├── .env.example            # 环境变量示例
├── .gitignore              # Git 忽略文件
├── pyproject.toml          # 项目配置和依赖
├── README.md               # 项目说明文档
├── GUIDE.md                # 详细使用指南
├── start_web.sh            # Linux/Mac 启动脚本
└── start_web.bat           # Windows 启动脚本
```

## 核心文件说明

### imageto3d/client.py
API 客户端核心实现，包含：
- `Seed3DClient` 类：封装所有 API 操作
- `create_task()`: 创建 3D 生成任务
- `get_task()`: 查询任务状态
- `list_tasks()`: 列出任务
- `delete_task()`: 删除任务
- `wait_for_completion()`: 等待任务完成

### imageto3d/cli.py
命令行工具实现，提供子命令：
- `create`: 创建新任务
- `get`: 查询任务详情
- `list`: 列出任务列表
- `delete`: 删除任务
- `web`: 启动 Web 服务器

### imageto3d/web.py
Flask Web 应用，提供 REST API：
- `POST /api/convert`: 创建转换任务
- `GET /api/status/<task_id>`: 查询任务状态
- `GET /api/tasks`: 列出任务
- `DELETE /api/delete/<task_id>`: 删除任务

### imageto3d/utils.py
工具函数：
- `validate_image()`: 验证图片是否符合 API 要求
- `get_image_info()`: 获取图片信息
- `download_file()`: 下载文件

### imageto3d/templates/index.html
现代化 Web 界面：
- 深色主题设计
- 响应式布局
- 实时任务状态更新
- 拖拽上传支持

## 依赖说明

### 核心依赖
- `volcengine-python-sdk[ark]`: 火山引擎 SDK
- `flask`: Web 框架
- `pillow`: 图片处理
- `requests`: HTTP 请求

### 开发依赖
- `pytest`: 测试框架

## 配置文件

### pyproject.toml
使用现代 Python 项目配置：
- 项目元数据
- 依赖管理
- 命令行入口点定义

### .env
环境变量配置：
```
ARK_API_KEY=your_api_key_here
```

## 使用方式

### 1. 安装
```bash
uv venv
source .venv/Scripts/activate  # Windows
uv pip install -e .
```

### 2. Web 界面
```bash
start_web.bat  # Windows
./start_web.sh # Linux/Mac
```

### 3. 命令行
```bash
imageto3d create --image-file image.jpg --wait --output model.glb
```

### 4. Python API
```python
from imageto3d.client import Seed3DClient

client = Seed3DClient()
result = client.create_task(image_url="...")
task = client.wait_for_completion(result.id)
```

## 扩展建议

### 添加新功能
1. 在 `client.py` 中添加新的 API 方法
2. 在 `cli.py` 中添加对应的命令
3. 在 `web.py` 中添加对应的路由
4. 在 `tests/` 中添加测试

### 自定义界面
1. 修改 `templates/index.html` 改变 UI
2. 在 `static/` 中添加 CSS/JS 资源
3. 在 `web.py` 中添加新路由

### 集成到其他项目
直接导入 `Seed3DClient` 类使用：
```python
from imageto3d.client import Seed3DClient
```

## 文件夹说明

### uploads/
Web 应用上传的图片临时存储（自动创建）

### outputs/
下载的 3D 模型文件存储（自动创建）

### .venv/
Python 虚拟环境（不提交到版本控制）

## 开发建议

### 代码风格
- 遵循 PEP 8
- 使用类型提示
- 添加详细的文档字符串

### 测试
```bash
pytest tests/
```

### 格式化
```bash
black imageto3d/
```

### 类型检查
```bash
mypy imageto3d/
```
