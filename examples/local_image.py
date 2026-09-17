"""
本地图片转换示例：使用本地图片文件
"""

import os
import sys
from pathlib import Path

from imageto3d.client import Seed3DClient
from imageto3d.utils import download_file, encode_image_to_base64, get_image_info

# 创建客户端
client = Seed3DClient()

# 本地图片路径（修改为你的图片路径）
local_image = "path/to/your/image.jpg"

# 检查文件是否存在
if not os.path.exists(local_image):
    print(f"错误: 图片文件不存在: {local_image}")
    print("请修改 local_image 变量为实际的图片路径")
    sys.exit(1)

print("=" * 60)
print("本地图片转 3D 示例")
print("=" * 60)
print()

# 显示图片信息
print("图片信息:")
try:
    info = get_image_info(local_image)
    print(f"  路径: {local_image}")
    print(f"  尺寸: {info['width']} x {info['height']} px")
    print(f"  大小: {info['size_mb']:.2f} MB")
    print(f"  格式: {info['format']}")
    print()
except ValueError as e:
    print(f"  ✗ 图片验证失败: {e}")
    sys.exit(1)

# 编码图片
print("正在编码图片...")
try:
    image_data_uri = encode_image_to_base64(local_image)
    print("✓ 图片编码完成")
    print()
except Exception as e:
    print(f"✗ 编码失败: {e}")
    sys.exit(1)

# 创建转换任务
print("正在创建 3D 生成任务...")
try:
    result = client.create_task(
        image_url=image_data_uri,
        subdivision_level="medium",
        file_format="glb"
    )

    print("✓ 任务创建成功!")
    print(f"  任务 ID: {result.id}")
    print()

    # 等待完成
    print("正在处理，请稍候...")
    task = client.wait_for_completion(result.id, timeout=300, poll_interval=5)

    print("✓ 转换完成!")
    print(f"  输出 URL: {task.content.file_url}")
    print()

    # 下载模型
    output_filename = Path(local_image).stem + "_3d.glb"
    print(f"正在下载到: {output_filename}")
    download_file(task.content.file_url, output_filename)

    print("✓ 下载完成!")
    print()
    print("=" * 60)
    print(f"3D 模型已保存到: {output_filename}")
    print("=" * 60)

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
