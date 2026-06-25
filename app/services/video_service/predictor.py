import json
import mimetypes
import os

import httpx

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)

HF_TOKEN = settings.hf_token
SPACE_ID = settings.hf_video_space_id
SPACE_API_NAME = settings.hf_video_space_api_name.lstrip("/")
SPACE_ROOT = f"https://{SPACE_ID.replace('/', '-').lower()}.hf.space"


class AIServiceUnavailable(Exception):
    pass


def _parse_sse_response(text: str) -> list:
    """
    Parse a Gradio SSE stream and return the data from the 'complete' event.

    The stream looks like:
        event: heartbeat
        data: null

        event: heartbeat
        data: null

        event: complete
        data: ["REAL", "100.00%", "0.00%"]

    Returns the parsed list from the 'complete' event data.
    Raises AIServiceUnavailable on error events or unexpected formats.
    """
    lines = text.splitlines()
    current_event = None

    for line in lines:
        if line.startswith("event:"):
            current_event = line[6:].strip()
        elif line.startswith("data:"):
            raw = line[5:].strip()

            if current_event == "error":
                try:
                    err = json.loads(raw)
                    msg = err.get("error") or "HuggingFace Space returned an error"
                except Exception:
                    msg = raw or "HuggingFace Space returned an error"
                raise AIServiceUnavailable(f"Model error: {msg}")

            if current_event == "complete":
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError as e:
                    raise AIServiceUnavailable(f"Could not parse Gradio complete payload: {e}")

                # payload is already the list: ["REAL", "100.00%", "0.00%"]
                if isinstance(payload, list):
                    return payload

                # Fallback: nested {"output": {"data": [...]}}
                if isinstance(payload, dict):
                    output = payload.get("output") or payload
                    data = output.get("data") if isinstance(output, dict) else None
                    if isinstance(data, list):
                        return data

                raise AIServiceUnavailable(
                    f"Unexpected complete payload format: {type(payload).__name__}"
                )

    raise AIServiceUnavailable("No 'complete' event found in Gradio SSE response")


async def predict_video(file_path: str):
    """
    Call the Hugging Face Space (Gradio) video API and return the prediction.

    Returns:
        {
            "prediction":    str   e.g. "REAL" or "FAKE"
            "confidence":    str   e.g. "100.00%"
            "fake_probability": str  e.g. "0.00%"
            "result_source": str
        }
    """
    headers = {}
    if HF_TOKEN:
        headers["Authorization"] = f"Bearer {HF_TOKEN}"

    mime_type, _ = mimetypes.guess_type(file_path)
    mime_type = mime_type or "application/octet-stream"

    async with httpx.AsyncClient(timeout=600) as client:
        # --- Step 1: Upload the video file ---
        logger.info(f"[predict_video] Uploading {os.path.basename(file_path)} to HF Space")
        with open(file_path, "rb") as f:
            files = {
                "files": (os.path.basename(file_path), f, mime_type)
            }
            upload_resp = await client.post(
                f"{SPACE_ROOT}/gradio_api/upload",
                files=files,
                headers=headers,
            )
        upload_resp.raise_for_status()

        upload_data = upload_resp.json()
        if not isinstance(upload_data, list) or not upload_data:
            raise AIServiceUnavailable("Unexpected upload response from HF Space")

        uploaded_path = upload_data[0]
        logger.info(f"[predict_video] Uploaded to: {uploaded_path}")

        # --- Step 2: Call /analyze ---
        payload = {
            "data": [
                {
                    "path": uploaded_path,
                    "orig_name": os.path.basename(file_path),
                    "mime_type": mime_type,
                    "meta": {"_type": "gradio.FileData"},
                }
            ]
        }

        call_resp = await client.post(
            f"{SPACE_ROOT}/gradio_api/call/{SPACE_API_NAME}",
            json=payload,
            headers=headers,
        )
        call_resp.raise_for_status()

        try:
            event_id = call_resp.json().get("event_id")
        except Exception:
            event_id = call_resp.text.strip().strip("\"")

        if not event_id:
            raise AIServiceUnavailable("Missing event_id from Gradio queue")

        logger.info(f"[predict_video] event_id={event_id}, polling result...")

        # --- Step 3: Poll result (SSE stream) ---
        result_resp = await client.get(
            f"{SPACE_ROOT}/gradio_api/call/{SPACE_API_NAME}/{event_id}",
            headers=headers,
        )
        result_resp.raise_for_status()

    # --- Step 4: Parse SSE response ---
    result_data = _parse_sse_response(result_resp.text)

    if len(result_data) < 1:
        raise AIServiceUnavailable("Empty result list from model")

    prediction  = result_data[0]
    confidence  = result_data[1] if len(result_data) > 1 else None
    fake_prob   = result_data[2] if len(result_data) > 2 else None

    logger.info(
        f"[predict_video] prediction={prediction}, confidence={confidence}, fake_prob={fake_prob}"
    )

    return {
        "prediction":     prediction,
        "confidence":     confidence,
        "fake_probability": fake_prob,
        "result_source":  "huggingface_video_space",
    }