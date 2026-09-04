from functools import lru_cache
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "长期环境决策看板 API"
    environment: str = "development"
    database_url: str = "sqlite:///./dashboard.db"
    cors_origins: str = "http://localhost:3000"
    publication_timezone: str = "Asia/Shanghai"
    publication_cutoff_day: int = 15
    publication_cutoff_time: str = "23:59"
    publication_day: int = 20
    raw_data_dir: str = "data/raw"
    fred_api_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.publication_timezone)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
