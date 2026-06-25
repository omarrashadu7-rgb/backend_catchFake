from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum




class UploadType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class UploadStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class UploadBase(BaseModel):
    filename: Optional[str] = Field(None, description="Original filename provided by the client")
    original_filename: Optional[str] = Field(None, description="Original filename preserved for prediction records")
    media_type: Optional[str] = Field(None, description="MIME type of the uploaded file")
    type: UploadType = Field(..., description="File type: image or video")
    file_type: Optional[str] = Field(None, description="File type value stored for analytics compatibility")
    status: UploadStatus = Field(default=UploadStatus.DONE, description="Upload processing status")
    prediction: Optional[str] = Field(None, description="Prediction result: Real or Fake")
    confidence: Optional[str] = Field(None, description="Prediction confidence score e.g. '99.50%'")
    fake_probability: Optional[str] = Field(None, description="Fake probability score e.g. '0.50%'")
    processing_time: Optional[float] = Field(None, description="AI service processing time in seconds")
    result_source: Optional[str] = Field(None, description="AI service that produced the prediction")
    error_message: Optional[str] = Field(None, description="Prediction error message when processing fails")
    heatmap_url: Optional[str] = Field(None, description="Public URL to the generated heatmap image")
    report_path: Optional[str] = Field(None, description="Server-side path to the generated PDF report")


class UploadCreate(UploadBase):
    user_id: str = Field(..., description="User ID of the uploader")
    file_path: str = Field(..., description="Local server path to the saved file")


class UploadResponse(UploadBase):
    id: str = Field(..., description="Upload MongoDB ObjectId as string")
    user_id: str = Field(..., description="User ID of the uploader")
    file_path: str = Field(..., description="Local server path to the saved file")
    created_at: datetime

    class Config:
        populate_by_name = True


class UploadInDB(UploadBase):
    id: str
    user_id: str
    file_path: str
    created_at: datetime

    class Config:
        populate_by_name = True


def upload_model(file_name: str, prediction: dict):

    return {
        "file_name": file_name,
        "prediction": prediction,
        "created_at": datetime.utcnow()
    }