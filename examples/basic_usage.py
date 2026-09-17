"""
示例脚本：演示如何使用 Image to 3D API
"""

import os
import sys

from imageto3d.client import Seed3DClient

# 设置 API Key（确保已在环境变量中设置）
api_key = os.environ.get("ARK_API_KEY")
if not api_key:
    print("错误: 请设置 ARK_API_KEY 环境变量")
    sys.exit(1)

# 创建客户端
client = Seed3DClient(api_key=api_key)

# 示例 1: 使用图片 URL 创建任务
print("=" * 60)
print("示例 1: 创建 3D 生成任务")
print("=" * 60)

image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/i23d_flower.jpeg"

try:
    result = client.create_task(
        image_url=image_url,
        subdivision_level="medium",
        file_format="glb"
    )

    print("✓ 任务创建成功!")
    print(f"  任务 ID: {result.id}")
    print(f"  状态: {result.status}")
    print(f"  模型: {result.model}")
    print()

    task_id = result.id

    # 示例 2: 等待任务完成
    print("=" * 60)
    print("示例 2: 等待任务完成")
    print("=" * 60)
    print("正在处理中，请稍候...")

    completed_task = client.wait_for_completion(
        task_id=task_id,
        timeout=300,
        poll_interval=5
    )

    print("✓ 任务完成!")
    print(f"  输出 URL: {completed_task.content.file_url}")
    print()

    # 示例 3: 下载 3D 模型
    print("=" * 60)
    print("示例 3: 下载 3D 模型")
    print("=" * 60)

    from imageto3d.utils import download_file

    output_path = "output_model.glb"
    download_file(completed_task.content.file_url, output_path)

    print(f"✓ 模型已下载到: {output_path}")
    print()

    # 示例 4: 查询任务详情
    print("=" * 60)
    print("示例 4: 查询任务详情")
    print("=" * 60)

    task_info = client.get_task(task_id)
    print(f"任务 ID: {task_info.id}")
    print(f"状态: {task_info.status}")
    print(f"创建时间: {task_info.created_at}")
    print()

    # 示例 5: 列出任务
    print("=" * 60)
    print("示例 5: 列出最近的任务")
    print("=" * 60)

    tasks_list = client.list_tasks(page_num=1, page_size=5)
    print(f"总任务数: {tasks_list.total}")
    print("当前页任务:")

    for task in tasks_list.items:
        print(f"  - ID: {task.id}")
        print(f"    状态: {task.status}")
        print(f"    创建时间: {task.created_at}")
        if task.status == "succeeded" and task.content:
            print(f"    输出: {task.content.file_url}")
        print()

    # 示例 6: 使用不同参数创建任务
    print("=" * 60)
    print("示例 6: 使用高质量设置创建任务")
    print("=" * 60)

    high_quality_result = client.create_task(
        image_url=image_url,
        subdivision_level="high",  # 高质量 (1M 面)
        file_format="obj"           # OBJ 格式
    )

    print("✓ 高质量任务创建成功!")
    print(f"  任务 ID: {high_quality_result.id}")
    print("  参数: 高质量 (1M 面), OBJ 格式")
    print()

    print("=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)

except Exception as e:
    print(f"✗ 错误: {e}")
    import traceback
    traceback.print_exc()
