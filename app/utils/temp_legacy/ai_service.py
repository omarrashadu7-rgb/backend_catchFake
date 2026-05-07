"""
HTTP client boundary for the isolated AI services.

The backend must not import TensorFlow/Keras directly. Image and video
inference run in their own FastAPI services so each model can keep the
runtime dependencies it needs.
"""

import os
from typing import Any

import httpx

from app.core.logging_config import get_logger
from app.core.config import get_settings

logger = get_logger(__name__)
settings = get_settings()


class AIServiceUnavailable(RuntimeError):
    """Raised when an isolated AI service cannot complete a prediction."""


async def _post_file(service_url: str, endpoint: str, file_path: str) -> dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Upload file not found: {file_path}")

    url = f"{service_url.rstrip('/')}/{endpoint.lstrip('/')}"
    filename = os.path.basename(file_path)

    timeout = httpx.Timeout(settings.ai_request_timeout_seconds)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            with open(file_path, "rb") as file_obj:
                response = await client.post(
                    url,
                    files={"file": (filename, file_obj, "application/octet-stream")},
                )
    except httpx.RequestError as exc:
        logger.error("AI service request failed: %s -> %s", url, exc)
        raise AIServiceUnavailable(
            f"AI service is unavailable. Could not reach {url}."
        ) from exc

    if response.status_code >= 400:
        detail = _extract_error_detail(response)
        logger.error("AI service returned %s from %s: %s", response.status_code, url, detail)
        raise AIServiceUnavailable(detail)

    try:
        data = response.json()
    except ValueError as exc:
        logger.error("AI service returned invalid JSON from %s: %s", url, response.text)
        raise AIServiceUnavailable("AI service returned an invalid response.") from exc

    if not data.get("prediction"):
        raise AIServiceUnavailable("AI service response did not include a prediction.")

    return data


def _extract_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or "AI service prediction failed."

    detail = payload.get("detail") or payload.get("message") or payload.get("error")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail)
    return str(detail or "AI service prediction failed.")


async def predict_image(file_path: str) -> dict[str, Any]:
    """Forward an image upload to the isolated image AI service."""
    return await _post_file(settings.image_ai_service_url, "/predict-image", file_path)


async def predict_video(file_path: str) -> dict[str, Any]:
    """Forward a video upload to the isolated video AI service."""
    return await _post_file(settings.video_ai_service_url, "/predict-video", file_path)
