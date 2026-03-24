from typing import Optional

import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

from models import (
    ArtifactRequest,
    BracketTrackerRequest,
    CapturePreviewMetadataRequest,
    CheckPortRequest,
    CheckoutRefRequest,
    CloneRepoRequest,
    DetectStackRequest,
    ExportArtifactsRequest,
    FileRequest,
    FunctionsMappingRequest,
    HttpHealthCheckRequest,
    InstallNodeDepsRequest,
    InstallPackageRequest,
    InstallPythonDepsRequest,
    RunCodeRequest,
    RuntimePolicy,
    SearchInFilesRequest,
    StartProcessRequest,
    StopProcessRequest,
    StreamLogsRequest,
    ToolLog,
    WriteEnvFileRequest,
    WriteFileRequest,
)
from runtime_manager import RuntimeManager
from storage import PersistenceStore

app = FastAPI(title="Agent Runtime Fabric", version="0.3.0")
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

ALLOWED_TOOLS = {
    # Deployment/runtime
    "clone_repo",
    "checkout_ref",
    "detect_stack",
    "install_node_deps",
    "install_python_deps",
    "write_env_file",
    "start_process",
    "stop_process",
    "check_port",
    "http_health_check",
    "stream_logs",
    "capture_preview_metadata",
    "export_artifacts",
    # Safe toolset
    "run_code",
    "install_package",
    "read_file",
    "write_file",
    "list_directory",
    "search_in_files",
    "functions_mapping",
    "bracket_tracker",
    "export_artifact",
    "session_reset",
}


def log_tool(session_id: str, tool: str, request: dict, result: dict) -> None:
    if tool not in ALLOWED_TOOLS and tool != "create_session":
        raise ValueError(f"disallowed tool: {tool}")
    persistence.append_tool_log(ToolLog(session_id=session_id, tool=tool, request=request, result=result))


def ensure_session(session_id: str) -> RuntimePolicy:
    try:
        return runtime.get_session(session_id).policy
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "component": "runtime-tools-gateway", "tools": sorted(ALLOWED_TOOLS)}


@app.post("/sessions")
def create_session(policy: Optional[RuntimePolicy] = None) -> dict:
    state = runtime.create_session(policy)
    package_state[state.session_id] = {"python": set(), "node": set()}
    result = state.model_dump(mode="json")
    log_tool(state.session_id, "create_session", {}, result)
    return result


@app.post("/session_reset/{session_id}")
def session_reset(session_id: str) -> dict:
    ensure_session(session_id)
    state = runtime.reset_session(session_id)
    result = state.model_dump(mode="json")
    log_tool(session_id, "session_reset", {}, result)
    return result


# Deployment/runtime tools endpoints
@app.post("/clone_repo")
def clone_repo(request: CloneRepoRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.clone_repo(request.session_id, request.repo_url, request.target_dir)
    log_tool(request.session_id, "clone_repo", request.model_dump(), result)
    return result


@app.post("/checkout_ref")
def checkout_ref(request: CheckoutRefRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.checkout_ref(request.session_id, request.repo_dir, request.ref)
    log_tool(request.session_id, "checkout_ref", request.model_dump(), result)
    return result


@app.post("/detect_stack")
def detect_stack(request: DetectStackRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.detect_stack(request.session_id, request.repo_dir)
    log_tool(request.session_id, "detect_stack", request.model_dump(), result)
    return result


@app.post("/install_node_deps")
def install_node_deps(request: InstallNodeDepsRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.install_node_deps(request.session_id, request.repo_dir, request.frozen_lockfile)
    log_tool(request.session_id, "install_node_deps", request.model_dump(), result)
    return result


@app.post("/install_python_deps")
def install_python_deps(request: InstallPythonDepsRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.install_python_deps(request.session_id, request.repo_dir, request.requirements_file)
    log_tool(request.session_id, "install_python_deps", request.model_dump(), result)
    return result


@app.post("/write_env_file")
def write_env_file(request: WriteEnvFileRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.write_env_file(request.session_id, request.repo_dir, request.env)
    log_tool(request.session_id, "write_env_file", request.model_dump(), result)
    return result


@app.post("/start_process")
def start_process(request: StartProcessRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.start_process(request.session_id, request.repo_dir, request.name, request.command, request.port)
    log_tool(request.session_id, "start_process", request.model_dump(), result)
    return result


@app.post("/stop_process")
def stop_process(request: StopProcessRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.stop_process(request.session_id, request.name)
    log_tool(request.session_id, "stop_process", request.model_dump(), result)
    return result


@app.post("/check_port")
def check_port(request: CheckPortRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.check_port(request.host, request.port)
    log_tool(request.session_id, "check_port", request.model_dump(), result)
    return result


@app.post("/http_health_check")
def http_health_check(request: HttpHealthCheckRequest) -> dict:
    ensure_session(request.session_id)
    response = requests.get(request.url, timeout=5)
    result = {"ok": response.ok, "status_code": response.status_code, "url": request.url, "body": response.text[:300]}
    log_tool(request.session_id, "http_health_check", request.model_dump(), result)
    return result


@app.post("/stream_logs")
def stream_logs(request: StreamLogsRequest) -> dict:
    ensure_session(request.session_id)
    result = runtime.stream_logs(request.session_id, request.name, request.lines)
    log_tool(request.session_id, "stream_logs", request.model_dump(), {"lines": result.get("lines", 0)})
    return result


@app.post("/capture_preview_metadata")
def capture_preview_metadata(request: CapturePreviewMetadataRequest) -> dict:
    ensure_session(request.session_id)
    logs = runtime.stream_logs(request.session_id, request.name, lines=200)
    health = None
    if request.base_url:
        try:
            r = requests.get(request.base_url, timeout=3)
            health = {"ok": r.ok, "status": r.status_code, "title_hint": r.text[:120]}
        except Exception as exc:  # noqa: BLE001
            health = {"ok": False, "error": str(exc)}
    result = {"name": request.name, "base_url": request.base_url, "health": health, "log_lines": logs.get("lines", 0), "log_path": logs.get("path")}
    log_tool(request.session_id, "capture_preview_metadata", request.model_dump(), result)
    return result


@app.post("/export_artifacts")
def export_artifacts(request: ExportArtifactsRequest) -> dict:
    ensure_session(request.session_id)
    src = runtime.resolve_workspace_path(request.session_id, request.source_dir)
    if not src.exists() or not src.is_dir():
        raise HTTPException(status_code=404, detail="source_dir not found")
    out_root = Path("../persistence/artifacts") / request.session_id
    out_root.mkdir(parents=True, exist_ok=True)
    target = out_root / src.name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src, target)
    result = {"artifact_dir": str(target), "file_count": sum(1 for p in target.rglob('*') if p.is_file())}
    log_tool(request.session_id, "export_artifacts", request.model_dump(), result)
    return result


# Safe tools endpoints
@app.post("/run_code")
def run_code(request: RunCodeRequest) -> dict:
    policy = ensure_session(request.session_id)
    timeout = min(request.timeout_seconds or policy.max_execution_seconds, policy.max_execution_seconds)
    result = runtime.run_code(request.language, request.code, timeout)
    output_bytes = len((result.get("stdout", "") + result.get("stderr", "")).encode("utf-8"))
    if output_bytes > policy.max_output_bytes:
        result = {"exit_code": 1, "stdout": "", "stderr": "output truncated by policy", "policy_violation": "max_output_bytes"}
    log_tool(request.session_id, "run_code", request.model_dump(), result)
    return result


@app.post("/install_package")
def install_package(request: InstallPackageRequest) -> dict:
    ensure_session(request.session_id)
    pkg = request.package if request.version is None else f"{request.package}=={request.version}"
    package_state[request.session_id][request.ecosystem].add(pkg)
    manifest = persistence.write_manifest(request.session_id, request.ecosystem, sorted(package_state[request.session_id][request.ecosystem]))
    result = {"status": "recorded", "ecosystem": request.ecosystem, "package": pkg, "manifest": str(manifest)}
    log_tool(request.session_id, "install_package", request.model_dump(), result)
    return result


@app.post("/list_directory")
def list_directory(request: FileRequest) -> dict:
    ensure_session(request.session_id)
    path = runtime.resolve_runtime_path(request.path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(status_code=404, detail="directory not found")
    entries = [{"name": c.name, "type": "dir" if c.is_dir() else "file"} for c in sorted(path.iterdir(), key=lambda p: p.name)]
    result = {"path": request.path, "entries": entries}
    log_tool(request.session_id, "list_directory", request.model_dump(), {"count": len(entries)})
    return result


@app.post("/read_file")
def read_file(request: FileRequest) -> dict:
    ensure_session(request.session_id)
    path = runtime.resolve_runtime_path(request.path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    content = path.read_text(encoding="utf-8", errors="ignore")
    result = {"path": request.path, "content": content}
    log_tool(request.session_id, "read_file", request.model_dump(), {"bytes": len(content)})
    return result


@app.post("/write_file")
def write_file(request: WriteFileRequest) -> dict:
    ensure_session(request.session_id)
    path = runtime.resolve_runtime_path(request.path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(request.content, encoding="utf-8")
    result = {"path": request.path, "bytes": len(request.content)}
    log_tool(request.session_id, "write_file", request.model_dump(), result)
    return result


@app.post("/search_in_files")
def search_in_files(request: SearchInFilesRequest) -> dict:
    ensure_session(request.session_id)
    root = runtime.resolve_runtime_path(request.root)
    if not root.exists() or not root.is_dir():
        raise HTTPException(status_code=404, detail="root directory not found")
    hits = runtime.search_in_files(root, request.pattern)
    result = {"count": len(hits), "hits": hits}
    log_tool(request.session_id, "search_in_files", request.model_dump(), {"count": len(hits)})
    return result


@app.post("/functions_mapping")
def functions_mapping(request: FunctionsMappingRequest) -> dict:
    ensure_session(request.session_id)
    path = runtime.resolve_runtime_path(request.path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    mapped = runtime.functions_mapping(path.read_text(encoding="utf-8", errors="ignore"))
    result = {"functions": mapped}
    log_tool(request.session_id, "functions_mapping", request.model_dump(), {"count": len(mapped)})
    return result


@app.post("/bracket_tracker")
def bracket_tracker(request: BracketTrackerRequest) -> dict:
    ensure_session(request.session_id)
    path = runtime.resolve_runtime_path(request.path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    result = runtime.bracket_tracker(path.read_text(encoding="utf-8", errors="ignore"))
    log_tool(request.session_id, "bracket_tracker", request.model_dump(), result)
    return result


@app.post("/export_artifact")
def export_artifact(request: ArtifactRequest) -> dict:
    ensure_session(request.session_id)
    src = runtime.resolve_runtime_path(request.source_path)
    if not src.exists() or not src.is_file():
        raise HTTPException(status_code=404, detail="artifact source not found")
    out_dir = Path("../persistence/artifacts") / request.session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / src.name
    target.write_bytes(src.read_bytes())
    result = {"artifact": str(target), "bytes": target.stat().st_size}
    log_tool(request.session_id, "export_artifact", request.model_dump(), result)
    return result


@app.get("/logs")
def logs(limit: int = 100) -> dict:
    return {"logs": persistence.read_logs(limit=limit)}
