from __future__ import annotations

import ast
import json
import re
import socket
import subprocess
import tempfile
import uuid
from pathlib import Path

from models import RuntimePolicy, SessionState


class RuntimeManager:
    def __init__(self, runtime_root: Path):
        self.runtime_root = runtime_root
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, SessionState] = {}
        self.processes: dict[str, dict[str, subprocess.Popen]] = {}
        self.logs: dict[str, dict[str, Path]] = {}

    def create_session(self, policy: RuntimePolicy | None = None) -> SessionState:
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, policy=policy or RuntimePolicy())
        self.sessions[sid] = state
        self.processes[sid] = {}
        self.logs[sid] = {}

        for zone in ["workspaces", "tmp", "output", "cache", "readonly-base"]:
            (self.runtime_root / zone / sid).mkdir(parents=True, exist_ok=True)
        return state

    def get_session(self, session_id: str) -> SessionState:
        if session_id not in self.sessions:
            raise KeyError("unknown session")
        return self.sessions[session_id]

    def reset_session(self, session_id: str) -> SessionState:
        state = self.get_session(session_id)
        state.status = "resetting"
        for zone in ["workspaces", "tmp", "output", "cache"]:
            zone_path = self.runtime_root / zone / session_id
            if zone_path.exists():
                for item in sorted(zone_path.rglob("*"), reverse=True):
                    if item.is_file():
                        item.unlink(missing_ok=True)
                    elif item.is_dir():
                        item.rmdir()
        for zone in ["workspaces", "tmp", "output", "cache"]:
            (self.runtime_root / zone / session_id).mkdir(parents=True, exist_ok=True)
        state.status = "active"
        return state

    def resolve_workspace_path(self, session_id: str, path: str) -> Path:
        root = self.runtime_root / "workspaces" / session_id
        resolved = (root / path).resolve()
        if not str(resolved).startswith(str(root.resolve())):
            raise ValueError("path escapes session workspace")
        return resolved

    def resolve_runtime_path(self, runtime_path: str) -> Path:
        sanitized = runtime_path.strip()
        if ".." in sanitized:
            raise ValueError("invalid path")
        if sanitized.startswith("/runtime/workspaces/"):
            rel = sanitized[len("/runtime/") :]
            return self.runtime_root / rel
        if sanitized.startswith("/runtime/tmp/") or sanitized.startswith("/runtime/output/") or sanitized.startswith("/runtime/cache/"):
            rel = sanitized[len("/runtime/") :]
            return self.runtime_root / rel
        raise ValueError("path is outside allowed runtime zones")

    # Deployment/runtime tools
    def clone_repo(self, session_id: str, repo_url: str, target_dir: str) -> dict:
        target = self.resolve_workspace_path(session_id, target_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["git", "clone", "--depth", "1", repo_url, str(target)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {"ok": result.returncode == 0, "stdout": result.stdout, "stderr": result.stderr, "path": str(target)}

    def checkout_ref(self, session_id: str, repo_dir: str, ref: str) -> dict:
        repo = self.resolve_workspace_path(session_id, repo_dir)
        fetch = subprocess.run(["git", "fetch", "--all", "--tags"], cwd=repo, capture_output=True, text=True, check=False)
        co = subprocess.run(["git", "checkout", ref], cwd=repo, capture_output=True, text=True, check=False)
        return {"ok": fetch.returncode == 0 and co.returncode == 0, "fetch_stderr": fetch.stderr, "checkout_stderr": co.stderr}

    def detect_stack(self, session_id: str, repo_dir: str) -> dict:
        repo = self.resolve_workspace_path(session_id, repo_dir)
        return {
            "node": (repo / "package.json").exists(),
            "python": any((repo / f).exists() for f in ["requirements.txt", "pyproject.toml", "Pipfile"]),
            "docker": (repo / "Dockerfile").exists(),
        }

    def install_node_deps(self, session_id: str, repo_dir: str, frozen_lockfile: bool) -> dict:
        repo = self.resolve_workspace_path(session_id, repo_dir)
        cmd = ["npm", "ci"] if frozen_lockfile and (repo / "package-lock.json").exists() else ["npm", "install"]
        run = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
        return {"ok": run.returncode == 0, "stderr": run.stderr[-4000:], "stdout": run.stdout[-4000:]}

    def install_python_deps(self, session_id: str, repo_dir: str, requirements_file: str) -> dict:
        repo = self.resolve_workspace_path(session_id, repo_dir)
        req = repo / requirements_file
        run = subprocess.run(["python3", "-m", "pip", "install", "-r", str(req)], cwd=repo, capture_output=True, text=True, check=False)
        return {"ok": run.returncode == 0, "stderr": run.stderr[-4000:], "stdout": run.stdout[-4000:]}

    def write_env_file(self, session_id: str, repo_dir: str, env: dict[str, str]) -> dict:
        repo = self.resolve_workspace_path(session_id, repo_dir)
        env_path = repo / ".env"
        lines = [f"{k}={json.dumps(v)[1:-1]}" for k, v in sorted(env.items())]
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"path": str(env_path), "count": len(env)}

    def start_process(self, session_id: str, repo_dir: str, name: str, command: list[str], port: int | None) -> dict:
        repo = self.resolve_workspace_path(session_id, repo_dir)
        logs_dir = self.runtime_root / "output" / session_id
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"{name}.log"
        log_file = log_path.open("a", encoding="utf-8")
        proc = subprocess.Popen(command, cwd=repo, stdout=log_file, stderr=subprocess.STDOUT, text=True)
        self.processes[session_id][name] = proc
        self.logs[session_id][name] = log_path
        return {"pid": proc.pid, "name": name, "port": port, "log_path": str(log_path)}

    def stop_process(self, session_id: str, name: str) -> dict:
        proc = self.processes[session_id].get(name)
        if not proc:
            return {"stopped": False, "reason": "process not found"}
        proc.terminate()
        proc.wait(timeout=5)
        del self.processes[session_id][name]
        return {"stopped": True, "return_code": proc.returncode}

    def check_port(self, host: str, port: int) -> dict:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.5)
        code = sock.connect_ex((host, port))
        sock.close()
        return {"open": code == 0, "host": host, "port": port}

    def stream_logs(self, session_id: str, name: str, lines: int) -> dict:
        path = self.logs[session_id].get(name)
        if not path or not path.exists():
            return {"logs": "", "lines": 0}
        content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        tail = content[-lines:]
        return {"logs": "\n".join(tail), "lines": len(tail), "path": str(path)}

    # Safe coding tools
    def run_code(self, language: str, code: str, timeout: int) -> dict:
        with tempfile.TemporaryDirectory() as td:
            temp = Path(td)
            if language == "python":
                file = temp / "snippet.py"
                file.write_text(code, encoding="utf-8")
                cmd = ["python3", str(file)]
            else:
                file = temp / "snippet.js"
                file.write_text(code, encoding="utf-8")
                cmd = ["node", str(file)]
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
            return {"exit_code": done.returncode, "stdout": done.stdout, "stderr": done.stderr}

    def functions_mapping(self, code: str) -> list[dict]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        out = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                out.append({"name": node.name, "line": node.lineno, "args": [a.arg for a in node.args.args]})
        return out

    def bracket_tracker(self, code: str) -> dict:
        stack = []
        pairs = {")": "(", "]": "[", "}": "{"}
        opens = set(pairs.values())
        for idx, ch in enumerate(code, start=1):
            if ch in opens:
                stack.append((ch, idx))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    return {"balanced": False, "error_at": idx}
                stack.pop()
        return {"balanced": len(stack) == 0, "unclosed": stack}

    def search_in_files(self, root: Path, pattern: str) -> list[dict]:
        rgx = re.compile(pattern)
        hits = []
        for f in root.rglob("*"):
            if not f.is_file():
                continue
            text = f.read_text(encoding="utf-8", errors="ignore")
            for ln, line in enumerate(text.splitlines(), start=1):
                if rgx.search(line):
                    hits.append({"file": str(f), "line": ln, "content": line[:240]})
        return hits[:200]
