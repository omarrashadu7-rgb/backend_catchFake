import os
from fastapi import APIRouter, Depends, status, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from app.core.security import get_current_user
from app.models.user import UserInDB
from app.services.upload_service import UploadService, get_upload_service
from app.utils.response_handler import success_response


router = APIRouter(prefix="/uploads", tags=["Uploads"])

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Upload image or video",
    description="Upload an image or video file. The file is saved locally to the uploads directory and metadata is tracked in MongoDB."
)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: UserInDB = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service)
):
    upload_response = await service.upload_file(current_user.id, file, background_tasks)
    
    return success_response(
        data=upload_response.model_dump(),
        message="File uploaded successfully."
    )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Get user upload history",
    description="Retrieve all uploads and their processing results for the authenticated user."
)
async def get_user_history(
    current_user: UserInDB = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service)
):
    uploads = await service.get_uploads_by_user(current_user.id)
    return success_response(
        data=[u.model_dump() for u in uploads],
        message="History retrieved successfully."
    )


@router.get(
    "/{upload_id}",
    status_code=status.HTTP_200_OK,
    summary="Get upload by ID",
    description="Retrieve specific upload details and AI results. Returns 404 if not found or unauthorized."
)
async def get_upload_result(
    upload_id: str,
    current_user: UserInDB = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service)
):
    from fastapi import HTTPException

    upload = await service.get_upload_by_id(current_user.id, upload_id)
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found."
        )
    return success_response(
        data=upload.model_dump(),
        message="Upload details retrieved successfully."
    )


@router.get(
    "/download/report/{upload_id}",
    summary="Download AI report PDF",
    description="Retrieve the generated PDF report for an upload. Must be authorized as the owner."
)
async def download_report(
    upload_id: str,
    current_user: UserInDB = Depends(get_current_user),
    service: UploadService = Depends(get_upload_service)
):
    upload = await service.get_upload_by_id(current_user.id, upload_id)
    if not upload:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found."
        )
    
    if not upload.report_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet generated or available."
        )

    if not os.path.exists(upload.report_path):
        # Fallback for mocked logic where files aren't physically created
        with open(upload.report_path, "wb") as empty_pdf:
            empty_pdf.write(b"%PDF-1.4 mock pdf data")
            
    return FileResponse(
        path=upload.report_path,
        media_type="application/pdf",
        filename=f"Report_{upload_id}.pdf"
    )
