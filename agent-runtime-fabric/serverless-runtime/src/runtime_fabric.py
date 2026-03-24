#!/usr/bin/env python3
"""ServerBuddy runtime with full tool surface (devops + coding tools)."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tarfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class RuntimePaths:
    readonly_base: Path
    workspaces_root: Path
    tmp_root: Path
    output_root: Path
    cache_root: Path

    @classmethod
    def default(cls) -> "RuntimePaths":
        root = Path("/runtime")
        return cls(
            readonly_base=root / "readonly-base",
            workspaces_root=root / "workspaces",
            tmp_root=root / "tmp",
            output_root=root / "output",
            cache_root=root / "cache",
        )


class PolicyError(Exception):
    pass


class ValidationError(Exception):
    pass


class RuntimePolicy:
    def __init__(self, policy: Dict[str, Any]):
        self.policy = policy
        rp = policy["runtime_profile"]
        self.allowed_tools = set(rp["tools"]["allowed"])
        self.ttl_seconds = int(rp["resources"].get("ttl_seconds", 1800))
        self.output_limit_mb = int(rp["resources"].get("output_limit_mb", 100))
        self.allow_domains = set(rp["network"].get("allow_domains", []))
        installer = rp["tools"].get("install_package", {})
        self.allowed_registries = set(installer.get("allowed_registries", []))

    @classmethod
    def from_yaml(cls, path: Path) -> "RuntimePolicy":
        text = path.read_text(encoding="utf-8")
        try:
            import yaml  # type: ignore
            return cls(yaml.safe_load(text))
        except Exception:
            return cls(_tiny_yaml(text))

    def ensure_tool_allowed(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise PolicyError(f"tool not allowed: {tool_name}")


class ToolRuntime:
    def __init__(self, policy: RuntimePolicy, paths: RuntimePaths | None = None):
        self.policy = policy
        self.paths = paths or RuntimePaths.default()
        self.paths.output_root.mkdir(parents=True, exist_ok=True)

    # ---------- shared helpers ----------
    def _workspace(self, session_id: str) -> Path:
        _validate_session_id(session_id)
        ws = self.paths.workspaces_root / session_id
        ws.mkdir(parents=True, exist_ok=True)
        (ws / "logs").mkdir(parents=True, exist_ok=True)
        return ws

    def _assert_in_workspace(self, session_id: str, p: Path) -> Path:
        ws = self._workspace(session_id).resolve()
        resolved = p.resolve()
        if os.path.commonpath([str(ws), str(resolved)]) != str(ws):
            raise PolicyError("path escapes workspace")
        return resolved

    def _repo_path(self, session_id: str, repo_dir: str) -> Path:
        if repo_dir.startswith("/"):
            raise ValidationError("repo_dir must be relative")
        return self._assert_in_workspace(session_id, self._workspace(session_id) / repo_dir)

    def _run(self, cmd: List[str], cwd: Path, timeout: int | None = None) -> Dict[str, Any]:
        start = time.time()
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout or self.policy.ttl_seconds,
            env=self._safe_env(),
        )
        cap = self.policy.output_limit_mb * 1024 * 1024
        return {
            "cmd": cmd,
            "exit_code": proc.returncode,
            "duration_ms": int((time.time() - start) * 1000),
            "stdout": proc.stdout[-cap:],
            "stderr": proc.stderr[-cap:],
        }

    def _audit(self, session_id: str, tool: str, args: Dict[str, Any], result: Dict[str, Any], status: str) -> None:
        row = {
            "ts": int(time.time()),
            "session_id": session_id,
            "tool": tool,
            "status": status,
            "args_hash": hashlib.sha256(json.dumps(args, sort_keys=True).encode()).hexdigest(),
            "result_hash": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
        }
        with (self.paths.output_root / "audit-ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    @staticmethod
    def _safe_env() -> Dict[str, str]:
        allow = {"PATH", "HOME", "LANG", "LC_ALL", "PYTHONIOENCODING"}
        return {k: v for k, v in os.environ.items() if k in allow}

    # ---------- original coding/runtime tools ----------
    def list_directory(self, session_id: str, rel_path: str = ".") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("list_directory")
        target = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        entries = []
        for p in sorted(target.iterdir() if target.exists() else []):
            entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size})
        return {"path": str(target), "entries": entries}

    def read_file(self, session_id: str, rel_path: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("read_file")
        p = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        return {"path": str(p), "content": p.read_text(encoding="utf-8")}

    def write_file(self, session_id: str, rel_path: str, content: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("write_file")
        p = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"path": str(p), "bytes": len(content.encode("utf-8"))}

    def search_in_files(self, session_id: str, pattern: str, rel_path: str = ".") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("search_in_files")
        root = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        rx = re.compile(pattern)
        matches = []
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                if rx.search(line):
                    matches.append({"file": str(p.relative_to(self._workspace(session_id))), "line": i, "text": line.strip()})
        return {"matches": matches[:2000]}

    def functions_mapping(self, session_id: str, rel_path: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("functions_mapping")
        p = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        text = p.read_text(encoding="utf-8", errors="ignore")
        out = []
        for idx, line in enumerate(text.splitlines(), start=1):
            pm = re.match(r"\s*def\s+([a-zA-Z_][\w]*)\s*\(", line)
            jm = re.match(r"\s*(?:function\s+([a-zA-Z_][\w]*)\s*\(|const\s+([a-zA-Z_][\w]*)\s*=\s*\(.*\)\s*=>)", line)
            if pm:
                out.append({"name": pm.group(1), "line": idx, "lang": "python"})
            elif jm:
                out.append({"name": jm.group(1) or jm.group(2), "line": idx, "lang": "javascript"})
        return {"file": rel_path, "functions": out}

    def bracket_tracker(self, session_id: str, rel_path: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("bracket_tracker")
        p = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        text = p.read_text(encoding="utf-8", errors="ignore")
        stack: List[Tuple[str, int]] = []
        pairs = {")": "(", "}": "{", "]": "["}
        issues = []
        for idx, ch in enumerate(text, start=1):
            if ch in "({[":
                stack.append((ch, idx))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    issues.append({"pos": idx, "issue": f"unexpected '{ch}'"})
                else:
                    stack.pop()
        for op, pos in stack:
            issues.append({"pos": pos, "issue": f"unclosed '{op}'"})
        return {"file": rel_path, "issues": issues, "balanced": not issues}

    def run_code(self, session_id: str, language: str, code: str, filename: str | None = None) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("run_code")
        ws = self._workspace(session_id)
        language = language.lower()
        if language == "python":
            exe, fname = "python3", (filename or "main.py")
        elif language in {"node", "javascript", "js"}:
            exe, fname = "node", (filename or "main.js")
        else:
            raise ValidationError("language must be python or node")
        script = self._assert_in_workspace(session_id, ws / fname)
        script.write_text(code, encoding="utf-8")
        return self._run([exe, str(script)], cwd=ws)

    def install_package(self, session_id: str, ecosystem: str, spec: str, repo_dir: str = "repo") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("install_package")
        repo = self._repo_path(session_id, repo_dir)
        ecosystem = ecosystem.lower()
        if ecosystem == "python":
            if "pypi.org" not in self.policy.allowed_registries:
                raise PolicyError("pypi.org not allowed")
            cmd = ["python3", "-m", "pip", "install", "--disable-pip-version-check", spec]
        elif ecosystem in {"node", "npm", "javascript"}:
            if "registry.npmjs.org" not in self.policy.allowed_registries:
                raise PolicyError("registry.npmjs.org not allowed")
            cmd = ["npm", "install", spec, "--ignore-scripts", "--no-audit"]
        else:
            raise ValidationError("ecosystem must be python or node")
        return self._run(cmd, cwd=repo)

    def export_artifact(self, session_id: str, rel_path: str, artifact_name: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("export_artifact")
        source = self._assert_in_workspace(session_id, self._workspace(session_id) / rel_path)
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", artifact_name)[:80]
        out = self.paths.output_root / f"{session_id}-{safe}.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(source, arcname=source.name)
        return {"artifact": str(out), "bytes": out.stat().st_size}

    def reset_session(self, session_id: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("reset_session")
        ws = self._workspace(session_id)
        shutil.rmtree(ws, ignore_errors=True)
        ws.mkdir(parents=True, exist_ok=True)
        return {"session_id": session_id, "status": "reset"}

    # ---------- devops/runtime tools ----------
    def clone_repo(self, session_id: str, repo_url: str, repo_dir: str = "repo") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("clone_repo")
        if not repo_url.startswith(("https://", "git@")):
            raise ValidationError("repo_url must be https:// or git@")
        target = self._repo_path(session_id, repo_dir)
        return self._run(["git", "clone", repo_url, str(target)], cwd=self._workspace(session_id))

    def checkout_ref(self, session_id: str, repo_dir: str, ref: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("checkout_ref")
        return self._run(["git", "checkout", ref], cwd=self._repo_path(session_id, repo_dir))

    def detect_stack(self, session_id: str, repo_dir: str = "repo") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("detect_stack")
        repo = self._repo_path(session_id, repo_dir)
        return {
            "repo": str(repo),
            "stack": {
                "node": (repo / "package.json").exists(),
                "python": (repo / "requirements.txt").exists() or (repo / "pyproject.toml").exists(),
                "docker": (repo / "Dockerfile").exists(),
            },
        }

    def install_node_deps(self, session_id: str, repo_dir: str = "repo") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("install_node_deps")
        repo = self._repo_path(session_id, repo_dir)
        cmd = ["npm", "ci"] if (repo / "package-lock.json").exists() else ["npm", "install"]
        cmd += ["--ignore-scripts", "--no-audit"]
        return self._run(cmd, cwd=repo)

    def install_python_deps(self, session_id: str, repo_dir: str = "repo") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("install_python_deps")
        repo = self._repo_path(session_id, repo_dir)
        if (repo / "requirements.txt").exists():
            return self._run(["python3", "-m", "pip", "install", "--disable-pip-version-check", "-r", "requirements.txt"], cwd=repo)
        if (repo / "pyproject.toml").exists():
            return self._run(["python3", "-m", "pip", "install", "."], cwd=repo)
        raise ValidationError("no requirements.txt or pyproject.toml found")

    def write_env_file(self, session_id: str, repo_dir: str, items: Dict[str, str], filename: str = ".env") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("write_env_file")
        repo = self._repo_path(session_id, repo_dir)
        out = self._assert_in_workspace(session_id, repo / filename)
        lines = []
        for k, v in items.items():
            if not re.fullmatch(r"[A-Z0-9_]+", k):
                raise ValidationError(f"invalid env key: {k}")
            lines.append(f"{k}={str(v).replace(chr(10), '')}")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"path": str(out), "keys": sorted(items.keys())}

    def start_process(self, session_id: str, repo_dir: str, command: List[str], name: str = "app") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("start_process")
        repo = self._repo_path(session_id, repo_dir)
        logs = self._workspace(session_id) / "logs"
        out_path = logs / f"{name}.out.log"
        err_path = logs / f"{name}.err.log"
        with out_path.open("a", encoding="utf-8") as out, err_path.open("a", encoding="utf-8") as err:
            proc = subprocess.Popen(command, cwd=str(repo), stdout=out, stderr=err, env=self._safe_env())
        meta = self._workspace(session_id) / f".{name}.pid.json"
        meta.write_text(json.dumps({"pid": proc.pid, "command": command, "name": name}), encoding="utf-8")
        return {"pid": proc.pid, "name": name, "stdout": str(out_path), "stderr": str(err_path)}

    def stop_process(self, session_id: str, name: str = "app") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("stop_process")
        meta = self._workspace(session_id) / f".{name}.pid.json"
        if not meta.exists():
            raise ValidationError("process metadata not found")
        pid = int(json.loads(meta.read_text(encoding="utf-8"))["pid"])
        try:
            os.kill(pid, 15)
            status = "terminated"
        except ProcessLookupError:
            status = "not_running"
        return {"name": name, "pid": pid, "status": status}

    def check_port(self, session_id: str, host: str = "127.0.0.1", port: int = 3000, timeout_sec: float = 1.0) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("check_port")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout_sec)
            ok = s.connect_ex((host, int(port))) == 0
        return {"host": host, "port": int(port), "open": ok}

    def http_health_check(self, session_id: str, url: str, timeout_sec: float = 2.0) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("http_health_check")
        if not url.startswith(("http://", "https://")):
            raise ValidationError("url must be http(s)")
        try:
            with urllib.request.urlopen(url, timeout=timeout_sec) as res:
                body = res.read(1024).decode("utf-8", errors="ignore")
                return {"url": url, "ok": 200 <= res.status < 400, "status": res.status, "body_preview": body}
        except urllib.error.URLError as exc:
            return {"url": url, "ok": False, "error": str(exc)}

    def stream_logs(self, session_id: str, name: str = "app", lines: int = 200) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("stream_logs")
        logs = self._workspace(session_id) / "logs"
        out = logs / f"{name}.out.log"
        err = logs / f"{name}.err.log"
        return {"stdout": _tail(out, lines), "stderr": _tail(err, lines), "stdout_path": str(out), "stderr_path": str(err)}

    def capture_preview_metadata(self, session_id: str, port: int = 3000, path: str = "/") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("capture_preview_metadata")
        url = f"http://127.0.0.1:{int(port)}{path}"
        health = self.http_health_check(session_id=session_id, url=url)
        return {"preview_url": url, "reachable": health.get("ok", False), "status": health.get("status"), "timestamp": int(time.time())}

    def export_artifacts(self, session_id: str, repo_dir: str = "repo", artifact_name: str = "runtime-artifacts") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("export_artifacts")
        source = self._repo_path(session_id, repo_dir)
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "-", artifact_name)[:80]
        out = self.paths.output_root / f"{session_id}-{safe}.tar.gz"
        with tarfile.open(out, "w:gz") as tar:
            tar.add(source, arcname=source.name)
        return {"artifact": str(out), "bytes": out.stat().st_size}


def _tail(path: Path, lines: int) -> str:
    if not path.exists():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore").splitlines()[-max(1, lines) :])


def _validate_session_id(session_id: str) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", session_id):
        raise ValidationError("invalid session_id")


def _tiny_yaml(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(-1, root)]
    for i, line in enumerate(lines):
        ind = len(line) - len(line.lstrip(" "))
        s = line.strip()
        while stack and ind <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if s.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError("invalid list")
            parent.append(_scalar(s[2:]))
            continue
        k, v = s.split(":", 1)
        k, v = k.strip(), v.strip()
        if not v:
            nxt = [] if _next_is_list(lines, i, ind) else {}
            parent[k] = nxt
            stack.append((ind, nxt))
        else:
            parent[k] = _scalar(v)
    return root


def _next_is_list(lines: List[str], i: int, ind: int) -> bool:
    for n in lines[i + 1 :]:
        ni = len(n) - len(n.lstrip(" "))
        if ni <= ind:
            return False
        return n.strip().startswith("- ")
    return False


def _scalar(v: str) -> Any:
    if v in {"true", "True"}:
        return True
    if v in {"false", "False"}:
        return False
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


def dispatch(runtime: ToolRuntime, request: Dict[str, Any]) -> Dict[str, Any]:
    tool = request.get("tool")
    session_id = request.get("session_id")
    args = request.get("args", {})
    if not tool or not session_id:
        raise ValidationError("tool and session_id required")
    handler = getattr(runtime, tool, None)
    if handler is None or not callable(handler):
        raise PolicyError(f"unknown tool: {tool}")
    try:
        result = handler(session_id=session_id, **args)
        runtime._audit(session_id, tool, args, result, "ok")
        return result
    except Exception as exc:
        err = {"error": type(exc).__name__, "message": str(exc)}
        runtime._audit(session_id, tool, args, err, "error")
        raise


def main() -> None:
    runtime = ToolRuntime(RuntimePolicy.from_yaml(Path(__file__).resolve().parents[2] / "mvp-policy.yaml"))
    print(json.dumps(dispatch(runtime, json.loads(input()))))


if __name__ == "__main__":
    main()
