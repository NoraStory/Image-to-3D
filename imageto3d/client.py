"""Doubao-Seed3D API client for image to 3D conversion."""

import time
from typing import Any, Callable, Dict, List, Optional, Union

from volcenginesdkarkruntime import Ark

from .config import resolve_api_key, resolve_model

VALID_LEVELS = ("high", "medium", "low")
VALID_FORMATS = ("glb", "obj", "usd", "usdz")
MAX_IMAGES = 4  # Seed3D 2.0 multi-view input supports up to 4 images

TERMINAL_STATUSES = ("succeeded", "failed", "cancelled")


def _normalise_image_urls(
    image_urls: Optional[Union[str, List[str]]] = None,
    image_url: Optional[str] = None,
) -> List[str]:
    """Normalise the two image argument aliases into a single list."""
    if image_urls is not None and image_url is not None:
        raise ValueError("Provide either image_urls or image_url, not both")

    if image_url:
        urls: List[str] = [image_url]
    elif isinstance(image_urls, str):
        urls = [image_urls]
    else:
        urls = list(image_urls or [])

    if len(urls) > MAX_IMAGES:
        raise ValueError(f"Up to {MAX_IMAGES} images are supported for multi-view input")
    return urls


class Seed3DClient:
    """Client for the Doubao-Seed3D-2.0 API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
    ):
        """
        Initialize the Seed3D client.

        Args:
            api_key: API key for authentication. If not provided, reads from
                ARK_API_KEY, the project/user .env file, or the user config.
            model: Model name (defaults to IMAGETO3D_MODEL, the configured
                default, then the built-in Seed3D 2.0 endpoint).
            timeout: HTTP request timeout in seconds for SDK calls.
        """
        self.api_key = resolve_api_key(api_key)
        self.model = resolve_model(model)
        # SDK-level retries for transient network errors
        self.client = Ark(api_key=self.api_key, timeout=timeout, max_retries=3)

    # ------------------------------------------------------------------ #
    # task operations
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_content(
        image_urls: List[str],
        subdivision_level: str,
        file_format: str,
        draft_task_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Build the content parts for a task creation request."""
        parts: List[Dict[str, Any]] = [
            {
                "type": "text",
                "text": f"--subdivisionlevel {subdivision_level} --fileformat {file_format}",
            }
        ]

        if draft_task_id:
            # Refine a previously created draft task
            parts.append({"type": "draft_task", "draft_task": {"id": draft_task_id}})
        else:
            for index, url in enumerate(image_urls, start=1):
                part: Dict[str, Any] = {
                    "type": "image_url",
                    "image_url": {"url": url},
                }
                # Multi-view input: assign roles input_image1..N.
                # A single image is sent without a role (verified working).
                if len(image_urls) > 1:
                    part["role"] = f"input_image{index}"
                parts.append(part)

        return parts

    def create_task(
        self,
        image_urls: Optional[Union[str, List[str]]] = None,
        image_url: Optional[str] = None,
        subdivision_level: str = "medium",
        file_format: str = "glb",
        draft: bool = False,
        draft_task_id: Optional[str] = None,
        seed: Optional[int] = None,
        callback_url: Optional[str] = None,
        priority: Optional[int] = None,
        execution_expires_after: Optional[int] = None,
        safety_identifier: Optional[str] = None,
        return_last_frame: Optional[bool] = None,
        service_tier: Optional[str] = None,
        camera_fixed: Optional[bool] = None,
        watermark: Optional[bool] = None,
        resolution: Optional[str] = None,
        ratio: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """
        Create a 3D generation task from one or more images.

        Args:
            image_urls: One image, or a list of up to 4 images (multi-view
                input greatly improves geometry accuracy). Accepts http(s)
                URLs and base64 data URIs.
            image_url: Backwards-compatible alias for a single image.
            subdivision_level: 'high', 'medium', or 'low'.
            file_format: 'glb', 'obj', 'usd', or 'usdz'.
            draft: Create a cheap, fast draft for preview.
            draft_task_id: Instead of images, refine an existing draft task.
            seed: Fixed seed for reproducibility.
            callback_url: Webhook URL called when the task finishes.
            priority: Task queue priority.
            execution_expires_after: Give up queued execution after N seconds.
            safety_identifier: Pass a safety identifier if required by your account.
            return_last_frame: Ask the API for the last frame as well.
            service_tier: Service tier override.
            camera_fixed: Fix the camera during generation.
            watermark: Add a watermark to the output.
            resolution: Output resolution hint.
            ratio: Output aspect ratio hint.
            timeout: Per-request HTTP timeout in seconds.

        Returns:
            Task creation response with task ID (ContentGenerationTaskID).
        """
        if subdivision_level not in VALID_LEVELS:
            raise ValueError(f"subdivision_level must be one of {VALID_LEVELS}")
        if file_format not in VALID_FORMATS:
            raise ValueError(f"file_format must be one of {VALID_FORMATS}")

        image_urls = _normalise_image_urls(image_urls, image_url)

        if not draft_task_id and not image_urls:
            raise ValueError("At least one image (or a draft_task_id) is required")
        if draft_task_id and image_urls:
            raise ValueError("Provide either images or draft_task_id, not both")

        content = self._build_content(
            image_urls, subdivision_level, file_format, draft_task_id=draft_task_id
        )

        kwargs: Dict[str, Any] = {"model": self.model, "content": content}
        if draft:
            kwargs["draft"] = True
        if seed is not None:
            kwargs["seed"] = int(seed)
        if callback_url:
            kwargs["callback_url"] = callback_url
        if priority is not None:
            kwargs["priority"] = int(priority)
        if execution_expires_after is not None:
            kwargs["execution_expires_after"] = int(execution_expires_after)
        if safety_identifier:
            kwargs["safety_identifier"] = safety_identifier
        if return_last_frame is not None:
            kwargs["return_last_frame"] = bool(return_last_frame)
        if service_tier:
            kwargs["service_tier"] = service_tier
        if camera_fixed is not None:
            kwargs["camera_fixed"] = bool(camera_fixed)
        if watermark is not None:
            kwargs["watermark"] = bool(watermark)
        if resolution:
            kwargs["resolution"] = resolution
        if ratio:
            kwargs["ratio"] = ratio
        if timeout is not None:
            kwargs["timeout"] = timeout

        return self.client.content_generation.tasks.create(**kwargs)

    def get_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """Get task details by task ID."""
        kwargs: Dict[str, Any] = {"task_id": task_id}
        if timeout is not None:
            kwargs["timeout"] = timeout
        return self.client.content_generation.tasks.get(**kwargs)

    def list_tasks(
        self,
        page_num: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
        task_ids: Optional[List[str]] = None,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Any:
        """List tasks with optional filters."""
        kwargs: Dict[str, Any] = {"page_num": page_num, "page_size": page_size}
        if status:
            kwargs["status"] = status
        if task_ids:
            kwargs["task_ids"] = task_ids
        if model:
            kwargs["model"] = model
        if timeout is not None:
            kwargs["timeout"] = timeout
        return self.client.content_generation.tasks.list(**kwargs)

    def delete_task(self, task_id: str, timeout: Optional[float] = None) -> None:
        """Delete a task by ID."""
        kwargs: Dict[str, Any] = {"task_id": task_id}
        if timeout is not None:
            kwargs["timeout"] = timeout
        self.client.content_generation.tasks.delete(**kwargs)

    def cancel_task(self, task_id: str) -> None:
        """Not supported by the current API surface."""
        raise NotImplementedError(
            "The Volcengine content_generation API does not expose a cancel endpoint. "
            "Tasks can only be deleted."
        )

    def upload_image(self, local_path: str, timeout: Optional[float] = None) -> Any:
        """
        Upload a local image via the Files API (kept for advanced workflows;
        task creation currently uses base64 data URIs instead).
        """
        kwargs: Dict[str, Any] = {"purpose": "user_data"}
        if timeout is not None:
            kwargs["timeout"] = timeout
        with open(local_path, "rb") as f:
            return self.client.files.create(file=f, **kwargs)

    # ------------------------------------------------------------------ #
    # waiting
    # ------------------------------------------------------------------ #

    def wait_for_completion(
        self,
        task_id: str,
        timeout: int = 300,
        poll_interval: int = 5,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        progress_callback: Optional[Callable[[Any], None]] = None,
    ) -> Any:
        """
        Wait for a task to complete, retrying transient network errors
        with exponential backoff.

        Returns:
            Final task details (ContentGenerationTask).

        Raises:
            TimeoutError: If the task doesn't complete within timeout.
            RuntimeError: If the task fails or is cancelled.
        """
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        if poll_interval <= 0:
            raise ValueError("poll_interval must be positive")

        start_time = time.time()
        consecutive_errors = 0

        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(
                    f"Task {task_id} did not complete within {timeout} seconds"
                )

            try:
                task = self.get_task(task_id)
                consecutive_errors = 0
            except Exception:
                # Transient failure (network blip, rate limit, 5xx): retry
                consecutive_errors += 1
                remaining = timeout - (time.time() - start_time)
                if consecutive_errors > max_retries or remaining <= 0:
                    raise
                delay = min(retry_base_delay * (2 ** (consecutive_errors - 1)), poll_interval)
                time.sleep(min(delay, max(remaining, 0.1)))
                continue

            if progress_callback is not None:
                progress_callback(task)

            status = task.status
            if status == "succeeded":
                return task
            if status in TERMINAL_STATUSES:
                error = getattr(task, "error", None)
                code = getattr(error, "code", None)
                message = getattr(error, "message", None) or (str(error) if error else "unknown error")
                suffix = f" (code: {code})" if code else ""
                raise RuntimeError(f"Task {task_id} {status}: {message}{suffix}")

            time.sleep(poll_interval)
