from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from models import (
    ArtifactRequest,
    BracketTrackerRequest,
    FileRequest,
    FunctionsMappingRequest,
    InstallPackageRequest,
    RunCodeRequest,
    RuntimePolicy,
    SearchInFilesRequest,
    ToolLog,
    WriteFileRequest,
)
from policy import validate_install
from runtime_manager import RuntimeManager
from storage import PersistenceStore

app = FastAPI(title="Agent Runtime Fabric", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

runtime = RuntimeManager(Path("/tmp/runtime"))
persistence = PersistenceStore(Path("../persistence"))
package_state: dict[str, dict[str, set[str]]] = {}


def log_tool(session_id: str, tool: str, request: dict, result: dict) -> None:
    persistence.append_tool_log(ToolLog(session_id=session_id, tool=tool, request=request, result=result))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "component": "execution-layer"}


@app.post("/sessions")
def create_session(policy: RuntimePolicy | None = None) -> dict:
    state = runtime.create_session(policy)
    package_state[state.session_id] = {"python": set(), "node": set()}
    result = state.model_dump(mode="json")
    log_tool(state.session_id, "create_session", {}, result)
    return result


@app.post("/session_reset/{session_id}")
def session_reset(session_id: str) -> dict:
    try:
        state = runtime.reset_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    result = state.model_dump(mode="json")
    log_tool(session_id, "session_reset", {}, result)
    return result


@app.post("/run_code")
def run_code(request: RunCodeRequest) -> dict:
    try:
        state = runtime.get_session(request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    timeout = request.timeout_seconds or state.policy.max_execution_seconds
    timeout = min(timeout, state.policy.max_execution_seconds)

    result = runtime.run_code(request.language, request.code, timeout)
    output_bytes = len((result.get("stdout", "") + result.get("stderr", "")).encode("utf-8"))
    if output_bytes > state.policy.max_output_bytes:
        result = {
            "exit_code": 1,
            "stdout": "",
            "stderr": "output truncated by policy",
            "policy_violation": "max_output_bytes",
        }

    log_tool(request.session_id, "run_code", request.model_dump(), result)
    return result


@app.post("/install_package")
def install_package(request: InstallPackageRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    try:
        validate_install(request.package, request.version)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pkg = request.package if request.version is None else f"{request.package}=={request.version}"
    package_state[request.session_id][request.ecosystem].add(pkg)
    manifest = persistence.write_manifest(
        request.session_id,
        request.ecosystem,
        sorted(package_state[request.session_id][request.ecosystem]),
    )

    result = {
        "status": "recorded",
        "ecosystem": request.ecosystem,
        "package": pkg,
        "manifest": str(manifest),
        "note": "MVP logs installs; worker-side installer would apply with allowlisted registry resolver.",
    }
    log_tool(request.session_id, "install_package", request.model_dump(), result)
    return result


@app.post("/read_file")
def read_file(request: FileRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        path = runtime.resolve_runtime_path(request.path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    text = path.read_text(encoding="utf-8", errors="ignore")
    result = {"path": request.path, "content": text}
    log_tool(request.session_id, "read_file", request.model_dump(), {"path": request.path, "bytes": len(text)})
    return result


@app.post("/write_file")
def write_file(request: WriteFileRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        path = runtime.resolve_runtime_path(request.path, must_be_writable=True)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(request.content, encoding="utf-8")
    result = {"path": request.path, "bytes": len(request.content)}
    log_tool(request.session_id, "write_file", request.model_dump(), result)
    return result


@app.post("/list_directory")
def list_directory(request: FileRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        path = runtime.resolve_runtime_path(request.path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=404, detail="directory not found")

    entries = [
        {"name": child.name, "type": "dir" if child.is_dir() else "file"}
        for child in sorted(path.iterdir(), key=lambda p: p.name)
    ]
    result = {"path": request.path, "entries": entries}
    log_tool(request.session_id, "list_directory", request.model_dump(), {"count": len(entries)})
    return result


@app.post("/search_in_files")
def search_in_files(request: SearchInFilesRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        root = runtime.resolve_runtime_path(request.root)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="root directory not found")

    hits = runtime.search_in_files(root, request.pattern)
    result = {"count": len(hits), "hits": hits}
    log_tool(request.session_id, "search_in_files", request.model_dump(), {"count": len(hits)})
    return result


@app.post("/functions_mapping")
def functions_mapping(request: FunctionsMappingRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        path = runtime.resolve_runtime_path(request.path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    code = path.read_text(encoding="utf-8", errors="ignore")
    mapping = runtime.functions_mapping(code)
    result = {"functions": mapping}
    log_tool(request.session_id, "functions_mapping", request.model_dump(), {"count": len(mapping)})
    return result


@app.post("/bracket_tracker")
def bracket_tracker(request: BracketTrackerRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        path = runtime.resolve_runtime_path(request.path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    code = path.read_text(encoding="utf-8", errors="ignore")
    result = runtime.bracket_tracker(code)
    log_tool(request.session_id, "bracket_tracker", request.model_dump(), result)
    return result


@app.post("/export_artifact")
def export_artifact(request: ArtifactRequest) -> dict:
    try:
        runtime.get_session(request.session_id)
        source = runtime.resolve_runtime_path(request.source_path)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not source.exists() or not source.is_file():
        raise HTTPException(status_code=404, detail="artifact source not found")

    artifact_dir = Path("../persistence/artifacts") / request.session_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    target = artifact_dir / source.name
    target.write_bytes(source.read_bytes())

    result = {"artifact": str(target), "bytes": target.stat().st_size}
    log_tool(request.session_id, "export_artifact", request.model_dump(), result)
    return result


@app.get("/logs")
def logs(limit: int = 100) -> dict:
    return {"logs": persistence.read_logs(limit=limit)}
