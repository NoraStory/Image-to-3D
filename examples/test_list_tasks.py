"""
查看已有任务的输出结构
"""

from imageto3d.client import Seed3DClient

client = Seed3DClient()

# 列出最近的任务
print("Listing recent tasks...")
result = client.list_tasks(page_size=5)

print(f"\nResult type: {type(result)}")

if hasattr(result, 'items'):
    tasks = result.items
    print(f"Found {len(tasks)} tasks")

    for task in tasks:
        print(f"\n{'='*50}")
        print(f"Task ID: {task.id}")
        print(f"Status: {task.status}")

        if task.status == "succeeded":
            print("\nSucceeded task found! Checking structure...")

            # 使用 model_dump 查看所有字段
            if hasattr(task, 'model_dump'):
                task_dict = task.model_dump()
                print("\nAll non-None fields:")
                for key, value in task_dict.items():
                    if value is not None:
                        print(f"  {key}: {type(value).__name__} = {value if len(str(value)) < 100 else str(value)[:100] + '...'}")

            # 检查常见的输出字段
            if hasattr(task, 'content'):
                print(f"\nContent attribute exists: {task.content}")
            if hasattr(task, 'output'):
                print(f"\nOutput attribute exists: {task.output}")

            break
else:
    print(f"Result: {result}")
