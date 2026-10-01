from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Locally, values come from backend/.env (development). On Vercel there is no .env file
    # (it is excluded by .vercelignore); values come from the project's environment variables.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"

    database_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_jwt_secret: str = ""
    jwt_audience: str = "authenticated"

    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    # Business defaults (V1 is single-currency / single-timezone)
    timezone: str = "Asia/Kolkata"
    currency: str = "INR"

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        """Fail fast at startup instead of serving a half-configured production API."""
        if self.environment != "production":
            return self
        problems = []
        if not self.database_url:
            problems.append("DATABASE_URL is required")
        if not self.supabase_url.startswith("https://"):
            problems.append("SUPABASE_URL must be an https URL")
        origins = self.cors_origin_list
        if not origins:
            problems.append("CORS_ORIGINS is required")
        for origin in origins:
            if not origin.startswith("https://") or "localhost" in origin:
                problems.append(f"CORS origin {origin!r} must be an https production URL")
        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
