from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.routers.auth_router import router as auth_router
from app.routers.image_router import router as image_router
from app.routers.video_router import router as video_router
from app.routers.report_router import router as report_router
from app.routers.admin_router import router as admin_router
from app.utils.temp_legacy.items_router import router as items_router
from app.utils.temp_legacy.health import router as legacy_health_router
from app.core.config import get_settings
from app.middleware.error_handler import DomainException
from app.core.logging_config import get_logger
from app.database.mongodb import get_db
settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up DeepFake Detection API...")

    try:
        for subdir in ["images", "videos", "heatmaps", "reports"]:
            os.makedirs(os.path.join(settings.upload_dir, subdir), exist_ok=True)
    except Exception:
        logger.warning("Could not create upload directories (read-only filesystem - expected on Vercel)")

    logger.info(
        "AI inference is delegated to isolated image/video services; "
        "backend will not import TensorFlow."
    )

    yield

    logger.info("Shutting down...")
   


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    description=(
        "DeepFake Detection System - REST API for image and video authenticity analysis. "
        "Upload media files to receive real/fake predictions powered by isolated AI services."
    ),
docs_url=None,
redoc_url=None
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Public API — JWT Bearer tokens, no cookies
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
BASE_DIR = Path(__file__).resolve().parent.parent

# Serve uploaded files (videos, images, heatmaps) as static assets
uploads_dir = os.path.join(os.getcwd(), settings.upload_dir)
try:
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
except Exception:
    logger.warning("Could not mount uploads directory (read-only filesystem - expected on Vercel)")

@app.exception_handler(DomainException)
async def domain_exception_handler(request: Request, exc: DomainException):
    logger.warning("Domain exception on %s %s: %s", request.method, request.url, exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": exc.message, "data": None},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled error on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error.", "data": None},
    )


@app.get("/health", tags=["Health"])
def health_check():
    """Health endpoint to verify API is running."""
    return {"success": True, "message": "API is healthy", "data": None}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(image_router, prefix="/api/v1")
app.include_router(video_router, prefix="/api/v1")
app.include_router(report_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(items_router, prefix="/api/v1")
# Including legacy health router just in case, but new /health is defined above
app.include_router(legacy_health_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
def root():
    return {
        "success": True,
        "message": f"Welcome to {settings.app_name} v{settings.app_version}. Visit /docs for the API.",
        "data": None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
