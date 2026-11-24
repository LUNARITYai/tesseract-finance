from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://tf:tf@localhost:5434/tesseract_finance"
    dev_user_email: str = "dev@example.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
