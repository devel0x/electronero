from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class RuntimePolicy(BaseModel):
    session_ttl_seconds: int = 3600
    max_execution_seconds: int = 20
    max_output_bytes: int = 120_000
    max_memory_mb: int = 512
    max_cpu_seconds: int = 15
    network_mode: Literal["deny", "allowlisted"] = "allowlisted"
    writable_zones: list[str] = Field(
        default_factory=lambda: [
            "/runtime/workspaces",
            "/runtime/tmp",
            "/runtime/output",
            "/runtime/cache",
        ]
    )


class SessionState(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    golden_image: str = "runtime-golden-v1"
    status: Literal["active", "resetting", "destroyed"] = "active"
    policy: RuntimePolicy = Field(default_factory=RuntimePolicy)


class RunCodeRequest(BaseModel):
    session_id: str
    language: Literal["python", "node"]
    code: str
    timeout_seconds: int | None = None


class InstallPackageRequest(BaseModel):
    session_id: str
    ecosystem: Literal["python", "node"]
    package: str
    version: str | None = None


class FileRequest(BaseModel):
    session_id: str
    path: str


class WriteFileRequest(FileRequest):
    content: str


class SearchInFilesRequest(BaseModel):
    session_id: str
    root: str
    pattern: str


class FunctionsMappingRequest(BaseModel):
    session_id: str
    path: str


class BracketTrackerRequest(BaseModel):
    session_id: str
    path: str


class ArtifactRequest(BaseModel):
    session_id: str
    source_path: str


class ToolLog(BaseModel):
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str
    tool: str
    request: dict[str, Any]
    result: dict[str, Any]
