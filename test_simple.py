"""
简单测试 - 检查 API 返回结构
"""

from imageto3d.client import Seed3DClient


def main():
    # 创建客户端
    client = Seed3DClient()

    # 使用示例图片
    image_url = "https://ark-project.tos-cn-beijing.volces.com/doc_image/i23d_flower.jpeg"

    print("Creating task...")
    try:
        result = client.create_task(
            image_url=image_url,
            subdivision_level="medium",
            file_format="glb"
        )

        print(f"Task created successfully!")
        print(f"Type: {type(result)}")
        print(f"Task ID: {result.id}")

        # 查询任务详情
        print(f"\nQuerying task details...")
        task_info = client.get_task(result.id)

        print(f"Task info type: {type(task_info)}")

        # 尝试不同方式访问属性
        if hasattr(task_info, 'status'):
            print(f"Status (attribute): {task_info.status}")

        if hasattr(task_info, 'model_dump'):
            task_dict = task_info.model_dump()
            print(f"Status (dict): {task_dict.get('status')}")
            print(f"All fields: {list(task_dict.keys())}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
