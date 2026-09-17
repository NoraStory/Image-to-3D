"""
调试脚本 - 检查 API 返回的对象结构
"""

import os
from imageto3d.client import Seed3DClient

# 创建客户端
client = Seed3DClient()

# 使用示例图片
image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/i23d_flower.jpeg"

print("正在创建任务...")
try:
    result = client.create_task(
        image_url=image_url,
        subdivision_level="medium",
        file_format="glb"
    )

    print("\n=== 创建任务返回对象 ===")
    print(f"类型: {type(result)}")
    print(f"内容: {result}")
    print(f"属性: {dir(result)}")

    # 尝试访问常见属性
    if hasattr(result, 'id'):
        print(f"\n✓ result.id = {result.id}")
    if hasattr(result, 'task_id'):
        print(f"✓ result.task_id = {result.task_id}")
    if hasattr(result, 'status'):
        print(f"✓ result.status = {result.status}")

    # 如果是字典类型
    if isinstance(result, dict):
        print(f"\n字典键: {result.keys()}")

    # 尝试获取任务ID
    task_id = None
    if hasattr(result, 'id'):
        task_id = result.id
    elif hasattr(result, 'task_id'):
        task_id = result.task_id
    elif isinstance(result, dict) and 'id' in result:
        task_id = result['id']

    if task_id:
        print(f"\n任务 ID: {task_id}")
        print("\n正在查询任务状态...")

        task_info = client.get_task(task_id)
        print("\n=== 查询任务返回对象 ===")
        print(f"类型: {type(task_info)}")
        print(f"内容: {task_info}")
        print(f"属性: {dir(task_info)}")

        # 尝试访问状态
        if hasattr(task_info, 'status'):
            print(f"\n✓ task_info.status = {task_info.status}")
        elif isinstance(task_info, dict) and 'status' in task_info:
            print(f"\n✓ task_info['status'] = {task_info['status']}")

except Exception as e:
    print(f"\n错误: {e}")
    import traceback
    traceback.print_exc()
