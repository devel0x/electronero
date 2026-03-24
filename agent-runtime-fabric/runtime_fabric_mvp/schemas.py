from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class Language(str, Enum):
    python = "python"
    nodejs = "nodejs"


class SessionCreateResponse(BaseModel):
    session_id: str
    workspace_path: str
    ttl_seconds: int


class RunCodeRequest(BaseModel):
    session_id: str = Field(min_length=6)
    language: Language
    code: str = Field(min_length=1)
    timeout_seconds: int = Field(default=20, ge=1, le=120)


class ToolResult(BaseModel):
    ok: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class InstallPackageRequest(BaseModel):
    session_id: str = Field(min_length=6)
    language: Language
    registry: str = Field(min_length=3)
    package: str = Field(min_length=1)
    version: str | None = None
