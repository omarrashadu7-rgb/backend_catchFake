import os
from datetime import datetime, timezone
from typing import Optional, List
from bson import ObjectId
from fastapi import UploadFile, HTTPException, status, BackgroundTasks


from app.models.upload import UploadCreate, UploadResponse, UploadType, UploadStatus
from app.services.image_service.predictor import predict_image, AIServiceUnavailable
from app.services.video_service.predictor import predict_video
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.middleware.error_handler import ValidationError, FileProcessingError
from app.middleware.activity_logger import log_activity
from app.models.admin import ActivityAction
from app.database.mongodb import get_db



settings = get_settings()
logger = get_logger(__name__)

# Allowed MIME types grouped by media type
_VALID_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}
_VALID_VIDEO_MIME = {"video/mp4", "video/webm", "video/quicktime"}


def _serialize_upload(doc: dict) -> dict:
    """Convert a raw MongoDB upload document to a flat Python dict."""
    doc["id"] = str(doc.pop("_id"))
    return doc


def _build_heatmap_url(heatmap_path: Optional[str]) -> Optional[str]:
    """
    Convert a server filesystem heatmap path to a public-facing URL.

    Example:
        uploads/heatmaps/abc.png  →  /uploads/heatmaps/abc.png
    """
    if not heatmap_path:
        return None
    # Normalise path separators and ensure it starts with /
    normalized = heatmap_path.replace("\\", "/")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized


def _apply_prediction_result(doc: dict, result: dict, source: str) -> None:
    """Persist the shared prediction fields returned by an isolated AI service."""
    doc["status"] = UploadStatus.DONE
    doc["prediction"] = result.get("prediction")
    doc["confidence"] = result.get("confidence")
    doc["processing_time"] = result.get("processing_time")
    doc["result_source"] = result.get("result_source", source)
    doc["heatmap_url"] = result.get("heatmap_url")
    doc["report_path"] = None
    doc["error_message"] = None



class UploadService:
    def __init__(self, db):
        self.db = db
        self.uploads = db["uploads"]

    async def upload_file(
        self,
        user_id: str,
        file: UploadFile,
        background_tasks: BackgroundTasks,
    ) -> UploadResponse:
        """
        Saves an uploaded file to disk and records metadata in MongoDB.
        - Images: predicted synchronously, result stored immediately.
        - Videos: saved and queued for background processing.
        """
        logger.info(f"Upload initiated — user={user_id}, file={file.filename}")

        # ── Validate MIME type ────────────────────────────────────────────────
        content_type = (file.content_type or "").lower()
        original_filename = file.filename or "unknown"

        if content_type in _VALID_IMAGE_MIME:
            file_type = UploadType.IMAGE
            subdir = "images"
        elif content_type in _VALID_VIDEO_MIME:
            file_type = UploadType.VIDEO
            subdir = "videos"
        else:
            logger.warning(f"Rejected unsupported MIME type: {content_type}")
            raise ValidationError(
                "Unsupported file type. Accepted: JPEG, PNG, WEBP images or MP4, WEBM, MOV videos."
            )

        # ── Validate and sanitize file extension ─────────────────────────────
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov"}
        if ext not in allowed_extensions:
            logger.warning(f"Rejected file with extension: {ext}")
            raise ValidationError(f"File extension '{ext}' is not allowed.")

        # ── Save file to the appropriate subdirectory ─────────────────────────
        target_dir = os.path.join(settings.upload_dir, subdir)
        os.makedirs(target_dir, exist_ok=True)

        unique_filename = f"{ObjectId()}{ext}"
        file_path = os.path.join(target_dir, unique_filename)

        try:
            with open(file_path, "wb") as out_file:
                while chunk := await file.read(1024 * 1024):  # 1 MB chunks
                    out_file.write(chunk)
            logger.info(f"File saved to disk: {file_path}")
        except Exception as e:
            logger.error(f"File write failed: {e}")
            raise FileProcessingError("Could not save file to disk.")
        finally:
            await file.close()

        # ── Build the MongoDB document ─────────────────────────────────────────
        now = datetime.now(timezone.utc)
        doc = {
            "user_id":   user_id,
            "filename":  original_filename,
            "original_filename": original_filename,
            "media_type": content_type,
            "file_path": file_path,
            "type":      file_type,
            "file_type": file_type.value,
            "created_at": now,
        }

        if file_type == UploadType.IMAGE:
            # Predict synchronously for images (fast API call)
            try:
                result = await predict_image(file_path)
                _apply_prediction_result(doc, result, "image_service")
            except (RuntimeError, AIServiceUnavailable) as e:
                logger.error(f"Image prediction failed: {e}")
                doc["status"] = UploadStatus.FAILED
                doc["prediction"] = None
                doc["confidence"] = None
                doc["processing_time"] = None
                doc["result_source"] = "image_service"
                doc["error_message"] = str(e)
        else:
            # Queue video for background processing
            doc["status"] = UploadStatus.QUEUED
            doc["prediction"] = None
            doc["confidence"] = None
            doc["processing_time"] = None
            doc["result_source"] = "video_service"
            doc["error_message"] = None

        inserted = await self.uploads.insert_one(doc)
        doc["_id"] = inserted.inserted_id

        if file_type == UploadType.VIDEO:
            background_tasks.add_task(
                self.process_video_background,
                str(inserted.inserted_id),
                file_path,
            )
            logger.info(f"Video queued for background processing — doc_id={inserted.inserted_id}")

        # ── Log the upload activity ────────────────────────────────────────────
        log_action = (
            ActivityAction.UPLOAD_IMAGE if file_type == UploadType.IMAGE
            else ActivityAction.UPLOAD_VIDEO
        )
        await log_activity(
            db=self.db,
            user_id=user_id,
            user_email="",   # resolved below if needed; kept lightweight here
            user_name="",
            action=log_action,
            details={
                "upload_id":        str(inserted.inserted_id),
                "filename":         original_filename,
                "file_type":        file_type.value,
                "prediction":       doc.get("prediction"),
                "confidence":       doc.get("confidence"),
                "status":           doc.get("status"),
            },
        )

        return UploadResponse(**_serialize_upload(doc))

    async def process_video_background(self, doc_id: str, file_path: str) -> None:
        """
        Background task: runs video inference and updates MongoDB with the result.
        Called by FastAPI BackgroundTasks after the HTTP response is sent.
        """
        logger.info(f"[BG] Starting video processing — doc_id={doc_id}")
        try:
            await self.uploads.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {"status": UploadStatus.PROCESSING}},
            )

            result = await predict_video(file_path)

            await self.uploads.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {
                    "status": UploadStatus.DONE,
                    "prediction": result.get("prediction"),
                    "confidence": result.get("confidence"),
                    "processing_time": result.get("processing_time"),
                    "result_source": result.get("result_source", "video_service"),
                    "heatmap_url": result.get("heatmap_url"),
                    "report_path": None,
                    "error_message": None,
                }},
            )
            logger.info(f"[BG] Video processing complete — doc_id={doc_id}, result={result}")

        except Exception as e:
            logger.error(f"[BG] Video processing failed — doc_id={doc_id}: {e}", exc_info=True)
            await self.uploads.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {
                    "status": UploadStatus.FAILED,
                    "processing_time": None,
                    "result_source": "video_service",
                    "error_message": str(e),
                }},
            )

    async def get_uploads_by_user(self, user_id: str) -> List[UploadResponse]:
        """Fetch all upload records for a specific user, newest first."""
        cursor = self.uploads.find({"user_id": user_id}).sort("created_at", -1)
        docs = await cursor.to_list(length=100)
        return [UploadResponse(**_serialize_upload(doc)) for doc in docs]

    async def get_upload_by_id(self, user_id: str, upload_id: str) -> Optional[UploadResponse]:
        """
        Fetch a single upload by its ID.
        Returns None if not found or if it belongs to a different user.
        """
        try:
            oid = ObjectId(upload_id)
        except Exception:
            return None

        doc = await self.uploads.find_one({"_id": oid, "user_id": user_id})
        if not doc:
            return None
        return UploadResponse(**_serialize_upload(doc))

async def get_upload_service() -> UploadService:
    """FastAPI dependency that provides a ready-to-use UploadService."""
    from app.database.mongodb import get_db
    return UploadService(await get_db())
    
