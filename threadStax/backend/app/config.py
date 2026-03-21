from pydantic import BaseModel


class Settings(BaseModel):
    redis_url: str = "redis://localhost:6379/7"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    redis_key_prefix: str = "tc:"
    cors_origin: str = "http://localhost:3000"


settings = Settings()
