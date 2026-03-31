from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gex_module import GexRunner

BASE_DIR = Path(__file__).resolve().parent
REPOS_DIR = Path("/workspace/repos")
RUNS_DIR = Path("/workspace/runs")
REPOS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="_Gex UI Runtime")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

runner = GexRunner()
RUN_CONTROL: dict[str, dict[str, Any]] = {}


class CloneRequest(BaseModel):
    git_url: str


class LoadLocalRequest(BaseModel):
    local_path: str


class RunRequest(BaseModel):
    repo: str
    mode: str = "sequential"
    file: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/repos")
def list_repos() -> list[dict[str, str]]:
    return [{"name": path.name, "path": str(path)} for path in sorted(REPOS_DIR.iterdir()) if path.is_dir()]


@app.post("/repos/clone")
def clone_repo(request: CloneRequest) -> dict[str, str]:
    name = request.git_url.rstrip("/").split("/")[-1].replace(".git", "")
    target = REPOS_DIR / name
    if target.exists():
        raise HTTPException(status_code=409, detail="Repo already exists")
    subprocess.run(["git", "clone", request.git_url, str(target)], check=True)
    return {"name": name, "path": str(target)}


@app.post("/repos/load")
def load_local_repo(request: LoadLocalRequest) -> dict[str, str]:
    source = Path(request.local_path).resolve()
    if not source.exists() or not source.is_dir():
        raise HTTPException(status_code=400, detail="Invalid local path")
    target = REPOS_DIR / source.name
    if target.exists():
        raise HTTPException(status_code=409, detail="Repo already loaded")
    shutil.copytree(source, target)
    return {"name": target.name, "path": str(target)}


@app.get("/repos/{repo_name}/tree")
def repo_tree(repo_name: str) -> list[dict[str, str]]:
    root = (REPOS_DIR / repo_name).resolve()
    if not root.exists():
        raise HTTPException(status_code=404, detail="Repo not found")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".git" not in path.parts:
            files.append({"path": str(path.relative_to(root)).replace("\\", "/")})
    return files


@app.get("/repos/{repo_name}/file")
def read_file(repo_name: str, path: str) -> dict[str, str]:
    root = (REPOS_DIR / repo_name).resolve()
    target = (root / path).resolve()
    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=403, detail="Invalid path")
    if not target.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": target.read_text(errors="replace")}


@app.post("/runs/start")
async def start_run(request: RunRequest) -> dict[str, str]:
    repo_path = (REPOS_DIR / request.repo).resolve()
    if not repo_path.exists():
        raise HTTPException(status_code=404, detail="Repo not found")

    run_id = datetime.utcnow().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
    run_dir = RUNS_DIR / run_id
    diff_dir = run_dir / "diffs"
    run_dir.mkdir(parents=True, exist_ok=True)
    diff_dir.mkdir(parents=True, exist_ok=True)

    queue: asyncio.Queue = asyncio.Queue()

    loop = asyncio.get_running_loop()
    thread_stop = __import__("threading").Event()

    def log(entry: dict) -> None:
        asyncio.run_coroutine_threadsafe(queue.put(entry), loop)

    async def worker() -> None:
        logs: list[dict] = []
        status = {"run_id": run_id, "status": "running", "repo": request.repo, "mode": request.mode, "file": request.file}
        (run_dir / "status.json").write_text(json.dumps(status, indent=2))
        try:
            if request.file:
                result = await asyncio.to_thread(runner.run_file, str(repo_path / request.file), stop_event=thread_stop, log=log)
            else:
                result = await asyncio.to_thread(runner.run_repo, str(repo_path), request.mode, stop_event=thread_stop, log=log)
            for diff in result["files"]:
                safe_name = diff["file"].replace("/", "__") + ".json"
                (diff_dir / safe_name).write_text(json.dumps(diff, indent=2))
            status["status"] = "completed"
        except Exception as exc:
            status["status"] = "error"
            status["error"] = str(exc)
            await queue.put({"type": "error", "message": str(exc)})
        finally:
            (run_dir / "status.json").write_text(json.dumps(status, indent=2))
            (run_dir / "logs.json").write_text(json.dumps(logs, indent=2))
            await queue.put({"type": "done", "run_id": run_id})

    task = asyncio.create_task(worker())
    RUN_CONTROL[run_id] = {"task": task, "queue": queue, "stop": thread_stop, "dir": run_dir}
    return {"run_id": run_id}


@app.post("/runs/{run_id}/stop")
async def stop_run(run_id: str) -> dict[str, str]:
    handle = RUN_CONTROL.get(run_id)
    if not handle:
        raise HTTPException(status_code=404, detail="Run not found")
    handle["stop"].set()
    return {"status": "stopping"}


@app.websocket("/ws/runs/{run_id}")
async def run_stream(ws: WebSocket, run_id: str) -> None:
    await ws.accept()
    handle = RUN_CONTROL.get(run_id)
    if not handle:
        await ws.send_json({"type": "error", "message": "Run not found"})
        await ws.close()
        return
    queue: asyncio.Queue = handle["queue"]
    while True:
        event = await queue.get()
        await ws.send_json(event)
        if event.get("type") == "done":
            break
    await ws.close()


@app.get("/runs/{run_id}/status")
def run_status(run_id: str) -> dict[str, Any]:
    run_dir = RUNS_DIR / run_id
    status_path = run_dir / "status.json"
    if not status_path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return json.loads(status_path.read_text())


@app.get("/runs/{run_id}/diffs")
def run_diffs(run_id: str) -> list[dict[str, Any]]:
    diff_dir = RUNS_DIR / run_id / "diffs"
    if not diff_dir.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    return [json.loads(path.read_text()) for path in sorted(diff_dir.glob("*.json"))]
