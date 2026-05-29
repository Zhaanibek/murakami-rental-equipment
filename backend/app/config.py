import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Try to load env file from the project root if running locally
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "postgresql://rental_user:rental_secure_pass_2026@db:5432/rental_equipment_db"
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

settings = Settings()
