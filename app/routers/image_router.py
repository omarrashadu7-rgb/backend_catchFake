from fastapi import APIRouter, UploadFile, File
from pathlib import Path
import shutil
import uuid

from app.services.image_service.predictor import predict_image
from app.services.upload_service import get_upload_service

upload_service = get_upload_service()

router = APIRouter(prefix="/images", tags=["Images"])

UPLOAD_DIR = Path("uploads/images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_and_predict(file: UploadFile = File(...)):

    file_extension = file.filename.split(".")[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 👇 prediction step
    result = await predict_image(str(file_path))

    return {
        "success": True,
        "message": "Processed successfully",
        "data": {
            "file": unique_filename,
            "prediction": result
        }
    }
        # Call predictor
    prediction_result = await predict_image(str(file_path))

    # Create upload record
    upload_record = {
        "file_name": unique_filename,
        "file_path": str(file_path),
        "prediction": prediction_result,   # ← store result here
        "error_message": None
    }

    # Save to DB
    await upload_service.save(upload_record)

    return {
        "success": True,
        "message": "Processed & saved to MongoDB",
        "data": {
            "file": unique_filename,
            "prediction": prediction_result
        }
    }                                                                           