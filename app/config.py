"""Application configuration module using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""

    # Target Hospital Directory API
    DIRECTORY_API_BASE_URL: str = "https://hospital-directory.onrender.com"
    
    # Technical constraints (Section 4 of assignment spec)
    MAX_CSV_RECORDS: int = 20
    
    # Network and performance settings
    REQUEST_TIMEOUT_SECONDS: float = 30.0
    MAX_CONCURRENT_REQUESTS: int = 10
    
    # Server metadata
    APP_TITLE: str = "Hospital Bulk Processing System"
    APP_DESCRIPTION: str = (
        "High-performance Bulk Processing API integrating with Hospital Directory API "
        "to handle CSV uploads, concurrent record creation, batch activation, and progress tracking."
    )
    APP_VERSION: str = "1.0.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
