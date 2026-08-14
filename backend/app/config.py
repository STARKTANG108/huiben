from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    provider_story: str = "mock"
    provider_script: str = "mock"
    provider_storyboard: str = "mock"
    provider_image: str = "mock"
    provider_tts: str = "mock"
    provider_bgm: str = "mock"
    provider_video: str = "mock"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    cosyvoice_api_key: str | None = None
    image_api_key: str | None = None

    storage_dir: str = "storage"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        if not path.is_absolute():
            # Resolve relative to backend/ (where uvicorn is typically started)
            path = Path(__file__).resolve().parent.parent / path
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
