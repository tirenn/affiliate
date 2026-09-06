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
    
    # Database: Supports SQLite (aiosqlite) or PostgreSQL (asyncpg)
    DATABASE_URL: str = f"sqlite+aiosqlite:///{DATA_DIR / 'affiliate.db'}"
    
    # OpenRouter API base
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    
    # Browser timeout in milliseconds
    BROWSER_TIMEOUT_MS: int = 45000
    
    # Storage Paths
    DATA_PATH: str = str(DATA_DIR)
    SCREENSHOTS_PATH: str = str(SCREENSHOTS_DIR)
    SESSIONS_PATH: str = str(SESSIONS_DIR)

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
