import json
import mimetypes
import os
import time

import httpx

from app.core.config import get_settings

settings = get_settings()

HF_TOKEN = settings.hf_token
SPACE_ID = settings.hf_space_id
SPACE_API_NAME = settings.hf_space_api_name.lstrip("/")
SPACE_ROOT = f"https://{SPACE_ID.replace('/', '-')}.hf.space"

HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}"
}


class AIServiceUnavailable(Exception):
    pass


async def predict_image(file_path: str) -> dict:
    start_time = time.time()

    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()

        headers = {}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        async with httpx.AsyncClient(timeout=300) as client:
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
                raise ValueError("Unexpected upload response")

            uploaded_path = upload_data[0]
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
                raise ValueError("Missing event_id from Gradio queue")

            result_resp = await client.get(
                f"{SPACE_ROOT}/gradio_api/call/{SPACE_API_NAME}/{event_id}",
                headers=headers,
            )
            result_resp.raise_for_status()

        data_lines = [
            line[5:].strip()
            for line in result_resp.text.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            raise ValueError("No data in Gradio response")

        last_payload = json.loads(data_lines[-1])
        if isinstance(last_payload, dict):
            output = last_payload.get("output") or last_payload
            result_data = output.get("data") if isinstance(output, dict) else output
        else:
            result_data = last_payload

        if not isinstance(result_data, (list, tuple)) or len(result_data) < 1:
            raise ValueError("Unexpected model response format")

        prediction = result_data[0]
        confidence = None

        return {
            "prediction": prediction,
            "confidence": confidence,
            "processing_time": round(time.time() - start_time, 2),
            "result_source": "huggingface_space",
            "heatmap_url": result_data[1] if len(result_data) > 1 else None
        }

    except Exception as e:
        raise AIServiceUnavailable(str(e))