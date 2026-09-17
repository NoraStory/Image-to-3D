# Image to 3D - 使用指南

## 快速开始

### 1. Web 界面（推荐新手使用）

最简单的方式是使用 Web 界面：

```bash
# Windows
start_web.bat

# Linux/Mac
./start_web.sh
```

然后在浏览器中打开 http://127.0.0.1:5000

#### Web 界面功能：

1. **上传图片**
   - 支持本地文件上传
   - 支持图片 URL
   - 自动验证图片尺寸和格式

2. **配置参数**
   - 网格质量：低/中/高
   - 输出格式：GLB/OBJ/USD/USDZ

3. **任务管理**
   - 实时查看转换状态
   - 自动刷新任务列表
   - 完成后直接下载

### 2. 命令行工具

命令行工具适合批量处理和脚本自动化。

#### 基本用法

```bash
# 激活虚拟环境
source .venv/Scripts/activate  # Windows
source .venv/bin/activate       # Linux/Mac

# 使用图片 URL
imageto3d create --image-url https://example.com/image.jpg

# 使用本地图片
imageto3d create --image-file path/to/image.jpg

# 等待完成并自动下载
imageto3d create --image-file image.jpg --wait --output model.glb

# 指定参数
imageto3d create \
  --image-file image.jpg \
  --subdivision-level high \
  --file-format obj \
  --wait \
  --output model.obj
```

#### 查询任务

```bash
# 获取任务状态
imageto3d get <task_id>

# 下载完成的模型
imageto3d get <task_id> --output model.glb
```

#### 管理任务

```bash
# 列出所有任务
imageto3d list

# 查看成功的任务
imageto3d list --status succeeded

# 删除任务
imageto3d delete <task_id>

# 批量转换目录（支持 --recursive / --skip-existing 断点续跑）
imageto3d batch ./images --output-dir outputs --concurrency 2

# 自动修复不符合要求的图片
imageto3d batch ./images --auto-process --wait
```

> Web 安全提示：`imageto3d web --host 0.0.0.0` 前请设置 `WEB_TOKEN`；
> 未设置时服务默认只允许绑定本机回环地址。Web 页面启动后会提示输入令牌。

### 3. Python API

适合集成到自己的项目中。

#### 最简示例

```python
from imageto3d.client import Seed3DClient

client = Seed3DClient()

# 创建任务
result = client.create_task(
    image_url="https://example.com/image.jpg",
    subdivision_level="medium",
    file_format="glb"
)

# 等待完成
task = client.wait_for_completion(result.id)

print(f"下载链接: {task.content.file_url}")
```

#### 完整示例

查看 `examples/` 目录：

- `quickstart.py` - 快速开始
- `basic_usage.py` - 基本功能演示
- `local_image.py` - 使用本地图片
- `batch_conversion.py` - 批量转换

运行示例：

```bash
python examples/quickstart.py
```

## 参数详解

### 网格质量 (subdivision_level)

决定 3D 模型的多边形面数量，影响模型精细度和文件大小：

| 级别 | 面数 | 适用场景 |
|------|------|----------|
| low | 100,000 | 快速预览、移动端应用 |
| medium | 500,000 | 一般用途、Web 展示 |
| high | 1,000,000 | 高质量渲染、专业制作 |

**建议：**
- 首次测试使用 `medium`
- 移动端或 Web 使用 `low` 或 `medium`
- 专业制作使用 `high`

### 输出格式 (file_format)

| 格式 | 描述 | 适用场景 |
|------|------|----------|
| GLB | GL Transmission Format Binary | Web/移动端，Three.js, Babylon.js |
| OBJ | Wavefront OBJ | 3D 建模软件（Blender, Maya, 3ds Max） |
| USD | Universal Scene Description | 影视制作、Apple 生态系统 |
| USDZ | USD ZIP Archive | iOS AR 应用、Apple 设备 |

**建议：**
- Web 展示：使用 `GLB`
- 3D 编辑：使用 `OBJ`
- iOS AR：使用 `USDZ`
- 影视制作：使用 `USD`

## 图片要求

### 必须满足的条件

1. **分辨率**：≤ 4096×4096 像素
2. **文件大小**：≤ 10MB
3. **宽高比**：0.4 ~ 2.5
4. **格式**：JPG, JPEG, PNG, WebP, BMP

### 图片准备建议

#### ✅ 好的图片

- 主体清晰，背景简单
- 光线均匀，对比度适中
- 包含物体的主要特征
- 单一主体，避免多个物体
- 正面或3/4角度拍摄

#### ❌ 不好的图片

- 模糊、过暗或过曝
- 主体不清晰
- 背景过于复杂
- 极端角度（俯视/仰视）
- 严重遮挡

### 预处理建议

```python
from PIL import Image

# 1. 调整大小（保持宽高比）
img = Image.open("input.jpg")
img.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
img.save("resized.jpg", quality=95)

# 2. 转换格式
img = Image.open("input.webp")
img.save("output.jpg", quality=95)

# 3. 去除背景（需要额外的库）
# 使用 rembg 或其他工具
```

## 常见问题

### 1. API Key 相关

**问题：** `API key is required`

**解决：**
```bash
# 设置环境变量
export ARK_API_KEY="your-api-key"  # Linux/Mac
set ARK_API_KEY=your-api-key       # Windows CMD
$env:ARK_API_KEY="your-api-key"    # Windows PowerShell

# 或在 .env 文件中设置
echo "ARK_API_KEY=your-api-key" > .env
```

### 2. 图片验证失败

**问题：** `Image resolution exceeds 4096x4096 limit`

**解决：** 使用图片编辑工具调整大小

```python
from PIL import Image

img = Image.open("large.jpg")
img.thumbnail((4096, 4096), Image.Resampling.LANCZOS)
img.save("resized.jpg", quality=95)
```

**问题：** `Aspect ratio outside valid range`

**解决：** 裁剪图片使宽高比在 0.4~2.5 之间

### 3. 任务处理

**问题：** 任务一直处于 `queued` 或 `running`

**解决：**
- 图片越复杂，处理时间越长（通常 2-5 分钟）
- 增加超时时间：`--timeout 600`
- 检查 API 配额是否用完

**问题：** 任务 `failed`

**解决：**
- 检查图片是否符合要求
- 查看任务详情：`imageto3d get <task_id>`
- 尝试使用不同的图片或参数

### 4. 下载失败

**问题：** 无法下载生成的 3D 模型

**解决：**
- 检查网络连接
- 输出 URL 有效期可能已过，重新获取
- 直接复制 URL 在浏览器中下载

## 性能优化

### 批量处理优化

```python
import time
from imageto3d.client import Seed3DClient

client = Seed3DClient()
tasks = []

# 1. 快速创建所有任务
for image_url in image_urls:
    result = client.create_task(image_url=image_url)
    tasks.append(result.id)
    time.sleep(1)  # 避免请求过快

# 2. 批量等待（而不是一个一个等）
for task_id in tasks:
    try:
        task = client.wait_for_completion(task_id, timeout=300)
        print(f"完成: {task.content.file_url}")
    except Exception as e:
        print(f"失败: {task_id} - {e}")
```

### 并发处理

```python
from concurrent.futures import ThreadPoolExecutor
from imageto3d.client import Seed3DClient

def process_image(image_url):
    client = Seed3DClient()
    result = client.create_task(image_url=image_url)
    task = client.wait_for_completion(result.id)
    return task.content.file_url

# 使用线程池并发处理
with ThreadPoolExecutor(max_workers=5) as executor:
    results = executor.map(process_image, image_urls)
    for url in results:
        print(f"完成: {url}")
```

## 集成到自己的项目

### Flask Web 应用

```python
from flask import Flask, request, jsonify
from imageto3d.client import Seed3DClient

app = Flask(__name__)
client = Seed3DClient()

@app.route('/convert', methods=['POST'])
def convert():
    image_url = request.json['image_url']
    result = client.create_task(image_url=image_url)
    return jsonify({'task_id': result.id})

@app.route('/status/<task_id>')
def status(task_id):
    task = client.get_task(task_id)
    return jsonify({
        'status': task.status,
        'output': task.content.file_url if task.status == 'succeeded' else None
    })
```

### Django 视图

```python
from django.http import JsonResponse
from imageto3d.client import Seed3DClient

def convert_image(request):
    client = Seed3DClient()
    image_url = request.POST['image_url']
    result = client.create_task(image_url=image_url)
    return JsonResponse({'task_id': result.id})
```

### FastAPI

```python
from fastapi import FastAPI
from imageto3d.client import Seed3DClient

app = FastAPI()
client = Seed3DClient()

@app.post("/convert")
async def convert(image_url: str):
    result = client.create_task(image_url=image_url)
    return {"task_id": result.id}

@app.get("/status/{task_id}")
async def status(task_id: str):
    task = client.get_task(task_id)
    return {
        "status": task.status,
        "output": task.content.file_url if task.status == "succeeded" else None
    }
```

## 进阶技巧

### 1. 自动重试机制

```python
from imageto3d.client import Seed3DClient
import time

def create_with_retry(client, image_url, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = client.create_task(image_url=image_url)
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"重试 {attempt + 1}/{max_retries}...")
            time.sleep(5)
```

### 2. 进度回调

```python
import time

def wait_with_progress(client, task_id, callback=None):
    while True:
        task = client.get_task(task_id)
        if callback:
            callback(task.status)

        if task.status in ['succeeded', 'failed', 'cancelled']:
            return task

        time.sleep(5)

# 使用
def on_progress(status):
    print(f"当前状态: {status}")

result = wait_with_progress(client, task_id, on_progress)
```

### 3. 缓存管理

```python
import json
import hashlib

def get_cache_key(image_url, params):
    data = f"{image_url}:{params}"
    return hashlib.md5(data.encode()).hexdigest()

def check_cache(cache_key):
    # 从数据库或文件读取缓存
    pass

def save_cache(cache_key, result):
    # 保存到数据库或文件
    pass
```

## 故障排查

### 开启调试日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('imageto3d')
```

### 检查网络连接

```bash
# 测试 API 端点连通性
curl -I https://ark.cn-beijing.volces.com
```

### 验证环境

```bash
# 检查 Python 版本
python --version  # 应该 >= 3.9

# 检查依赖
pip list | grep volcengine

# 检查环境变量
echo $ARK_API_KEY
```

## 获取帮助

- **项目文档**：查看 README.md
- **示例代码**：查看 examples/ 目录
- **API 文档**：https://www.volcengine.com/docs/82379/1856293
- **控制台**：https://console.volcengine.com/ark/
- **问题反馈**：提交 Issue

## 许可和使用限制

- 遵守火山引擎服务条款
- 注意 API 调用配额
- 不要分享 API Key
- 合理使用，避免滥用
