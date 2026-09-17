"""
快速开始示例：最简单的使用方式
"""

from imageto3d.client import Seed3DClient

# 创建客户端
client = Seed3DClient()

# 使用示例图片 URL
image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/i23d_flower.jpeg"

print("正在创建 3D 生成任务...")

# 创建任务
result = client.create_task(
    image_url=image_url,
    subdivision_level="medium",
    file_format="glb"
)

print(f"任务 ID: {result.id}")
print("任务已创建，正在处理中...")

# 等待完成
task = client.wait_for_completion(result.id, timeout=300)

print("✓ 转换完成!")
print(f"下载链接: {task.content.file_url}")
