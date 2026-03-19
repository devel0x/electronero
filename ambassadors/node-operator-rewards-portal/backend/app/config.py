"""Configuration helpers for the Node Operator Rewards Portal backend."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic import BaseSettings, Field, RedisDsn, validator


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "Interchained Node Operator Rewards Portal"
    secret_key: str = Field(..., env="PORTAL_SECRET_KEY")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 60 * 60 * 4  # 4 hours
    redis_url: RedisDsn = Field("redis://localhost:6379/6", env="PORTAL_REDIS_URL")
    reward_pool_daily: float = Field(1000.0, env="PORTAL_REWARD_POOL_DAILY")
    initial_pool_balance: float = Field(100000.0, env="PORTAL_INITIAL_POOL_BALANCE")
    reward_distribution_interval_seconds: int = 60 * 60 * 24
    health_check_interval_seconds: int = 60
    rpc_timeout_seconds: float = Field(5.0, ge=0.1)
    admin_emails: List[str] = Field(default_factory=list, env="PORTAL_ADMIN_EMAILS")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("secret_key")
    def _validate_secret_key(cls, value: Optional[str]) -> str:
        if not value:
            raise ValueError(
                "PORTAL_SECRET_KEY must be provided via environment variables or a .env file."
            )
        if len(value) < 32:
            raise ValueError("PORTAL_SECRET_KEY must be at least 32 characters long.")
        return value

    @validator("admin_emails", pre=True)
    def _split_admin_emails(cls, value: str | List[str]) -> List[str]:
        if isinstance(value, list):
            return [email.strip().lower() for email in value if email]
        if not value:
            return []
        return [email.strip().lower() for email in value.split(",") if email.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()


def get_redis_url() -> str:
    """Convenience helper for retrieving the Redis connection string."""

    return str(get_settings().redis_url)
