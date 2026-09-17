"""
测试任务完成后的输出结构
"""

from imageto3d.client import Seed3DClient
import time


def main():
    # 创建客户端
    client = Seed3DClient()

    # 使用示例图片
    image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/i23d_flower.jpeg"

    print("Creating task with low quality for faster testing...")
    result = client.create_task(
        image_url=image_url,
        subdivision_level="low",  # 使用低质量以加快处理速度
        file_format="glb"
    )

    print(f"Task ID: {result.id}")
    print(f"\nWaiting for completion (this may take 2-5 minutes)...")

    try:
        task = client.wait_for_completion(result.id, timeout=600, poll_interval=10)

        print(f"\nTask completed successfully!")
        print(f"Task type: {type(task)}")
        print(f"Status: {task.status}")

        # 检查输出结构
        if hasattr(task, 'content'):
            print(f"\nHas 'content' attribute")
            print(f"Content type: {type(task.content)}")
            print(f"Content: {task.content}")

        # 使用 model_dump 查看所有字段
        if hasattr(task, 'model_dump'):
            task_dict = task.model_dump()
            print(f"\nAll fields:")
            for key, value in task_dict.items():
                if value is not None:
                    print(f"  {key}: {type(value).__name__}")
                    if key in ['content', 'output'] and value:
                        print(f"    Value: {value}")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
