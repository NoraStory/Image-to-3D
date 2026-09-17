# 🚀 快速开始 - 3 分钟上手指南

## 方式一：Web 界面（最简单）⭐

### 1. 启动应用

**Windows 用户：**
```bash
双击运行 start_web.bat
```

**Linux/Mac 用户：**
```bash
./start_web.sh
```

### 2. 打开浏览器

访问：http://127.0.0.1:5000

### 3. 上传图片

- **方式 A**：拖拽图片到上传区域
- **方式 B**：点击选择本地图片
- **方式 C**：输入图片 URL

### 4. 配置参数（可选）

- **网格质量**：选择 低/中/高（默认：中）
- **输出格式**：选择 GLB/OBJ/USD/USDZ（默认：GLB）

### 5. 开始转换

点击 "开始转换" 按钮，等待 2-5 分钟

### 6. 下载模型

转换完成后，点击 "下载 3D 模型" 按钮

---

## 方式二：命令行（适合高级用户）

### 基本用法

```bash
# 激活环境
source .venv/Scripts/activate  # Windows
source .venv/bin/activate       # Linux/Mac

# 使用图片 URL
imageto3d create --image-url https://example.com/image.jpg --wait --output model.glb

# 使用本地图片
imageto3d create --image-file path/to/image.jpg --wait --output model.glb
```

### 高级参数

```bash
# 高质量 + OBJ 格式
imageto3d create \
  --image-file image.jpg \
  --subdivision-level high \
  --file-format obj \
  --wait \
  --output model.obj

# 查询任务状态
imageto3d get <task_id>

# 列出所有任务
imageto3d list
```

---

## 方式三：Python API（适合开发者）

### 最简代码

```python
from imageto3d.client import Seed3DClient

# 创建客户端
client = Seed3DClient()

# 转换图片
result = client.create_task(
    image_url="https://example.com/image.jpg",
    subdivision_level="medium",
    file_format="glb"
)

# 等待完成
task = client.wait_for_completion(result.id)

# 获取下载链接
print(f"下载链接: {task.content.file_url}")
```

### 运行示例

```bash
# 快速开始示例
python examples/quickstart.py

# 完整功能演示
python examples/basic_usage.py

# 本地图片处理
python examples/local_image.py

# 批量转换
python examples/batch_conversion.py
```

---

## 测试用例

### 使用示例图片

```bash
# 官方示例图片（一朵花）
imageto3d create \
  --image-url "https://ark-project.tos-cn-beijing.volces.com/doc_image/i23d_flower.jpeg" \
  --wait \
  --output flower.glb
```

### 使用自己的图片

确保图片符合以下要求：
- ✅ 分辨率 ≤ 4096×4096
- ✅ 文件大小 ≤ 10MB
- ✅ 宽高比 0.4~2.5
- ✅ 格式：JPG, PNG, WebP, BMP

---

## 验证安装

运行系统检查：

```bash
python check_system.py
```

应该看到：
```
🎉 所有检查通过！系统配置正确。
```

---

## 常见问题

### Q1: 提示 "API key is required"
**A:** 检查 `.env` 文件是否存在，内容应为：
```
ARK_API_KEY=your_api_key_here
```

### Q2: 命令行工具找不到
**A:** 确保已安装项目：
```bash
pip install -e .
```

### Q3: 图片验证失败
**A:** 检查图片是否符合要求，可以使用工具调整大小：
```python
from PIL import Image
img = Image.open("large.jpg")
img.thumbnail((2048, 2048))
img.save("resized.jpg")
```

### Q4: 任务一直在处理中
**A:** 正常情况下需要 2-5 分钟，复杂图片可能更久。可以增加超时时间：
```bash
imageto3d create --image-file image.jpg --wait --timeout 600
```

---

## 下一步

1. **阅读完整文档**
   - [README.md](README.md) - 项目介绍
   - [GUIDE.md](GUIDE.md) - 详细使用指南
   - [STRUCTURE.md](STRUCTURE.md) - 项目架构

2. **查看示例代码**
   - [examples/](examples/) 目录包含 4 个实用示例

3. **集成到项目**
   - 参考 [GUIDE.md](GUIDE.md) 的集成章节

---

## 帮助

遇到问题？

1. 运行 `python check_system.py` 检查配置
2. 查看 [GUIDE.md](GUIDE.md) 常见问题章节
3. 检查 API 文档：https://www.volcengine.com/docs/82379/1856293

---

## 当前状态

✅ 运行 `start_web.bat`（Windows）或 `./start_web.sh`（Linux/Mac）即可启动 Web 服务器  
✅ 命令行工具已就绪  
✅ Python API 可用  
✅ 所有示例可运行  
✅ API Key 通过 `.env` 或环境变量配置  

**立即开始使用吧！** 🎉
