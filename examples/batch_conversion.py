"""
批量转换示例：处理多张图片
"""

import time

from imageto3d.client import Seed3DClient
from imageto3d.utils import download_file

# 创建客户端
client = Seed3DClient()

# 要转换的图片 URLs
images = [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg",
    "https://example.com/image3.jpg",
]

# 配置参数
config = {
    "subdivision_level": "medium",
    "file_format": "glb"
}

print(f"开始批量转换 {len(images)} 张图片...")
print("=" * 60)

# 创建所有任务
task_ids = []
for i, image_url in enumerate(images, 1):
    try:
        print(f"[{i}/{len(images)}] 创建任务: {image_url}")
        result = client.create_task(
            image_url=image_url,
            subdivision_level=config["subdivision_level"],
            file_format=config["file_format"]
        )
        task_ids.append({
            "id": result.id,
            "url": image_url,
            "index": i
        })
        print(f"  ✓ 任务 ID: {result.id}")

        # 避免请求过快
        time.sleep(1)

    except Exception as e:
        print(f"  ✗ 失败: {e}")

print()
print("=" * 60)
print(f"已创建 {len(task_ids)} 个任务，等待处理...")
print("=" * 60)
print()

# 等待所有任务完成
completed = []
failed = []

for task_info in task_ids:
    task_id = task_info["id"]
    index = task_info["index"]

    print(f"[{index}/{len(task_ids)}] 等待任务 {task_id}...")

    try:
        task = client.wait_for_completion(
            task_id=task_id,
            timeout=300,
            poll_interval=5
        )

        output_file = f"output_{index}.{config['file_format']}"
        download_file(task.content.file_url, output_file)

        completed.append({
            "task_id": task_id,
            "output": output_file,
            "url": task_info["url"]
        })

        print(f"  ✓ 完成! 已保存到: {output_file}")

    except Exception as e:
        failed.append({
            "task_id": task_id,
            "url": task_info["url"],
            "error": str(e)
        })
        print(f"  ✗ 失败: {e}")

    print()

# 输出总结
print("=" * 60)
print("批量转换完成!")
print("=" * 60)
print(f"成功: {len(completed)}")
print(f"失败: {len(failed)}")
print()

if completed:
    print("成功的任务:")
    for item in completed:
        print(f"  - {item['output']} <- {item['url']}")
    print()

if failed:
    print("失败的任务:")
    for item in failed:
        print(f"  - {item['url']}: {item['error']}")
