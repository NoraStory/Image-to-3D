"""
单元测试：测试 Image to 3D 核心功能
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from imageto3d.client import Seed3DClient
from imageto3d.utils import get_image_info, validate_image


class TestSeed3DClient:
    """测试 Seed3D 客户端"""

    def test_init_with_api_key(self):
        """测试使用 API key 初始化"""
        client = Seed3DClient(api_key="test-key")
        assert client.api_key == "test-key"

    def test_init_without_api_key(self):
        """测试没有 API key 时抛出异常"""
        with patch.dict(os.environ, {}, clear=True), patch(
            "imageto3d.client.resolve_api_key",
            side_effect=ValueError("API key is required"),
        ), pytest.raises(ValueError):
            Seed3DClient()

    def test_init_from_env(self):
        """测试从环境变量读取 API key"""
        with patch.dict(os.environ, {"ARK_API_KEY": "env-key"}):
            client = Seed3DClient()
            assert client.api_key == "env-key"

    def test_invalid_subdivision_level(self):
        """测试无效的网格质量参数"""
        client = Seed3DClient(api_key="test-key")
        with pytest.raises(ValueError):
            client.create_task(
                image_url="https://example.com/image.jpg",
                subdivision_level="invalid"
            )

    def test_invalid_file_format(self):
        """测试无效的文件格式参数"""
        client = Seed3DClient(api_key="test-key")
        with pytest.raises(ValueError):
            client.create_task(
                image_url="https://example.com/image.jpg",
                file_format="invalid"
            )


class TestImageValidation:
    """测试图片验证功能"""

    def create_test_image(self, width, height, format="PNG"):
        """创建测试图片"""
        img = Image.new("RGB", (width, height), color="red")
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=f".{format.lower()}"
        )
        img.save(temp_file.name, format=format)
        temp_file.close()
        return temp_file.name

    def test_valid_image(self):
        """测试有效的图片"""
        image_path = self.create_test_image(800, 600)
        try:
            validate_image(image_path)  # 不应抛出异常
        finally:
            os.unlink(image_path)

    def test_image_not_found(self):
        """测试图片不存在"""
        with pytest.raises(FileNotFoundError):
            validate_image("non_existent_file.jpg")

    def test_invalid_format(self):
        """测试不支持的格式"""
        temp_file = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".txt"
        )
        temp_file.write(b"not an image")
        temp_file.close()

        try:
            with pytest.raises(ValueError, match="Unsupported format"):
                validate_image(temp_file.name)
        finally:
            os.unlink(temp_file.name)

    def test_image_too_large_resolution(self):
        """测试分辨率过大"""
        image_path = self.create_test_image(5000, 5000)
        try:
            with pytest.raises(ValueError, match="exceeds 4096x4096"):
                validate_image(image_path)
        finally:
            os.unlink(image_path)

    def test_invalid_aspect_ratio(self):
        """测试宽高比不合法"""
        # 宽高比 < 0.4
        image_path = self.create_test_image(100, 300)
        try:
            with pytest.raises(ValueError, match="Aspect ratio"):
                validate_image(image_path)
        finally:
            os.unlink(image_path)

    def test_get_image_info(self):
        """测试获取图片信息"""
        image_path = self.create_test_image(800, 600)
        try:
            info = get_image_info(image_path)
            assert info["width"] == 800
            assert info["height"] == 600
            assert info["format"] == "PNG"
            assert info["size_mb"] > 0
        finally:
            os.unlink(image_path)


class TestClientMethods:
    """测试客户端方法"""

    @patch("imageto3d.client.Ark")
    def test_create_task(self, mock_ark):
        """测试创建任务"""
        # Mock Ark 客户端响应
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_result.status = "queued"

        mock_client = Mock()
        mock_client.content_generation.tasks.create.return_value = mock_result
        mock_ark.return_value = mock_client

        # 测试
        client = Seed3DClient(api_key="test-key")
        result = client.create_task(
            image_url="https://example.com/image.jpg",
            subdivision_level="high",
            file_format="obj"
        )

        assert result.id == "task-123"
        assert result.status == "queued"

        # 验证调用参数
        call_args = mock_client.content_generation.tasks.create.call_args
        assert call_args[1]["model"] == "doubao-seed3d-2-0-260328"
        content = call_args[1]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert "--subdivisionlevel high" in content[0]["text"]
        assert "--fileformat obj" in content[0]["text"]

    @patch("imageto3d.client.Ark")
    def test_get_task(self, mock_ark):
        """测试获取任务"""
        mock_result = Mock()
        mock_result.id = "task-123"
        mock_result.status = "succeeded"

        mock_client = Mock()
        mock_client.content_generation.tasks.get.return_value = mock_result
        mock_ark.return_value = mock_client

        client = Seed3DClient(api_key="test-key")
        result = client.get_task("task-123")

        assert result.id == "task-123"
        assert result.status == "succeeded"

    @patch("imageto3d.client.Ark")
    def test_list_tasks(self, mock_ark):
        """测试列出任务"""
        mock_result = Mock()
        mock_result.items = [Mock(id="task-1"), Mock(id="task-2")]
        mock_result.total = 2

        mock_client = Mock()
        mock_client.content_generation.tasks.list.return_value = mock_result
        mock_ark.return_value = mock_client

        client = Seed3DClient(api_key="test-key")
        result = client.list_tasks(page_num=1, page_size=10)

        assert len(result.items) == 2
        assert result.total == 2

    @patch("imageto3d.client.Ark")
    def test_delete_task(self, mock_ark):
        """测试删除任务"""
        mock_client = Mock()
        mock_ark.return_value = mock_client

        client = Seed3DClient(api_key="test-key")
        client.delete_task("task-123")

        mock_client.content_generation.tasks.delete.assert_called_once_with(
            task_id="task-123"
        )

    @patch("imageto3d.client.Ark")
    @patch("imageto3d.client.time.sleep")
    def test_wait_for_completion_success(self, mock_sleep, mock_ark):
        """测试等待任务完成 - 成功"""
        # 模拟任务从 running 变为 succeeded
        mock_task_running = Mock()
        mock_task_running.status = "running"

        mock_task_success = Mock()
        mock_task_success.status = "succeeded"

        mock_client = Mock()
        mock_client.content_generation.tasks.get.side_effect = [
            mock_task_running,
            mock_task_success
        ]
        mock_ark.return_value = mock_client

        client = Seed3DClient(api_key="test-key")
        result = client.wait_for_completion("task-123", timeout=60)

        assert result.status == "succeeded"

    @patch("imageto3d.client.Ark")
    @patch("imageto3d.client.time.sleep")
    def test_wait_for_completion_timeout(self, mock_sleep, mock_ark):
        """测试等待任务完成 - 超时"""
        mock_task = Mock()
        mock_task.status = "running"

        mock_client = Mock()
        mock_client.content_generation.tasks.get.return_value = mock_task
        mock_ark.return_value = mock_client

        client = Seed3DClient(api_key="test-key")

        with pytest.raises(TimeoutError):
            client.wait_for_completion("task-123", timeout=1, poll_interval=1)

    @patch("imageto3d.client.Ark")
    @patch("imageto3d.client.time.sleep")
    def test_wait_for_completion_failed(self, mock_sleep, mock_ark):
        """测试等待任务完成 - 失败"""
        mock_task = Mock()
        mock_task.status = "failed"
        mock_task.get.return_value = "Some error"

        mock_client = Mock()
        mock_client.content_generation.tasks.get.return_value = mock_task
        mock_ark.return_value = mock_client

        client = Seed3DClient(api_key="test-key")

        with pytest.raises(RuntimeError, match="failed"):
            client.wait_for_completion("task-123", timeout=60)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
