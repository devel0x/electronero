from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RuntimePolicy(BaseModel):
    session_ttl_seconds: int = 3600
    max_execution_seconds: int = 30
    max_output_bytes: int = 200_000
    max_memory_mb: int = 1024
    network_mode: Literal["deny", "allowlisted"] = "allowlisted"


class SessionState(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    golden_image: str = "runtime-golden-v2-node-python"
    status: Literal["active", "resetting", "destroyed"] = "active"
    policy: RuntimePolicy = Field(default_factory=RuntimePolicy)


# Deployment/runtime tools
class CloneRepoRequest(BaseModel):
    session_id: str
    repo_url: str
    target_dir: str


class CheckoutRefRequest(BaseModel):
    session_id: str
    repo_dir: str
    ref: str


class DetectStackRequest(BaseModel):
    session_id: str
    repo_dir: str


class InstallNodeDepsRequest(BaseModel):
    session_id: str
    repo_dir: str
    frozen_lockfile: bool = True


class InstallPythonDepsRequest(BaseModel):
    session_id: str
    repo_dir: str
    requirements_file: str = "requirements.txt"


class WriteEnvFileRequest(BaseModel):
    session_id: str
    repo_dir: str
    env: dict[str, str]


class StartProcessRequest(BaseModel):
    session_id: str
    repo_dir: str
    name: str
    command: list[str]
    port: Optional[int] = None


class StopProcessRequest(BaseModel):
    session_id: str
    name: str


class CheckPortRequest(BaseModel):
    session_id: str
    port: int
    host: str = "127.0.0.1"


class HttpHealthCheckRequest(BaseModel):
    session_id: str
    url: str


class StreamLogsRequest(BaseModel):
    session_id: str
    name: str
    lines: int = 80


class CapturePreviewMetadataRequest(BaseModel):
    session_id: str
    name: str
    base_url: Optional[str] = None


class ExportArtifactsRequest(BaseModel):
    session_id: str
    source_dir: str


# Safe coding/file tools
class RunCodeRequest(BaseModel):
    session_id: str
    language: Literal["python", "node"]
    code: str
    timeout_seconds: Optional[int] = None


class InstallPackageRequest(BaseModel):
    session_id: str
    ecosystem: Literal["python", "node"]
    package: str
    version: Optional[str] = None


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
