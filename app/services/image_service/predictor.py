import json
import mimetypes
import os
import re
import time

import httpx

from app.core.logging_config import get_logger

from app.core.config import get_settings

settings = get_settings()

logger = get_logger(__name__)

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
            logger.info("Gradio raw response (first 2000 chars): %s", result_resp.text[:2000])
            raise ValueError("No data in Gradio response")

        last_payload = json.loads(data_lines[-1])
        logger.info("Gradio last payload: %s", last_payload)
        if isinstance(last_payload, dict):
            output = last_payload.get("output") or last_payload
            result_data = output.get("data") if isinstance(output, dict) else output
        else:
            result_data = last_payload

        if not isinstance(result_data, (list, tuple)) or len(result_data) < 1:
            raise ValueError("Unexpected model response format")

        prediction = result_data[0]
        confidence = None
        heatmap_url = None

        # ── Extract heatmap from second element ────────────────────────────────
        if len(result_data) > 1:
            heatmap_data = result_data[1]
            if isinstance(heatmap_data, dict):
                heatmap_url = heatmap_data.get("url") or heatmap_data.get("path")
            else:
                heatmap_url = heatmap_data

        # ── Extract confidence from prediction string ──────────────────────────
        # Model may return "Fake | Confidence: 83.24%" or "Real\nConfidence: 96.10%"
        # Try dedicated field first, then parse from prediction text.
        if len(result_data) > 2 and result_data[2] is not None:
            raw_conf = result_data[2]
            if isinstance(raw_conf, (int, float)):
                confidence = f"{float(raw_conf):.2f}%"
            elif isinstance(raw_conf, str):
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", raw_conf)
                confidence = f"{float(m.group(1)):.2f}%" if m else raw_conf

        if confidence is None and isinstance(prediction, str):
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", prediction)
            if m:
                confidence = f"{float(m.group(1)):.2f}%"

        logger.info(
            "[predict_image] prediction=%s, confidence=%s, heatmap_url=%s",
            prediction, confidence, heatmap_url
        )

        return {
            "prediction": prediction,
            "confidence": confidence,
            "processing_time": round(time.time() - start_time, 2),
            "result_source": "huggingface_space",
            "heatmap_url": heatmap_url
        }

    except Exception as e:
        raise AIServiceUnavailable(str(e))