from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_secret_key: str = Field("dev-secret-key")
    fernet_secret: str = Field("NzQzYTRhM2FjMjI5N2U3Y2YxZjI1MjJiMGY1ZjYyZTU=")
    database_url: str = Field("sqlite+aiosqlite:///data/db.sqlite")
    uvicorn_host: str = Field("127.0.0.1")
    uvicorn_port: int = Field(8000)
    session_cookie_name: str = Field("clinic_session")
    session_cookie_secure: bool = Field(False)
    csrf_secret: str = Field("dev-csrf-secret")
    log_level: str = Field("info")
    locale: str = Field("fr")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def base_path(self) -> Path:
        return Path(__file__).resolve().parent.parent

    @property
    def data_path(self) -> Path:
        return self.base_path / "data"

    @property
    def files_path(self) -> Path:
        return self.base_path / "files"

    @property
    def exports_path(self) -> Path:
        return self.base_path / "exports"

    @property
    def pdf_templates_path(self) -> Path:
        return self.base_path / "app" / "pdf_templates"

    @property
    def locale_path(self) -> Path:
        return self.base_path / "locales"

    @property
    def static_path(self) -> Path:
        return self.base_path / "app" / "static"

    @property
    def template_path(self) -> Path:
        return self.base_path / "app" / "templates"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.files_path.mkdir(parents=True, exist_ok=True)
    settings.exports_path.mkdir(parents=True, exist_ok=True)
    return settings

