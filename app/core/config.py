from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )

    APP_NAME: str = "enginelabs-2api"
    APP_VERSION: str = "4.0.0-Phoenix"
    DESCRIPTION: str = "一个将 cto.new (EngineLabs) API 转换为兼容 OpenAI 格式的高性能代理。实现全自动令牌续期，一劳永逸。"

    # --- 安全与网络 ---
    API_MASTER_KEY: Optional[str] = None
    NGINX_PORT: int = 8089
    API_REQUEST_TIMEOUT: int = 300

    # --- Clerk 认证凭证 ---
    CLERK_COOKIE: Optional[str] = None

    # --- 模型配置 ---
    DEFAULT_MODEL: str = "ClaudeSonnet4_5"
    KNOWN_MODELS: List[str] = ["ClaudeSonnet4_5", "GPT5"]

settings = Settings()
