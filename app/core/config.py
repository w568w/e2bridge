from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )

    APP_NAME: str = "e2bridge"
    APP_VERSION: str = "1.0.0"
    DESCRIPTION: str = "Convert cto.new API to OpenAI-compatible format"

    # --- Security & Network ---
    API_MASTER_KEY: Optional[str] = None
    API_REQUEST_TIMEOUT: int = 300

    # --- Clerk Authentication ---
    CLERK_COOKIE: Optional[str] = None
    CLERK_SESSION_ID: Optional[str] = None
    CLERK_ORGANIZATION_ID: Optional[str] = None

    # --- Model Configuration ---
    DEFAULT_MODEL: str = "ClaudeSonnet4_5"
    KNOWN_MODELS: List[str] = ["ClaudeSonnet4_5", "GPT5"]

settings = Settings()
