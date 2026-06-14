from fastapi import APIRouter, UploadFile, File, Depends
from pathlib import Path
import shutil
import uuid

from app.services.image_service.predictor import predict_image
from app.core.security import get_current_user
from app.models.user import UserInDB

router = APIRouter(prefix="/images", tags=["Images"])

UPLOAD_DIR = Path("uploads/images")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_and_predict(
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_user),
):

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
