class AIServiceUnavailable(Exception):
    pass


async def predict_video(file_path: str):
    """
    Temporary mock prediction until HuggingFace integration.
    """

    return {
        "prediction": "Real",
        "confidence": 87.5,
        "accuracy": 91.3
    }