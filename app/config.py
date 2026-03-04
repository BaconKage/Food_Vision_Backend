from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "Food Vision Backend"
    mongodb_uri: str = Field(..., alias="MONGODB_URI")
    mongodb_db_name: str = Field(..., alias="MONGODB_DB_NAME")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field("gpt-4.1-mini", alias="OPENAI_MODEL")

    max_image_mb: int = Field(8, alias="MAX_IMAGE_MB")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    openai_max_retries: int = 3
    min_food_confidence: float = 0.45


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
