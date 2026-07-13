"""
Configuration — environment variable management
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AccessAI"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_DEFAULT_MODEL: str = "llama3"
    OLLAMA_TIMEOUT: int = 120
    OLLAMA_MAX_RETRIES: int = 3

    # Scanner
    BROWSER_HEADLESS: bool = True
    SCAN_TIMEOUT: int = 60
    SCREENSHOT_ENABLED: bool = True
    MAX_PAGES_PER_SCAN: int = 5

    # Storage
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/accessai.db"
    REPORTS_DIR: str = "data/reports"
    SCREENSHOTS_DIR: str = "data/screenshots"

    # Security
    MAX_URL_LENGTH: int = 2048
    RATE_LIMIT_SCANS_PER_HOUR: int = 20

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
                return False
        return value

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
