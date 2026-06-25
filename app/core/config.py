from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import os


class Settings(BaseSettings):
    # Application
    app_name: str = "DeepFake Detection API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",   # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:5500",   # VS Code Live Server
        "http://127.0.0.1:5500",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "null",                    # file:// origin (open-from-disk)
        "https://catch-fake.vercel.app",    # Production frontend v1
        "https://catch-fake2.vercel.app",   # Production frontend v2
    ]

    # Storage
    upload_dir: str = "uploads"

    @field_validator("upload_dir", mode="before")
    @classmethod
    def resolve_upload_dir(cls, v: str) -> str:
        # Vercel has a read-only filesystem — only /tmp is writable
        if os.environ.get("VERCEL"):
            return "/tmp/uploads"
        return v

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "deepfake_db"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60       # 1 hour default
    jwt_refresh_expire_minutes: int = 10080  # 7 days default

    # Admin
    # Stored as a plain string to avoid pydantic-settings JSON-parsing issues
    # with list[str] fields when the env var is empty or comma-separated.
    # Use the `admin_emails` property to get a parsed Python list.
    # In .env:  ADMIN_EMAILS=alice@example.com,bob@example.com
    admin_emails_raw: str = ""

    @property
    def admin_emails(self) -> list[str]:
        """Return the parsed list of admin emails (lowercased, stripped)."""
        return [e.strip().lower() for e in self.admin_emails_raw.split(",") if e.strip()]

    # HuggingFace Inference API
    # Replace with your token in .env — never commit the real value
    hf_token: str = "HF_TOKEN_2"
    hf_model_url: str = "https://api-inference.huggingface.co/models/mohamedahmed2003/deepfake-detector"

    # HuggingFace Space (Gradio) API
    hf_space_id: str = "Ahmedkhairy2/deepfake"
    hf_space_api_name: str = "/analyze"

    # HuggingFace Space (Gradio) API for video
    hf_video_space_id: str = "mohamedahmed2003/deepfake-detector"
    hf_video_space_api_name: str = "/analyze"

    # Video processing
    # Number of evenly-spaced frames extracted per video for prediction
    video_sample_frames: int = 16

    # Isolated AI services
    image_ai_service_url: str = "http://localhost:9001"
    video_ai_service_url: str = "http://localhost:9002"
    ai_request_timeout_seconds: float = 300.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
