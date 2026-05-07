import httpx
import os
import time

from app.core.config import get_settings

settings = get_settings()

HF_TOKEN="[ENCRYPTION_KEY]"
MODEL_URL="https://api-inference.huggingface.co/models/Ahmedkhairy2/Deepfake_last2"

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

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                MODEL_URL,
                headers=HEADERS,
                content=image_bytes
            )

        if response.status_code != 200:
            raise AIServiceUnavailable(f"HuggingFace error: {response.text}")

        result = response.json()

        # 🧠 حسب شكل الرد من موديلك
        # غالبًا بيكون list زي:
        # [{"label": "REAL", "score": 0.98}]

        if isinstance(result, list) and len(result) > 0:
            prediction = result[0]["label"]
            confidence = result[0]["score"]
        else:
            raise ValueError("Unexpected model response format")

        return {
            "prediction": prediction,
            "confidence": confidence,
            "processing_time": round(time.time() - start_time, 2),
            "result_source": "huggingface_image_model",
            "heatmap_url": None
        }

    except Exception as e:
        raise AIServiceUnavailable(str(e))