from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from policy import PolicyError, load_runtime_policy
from runtime_worker import RuntimeWorker
from schemas import InstallPackageRequest, RunCodeRequest, SessionCreateResponse, ToolResult

BASE_DIR = Path(__file__).resolve().parents[1]
POLICY_PATH = BASE_DIR / "mvp-policy.yaml"
RUNTIME_ROOT = BASE_DIR / ".runtime"

policy = load_runtime_policy(POLICY_PATH)
worker = RuntimeWorker(root=RUNTIME_ROOT, policy=policy)

app = FastAPI(title="Agent Runtime Fabric MVP", version="0.2.0")


class ExportRequest(BaseModel):
    session_id: str
    relative_path: str


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "policy": policy.name}


@app.post("/sessions", response_model=SessionCreateResponse)
def create_session() -> SessionCreateResponse:
    session_id = f"sess-{uuid.uuid4().hex[:12]}"
    workspace = worker.workspace_for_session(session_id)
    return SessionCreateResponse(
        session_id=session_id,
        workspace_path=str(workspace),
        ttl_seconds=policy.ttl_seconds,
    )


@app.post("/tools/run_code", response_model=ToolResult)
def run_code(request: RunCodeRequest) -> ToolResult:
    try:
        return worker.run_code(request)
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc)) from exc
    except PolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/tools/install_package", response_model=ToolResult)
def install_package(request: InstallPackageRequest) -> ToolResult:
    try:
        return worker.install_package(request)
    except PolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.post("/tools/export_artifact")
def export_artifact(request: ExportRequest) -> dict[str, str]:
    try:
        exported = worker.export_artifact(request.session_id, request.relative_path)
        return {"artifact_path": str(exported)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PolicyError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.delete("/sessions/{session_id}")
def reset_session(session_id: str) -> dict[str, str]:
    worker.reset_session(session_id)
    return {"status": "reset", "session_id": session_id}
