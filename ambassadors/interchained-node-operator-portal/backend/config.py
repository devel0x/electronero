"""Application configuration via environment variables."""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import AnyUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly typed application settings loaded from the environment."""

    app_name: str = "Interchained Operator Control Plane"
    environment: str = Field(default="development", description="Deployment environment name")
    redis_url: AnyUrl = Field(default="redis://localhost:6379/6", description="Redis connection URL")
    session_ttl_seconds: int = Field(default=60 * 60 * 24 * 7, ge=3600)
    monitor_interval_seconds: int = Field(default=60, ge=15)
    reward_distribution_hour_utc: int = Field(default=0, ge=0, le=23)
    audit_log_retention_days: int = Field(default=90, ge=7)
    allowed_cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    default_plan: str = Field(default="enterprise")

    model_config = SettingsConfigDict(env_prefix="PORTAL_", env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""

    return Settings()
