import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SESSIONS_DIR = DATA_DIR / "sessions"

DATA_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Threads Affiliate Bot"
    
    # Database: Supports SQLite (aiosqlite) or PostgreSQL (asyncpg) - loaded strictly from .env
    DATABASE_URL: str
    
    # Admin API Key / Passcode - loaded strictly from .env
    X_ADMIN_KEY: str = ""
    ADMIN_PASSCODE: str = ""

    # Service Port - loaded strictly from .env
    PORT: int

    @property
    def admin_key(self) -> str:
        return self.X_ADMIN_KEY or self.ADMIN_PASSCODE
    
    # OpenRouter API base
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Browser timeout in milliseconds
    BROWSER_TIMEOUT_MS: int = 45000
    
    # Storage Paths
    DATA_PATH: str = str(DATA_DIR)
    SCREENSHOTS_PATH: str = str(SCREENSHOTS_DIR)
    SESSIONS_PATH: str = str(SESSIONS_DIR)

    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR.parent / ".env"), str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
