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
SPACE_ROOT = f"https://{SPACE_ID.replace('/', '-').lower()}.hf.space"

# Strip leading slash and ensure it's a simple endpoint name (not a full space path).
# On Vercel the env var may accidentally be set to the video space id instead of "/analyze".
_raw_api_name = settings.hf_space_api_name.lstrip("/").strip()
SPACE_API_NAME = _raw_api_name if "/" not in _raw_api_name else "analyze"

logger.info(
    "[image predictor] SPACE_ROOT=%s, SPACE_API_NAME=%s",
    SPACE_ROOT, SPACE_API_NAME
)


class AIServiceUnavailable(Exception):
    pass


async def predict_image(file_path: str) -> dict:
    start_time = time.time()

    try:
        headers = {}
        if HF_TOKEN:
            headers["Authorization"] = f"Bearer {HF_TOKEN}"

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        async with httpx.AsyncClient(timeout=300) as client:
            # ── Step 1: Upload file (open once only) ─────────────────────────
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
                raise ValueError(f"Unexpected upload response: {upload_resp.text[:200]}")

            uploaded_path = upload_data[0]
            logger.info("[predict_image] Uploaded to HF Space: %s", uploaded_path)

            # ── Step 2: Call /analyze endpoint ────────────────────────────────
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
                raise ValueError(f"Missing event_id from Gradio queue. Response: {call_resp.text[:200]}")

            logger.info("[predict_image] event_id=%s, polling result...", event_id)

            # ── Step 3: Poll result (SSE stream) ──────────────────────────────
            result_resp = await client.get(
                f"{SPACE_ROOT}/gradio_api/call/{SPACE_API_NAME}/{event_id}",
                headers=headers,
            )
            result_resp.raise_for_status()

        # ── Step 4: Parse SSE stream (event: complete / event: error) ────────
        lines = result_resp.text.splitlines()
        current_event = None
        result_data = None

        for line in lines:
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                raw = line[5:].strip()
                if current_event == "error":
                    try:
                        err = json.loads(raw)
                        err_msg = err.get("error") or "HuggingFace Space returned an error"
                    except Exception:
                        err_msg = raw or "HuggingFace Space returned an error"
                    raise AIServiceUnavailable(f"Model error: {err_msg}")

                if current_event == "complete":
                    try:
                        payload_parsed = json.loads(raw)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Could not parse Gradio complete payload: {e}")

                    if isinstance(payload_parsed, list):
                        result_data = payload_parsed
                    elif isinstance(payload_parsed, dict):
                        output = payload_parsed.get("output") or payload_parsed
                        result_data = output.get("data") if isinstance(output, dict) else output

        if result_data is None:
            logger.info("Gradio raw response (first 2000 chars): %s", result_resp.text[:2000])
            raise ValueError("No 'complete' event found in Gradio response")

        if not isinstance(result_data, (list, tuple)) or len(result_data) < 1:
            raise ValueError(f"Unexpected model response format: {result_data}")

        prediction = result_data[0]
        raw_prediction_text = prediction if isinstance(prediction, str) else ""
        confidence = None
        heatmap_url = None

        # ── Normalise prediction label ─────────────────────────────────────────
        # The model may return: "Prediction: Fake\nConfidence: 51.84%", "FAKE", etc.
        # Extract a clean "Fake" / "Real" label for consistent storage.
        if isinstance(prediction, str):
            pred_lower = prediction.lower()
            if "fake" in pred_lower:
                prediction = "Fake"
            elif "real" in pred_lower:
                prediction = "Real"
            # else keep as-is (unknown)

        # ── Extract heatmap from second element ────────────────────────────────
        if len(result_data) > 1:
            heatmap_data = result_data[1]
            if isinstance(heatmap_data, dict):
                heatmap_url = heatmap_data.get("url") or heatmap_data.get("path")
            else:
                heatmap_url = heatmap_data

        # ── Extract confidence ─────────────────────────────────────────────────
        # Try result_data[2] first, then parse from the raw prediction text.
        if len(result_data) > 2 and result_data[2] is not None:
            raw_conf = result_data[2]
            if isinstance(raw_conf, (int, float)):
                confidence = f"{float(raw_conf):.2f}%"
            elif isinstance(raw_conf, str):
                m = re.search(r"(\d+(?:\.\d+)?)\s*%", raw_conf)
                confidence = f"{float(m.group(1)):.2f}%" if m else raw_conf

        if confidence is None and raw_prediction_text:
            m = re.search(r"(\d+(?:\.\d+)?)\s*%", raw_prediction_text)
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