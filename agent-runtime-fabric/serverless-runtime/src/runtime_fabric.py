#!/usr/bin/env python3
"""Server-less sandboxed agent runtime for Python and Node.js.

Production-oriented hardening goals:
- tool-mediated execution (no raw shell interface)
- scoped filesystem access per session
- policy-driven limits (cpu/memory/time/output)
- immutable-ish audit ledger events in output zone
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import resource
import shutil
import subprocess
import tarfile
import time
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
        self.allow_domains = set(rp["network"].get("allow_domains", []))

        resources = rp["resources"]
        self.ttl_seconds = int(resources.get("ttl_seconds", 1800))
        self.output_limit_mb = int(resources.get("output_limit_mb", 100))
        self.memory_limit_mb = int(resources.get("memory_limit_mb", 1024))
        self.cpu_quota = int(float(resources.get("cpu_quota", 2)))

        installer = rp["tools"].get("install_package", {})
        self.allowed_registries = set(installer.get("allowed_registries", []))
        self.require_version_pin = bool(installer.get("require_version_pin", False))

        # runtime safety caps for input payloads
        self.max_code_bytes = 512_000
        self.max_file_write_bytes = 2_000_000

    @classmethod
    def from_yaml(cls, path: Path) -> "RuntimePolicy":
        text = path.read_text(encoding="utf-8")
        policy = _minimal_yaml_parse(text)
        return cls(policy)

    def ensure_tool_allowed(self, tool_name: str) -> None:
        if tool_name not in self.allowed_tools:
            raise PolicyError(f"tool not allowed: {tool_name}")


class ToolRuntime:
    def __init__(self, policy: RuntimePolicy, paths: RuntimePaths | None = None):
        self.policy = policy
        self.paths = paths or RuntimePaths.default()
        self.paths.output_root.mkdir(parents=True, exist_ok=True)

    def _workspace(self, session_id: str) -> Path:
        _validate_session_id(session_id)
        ws = self.paths.workspaces_root / session_id
        ws.mkdir(parents=True, exist_ok=True)
        self.paths.tmp_root.mkdir(parents=True, exist_ok=True)
        self.paths.output_root.mkdir(parents=True, exist_ok=True)
        self.paths.cache_root.mkdir(parents=True, exist_ok=True)
        return ws

    def _assert_scoped_path(self, candidate: Path, session_id: str) -> Path:
        ws = self._workspace(session_id).resolve()
        target = candidate.resolve()
        if os.path.commonpath([str(target), str(ws)]) != str(ws):
            raise PolicyError(f"path outside session scope: {candidate}")
        return target

    def _audit(self, session_id: str, tool: str, args: Dict[str, Any], result: Dict[str, Any], status: str) -> None:
        ledger = self.paths.output_root / "audit-ledger.jsonl"
        row = {
            "ts": int(time.time()),
            "session_id": session_id,
            "tool": tool,
            "status": status,
            "args_hash": hashlib.sha256(json.dumps(args, sort_keys=True).encode("utf-8")).hexdigest(),
            "result_hash": hashlib.sha256(json.dumps(result, sort_keys=True).encode("utf-8", errors="ignore")).hexdigest(),
        }
        with ledger.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def list_directory(self, session_id: str, rel_path: str = ".") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("list_directory")
        ws = self._workspace(session_id)
        target = self._assert_scoped_path((ws / rel_path), session_id)
        entries = []
        for p in sorted(target.iterdir() if target.exists() else []):
            entries.append({"name": p.name, "type": "dir" if p.is_dir() else "file", "size": p.stat().st_size})
        return {"path": str(target), "entries": entries}

    def read_file(self, session_id: str, rel_path: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("read_file")
        ws = self._workspace(session_id)
        target = self._assert_scoped_path((ws / rel_path), session_id)
        return {"path": str(target), "content": target.read_text(encoding="utf-8")}

    def write_file(self, session_id: str, rel_path: str, content: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("write_file")
        payload_bytes = len(content.encode("utf-8"))
        if payload_bytes > self.policy.max_file_write_bytes:
            raise PolicyError(f"write exceeds max_file_write_bytes={self.policy.max_file_write_bytes}")

        ws = self._workspace(session_id)
        target = self._assert_scoped_path((ws / rel_path), session_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "bytes": payload_bytes}

    def search_in_files(self, session_id: str, pattern: str, rel_path: str = ".") -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("search_in_files")
        ws = self._workspace(session_id)
        target = self._assert_scoped_path((ws / rel_path), session_id)
        rx = re.compile(pattern)
        matches: List[Dict[str, Any]] = []
        for p in target.rglob("*"):
            if not p.is_file():
                continue
            try:
                for idx, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                    if rx.search(line):
                        matches.append({"file": str(p.relative_to(ws)), "line": idx, "text": line.strip()})
            except OSError:
                continue
        return {"matches": matches[:2000]}

    def functions_mapping(self, session_id: str, rel_path: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("functions_mapping")
        ws = self._workspace(session_id)
        target = self._assert_scoped_path((ws / rel_path), session_id)
        text = target.read_text(encoding="utf-8", errors="ignore")

        mapping: List[Dict[str, Any]] = []
        for idx, line in enumerate(text.splitlines(), start=1):
            py_match = re.match(r"\s*def\s+([a-zA-Z_][\w]*)\s*\(", line)
            js_match = re.match(r"\s*(?:function\s+([a-zA-Z_][\w]*)\s*\(|const\s+([a-zA-Z_][\w]*)\s*=\s*\(.*\)\s*=>)", line)
            if py_match:
                mapping.append({"name": py_match.group(1), "line": idx, "lang": "python"})
            elif js_match:
                mapping.append({"name": js_match.group(1) or js_match.group(2), "line": idx, "lang": "javascript"})
        return {"file": rel_path, "functions": mapping}

    def bracket_tracker(self, session_id: str, rel_path: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("bracket_tracker")
        ws = self._workspace(session_id)
        target = self._assert_scoped_path((ws / rel_path), session_id)
        text = target.read_text(encoding="utf-8", errors="ignore")

        stack: List[Tuple[str, int]] = []
        pairs = {")": "(", "}": "{", "]": "["}
        openers = set(pairs.values())
        issues: List[Dict[str, Any]] = []

        for idx, ch in enumerate(text, start=1):
            if ch in openers:
                stack.append((ch, idx))
            elif ch in pairs:
                if not stack or stack[-1][0] != pairs[ch]:
                    issues.append({"pos": idx, "issue": f"unexpected '{ch}'"})
                else:
                    stack.pop()

        for opener, pos in stack:
            issues.append({"pos": pos, "issue": f"unclosed '{opener}'"})

        return {"file": rel_path, "issues": issues, "balanced": not issues}

    def run_code(self, session_id: str, language: str, code: str, filename: str | None = None) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("run_code")
        code_bytes = len(code.encode("utf-8"))
        if code_bytes > self.policy.max_code_bytes:
            raise PolicyError(f"code exceeds max_code_bytes={self.policy.max_code_bytes}")

        ws = self._workspace(session_id)
        language = language.lower().strip()
        if language not in {"python", "node", "javascript", "js"}:
            raise PolicyError("language must be python or node")

        if language == "python":
            interpreter = shutil.which("python3") or "python3"
            file_name = filename or "main.py"
        else:
            interpreter = shutil.which("node") or "node"
            file_name = filename or "main.js"

        if file_name.startswith("/"):
            raise ValidationError("filename must be relative")

        script = self._assert_scoped_path(ws / file_name, session_id)
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(code, encoding="utf-8")

        start = time.time()
        proc = subprocess.run(
            [interpreter, str(script)],
            cwd=str(ws),
            text=True,
            capture_output=True,
            timeout=self.policy.ttl_seconds,
            env=self._safe_env(),
            preexec_fn=self._resource_limiter(),
        )
        duration_ms = int((time.time() - start) * 1000)

        out_cap = self.policy.output_limit_mb * 1024 * 1024
        return {
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "stdout": proc.stdout[-out_cap:],
            "stderr": proc.stderr[-out_cap:],
            "script": str(script),
        }

    def install_package(self, session_id: str, ecosystem: str, spec: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("install_package")
        ws = self._workspace(session_id)

        ecosystem = ecosystem.lower().strip()
        _validate_package_spec(spec, require_pin=self.policy.require_version_pin)

        if ecosystem == "python":
            if "pypi.org" not in self.policy.allowed_registries:
                raise PolicyError("pypi.org not allowed by policy")
            cmd = [
                shutil.which("python3") or "python3",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--target",
                str(ws / ".venv_lib"),
                spec,
            ]
        elif ecosystem in {"node", "npm", "javascript"}:
            if "registry.npmjs.org" not in self.policy.allowed_registries:
                raise PolicyError("registry.npmjs.org not allowed by policy")
            cmd = [shutil.which("npm") or "npm", "install", "--prefix", str(ws), spec, "--ignore-scripts", "--no-audit"]
        else:
            raise PolicyError("ecosystem must be python or npm")

        start = time.time()
        proc = subprocess.run(
            cmd,
            cwd=str(ws),
            text=True,
            capture_output=True,
            timeout=min(self.policy.ttl_seconds, 300),
            env=self._safe_env(),
            preexec_fn=self._resource_limiter(),
        )
        duration_ms = int((time.time() - start) * 1000)
        return {
            "exit_code": proc.returncode,
            "duration_ms": duration_ms,
            "stdout": proc.stdout[-32768:],
            "stderr": proc.stderr[-32768:],
            "cmd": cmd,
        }

    def export_artifact(self, session_id: str, rel_path: str, artifact_name: str) -> Dict[str, Any]:
        self.policy.ensure_tool_allowed("export_artifact")
        ws = self._workspace(session_id)
        source = self._assert_scoped_path(ws / rel_path, session_id)

        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "-", artifact_name)[:80]
        destination = self.paths.output_root / f"{session_id}-{safe_name}.tar.gz"
        with tarfile.open(destination, "w:gz") as tar:
            tar.add(source, arcname=source.name)
        return {"artifact": str(destination), "bytes": destination.stat().st_size}

    def reset_session(self, session_id: str) -> Dict[str, Any]:
        ws = self._workspace(session_id)
        if ws.exists():
            shutil.rmtree(ws)
        ws.mkdir(parents=True, exist_ok=True)
        return {"session_id": session_id, "status": "reset"}

    def _resource_limiter(self):
        cpu = max(1, self.policy.cpu_quota)
        mem_bytes = self.policy.memory_limit_mb * 1024 * 1024

        def _apply_limits():
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        return _apply_limits

    @staticmethod
    def _safe_env() -> Dict[str, str]:
        allow = {"PATH", "HOME", "LANG", "LC_ALL", "PYTHONIOENCODING"}
        env = {k: v for k, v in os.environ.items() if k in allow}
        env["PYTHONUNBUFFERED"] = "1"
        return env


def _validate_session_id(session_id: str) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", session_id):
        raise ValidationError("invalid session_id format")


def _validate_package_spec(spec: str, require_pin: bool) -> None:
    if not re.fullmatch(r"[a-zA-Z0-9_.\-/@]+(?:==[a-zA-Z0-9_.\-]+)?", spec):
        raise ValidationError("invalid package spec")
    if require_pin and "==" not in spec:
        raise PolicyError("package version pin required by policy")


def _minimal_yaml_parse(text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except Exception:
        pass
    return _tiny_yaml(text)


def _tiny_yaml(text: str) -> Dict[str, Any]:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    root: Dict[str, Any] = {}
    stack: List[Tuple[int, Any]] = [(-1, root)]

    for idx_line, line in enumerate(lines):
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            value = _yaml_scalar(stripped[2:])
            if not isinstance(parent, list):
                raise ValueError("invalid yaml list structure")
            parent.append(value)
            continue

        if ":" not in stripped:
            raise ValueError(f"invalid yaml line: {line}")

        key, raw_val = stripped.split(":", 1)
        key = key.strip()
        raw_val = raw_val.strip()

        if raw_val == "":
            next_container: Any = [] if _next_is_list(lines, idx_line, indent) else {}
            if isinstance(parent, dict):
                parent[key] = next_container
            else:
                raise ValueError("invalid yaml nesting")
            stack.append((indent, next_container))
        else:
            if isinstance(parent, dict):
                parent[key] = _yaml_scalar(raw_val)
            else:
                raise ValueError("invalid yaml map placement")

    return root


def _next_is_list(lines: List[str], start_idx: int, cur_indent: int) -> bool:
    for next_line in lines[start_idx + 1 :]:
        n_indent = len(next_line) - len(next_line.lstrip(" "))
        if n_indent <= cur_indent:
            return False
        return next_line.strip().startswith("- ")
    return False


def _yaml_scalar(value: str) -> Any:
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def dispatch(runtime: ToolRuntime, request: Dict[str, Any]) -> Dict[str, Any]:
    if "tool" not in request or "session_id" not in request:
        raise ValidationError("request must include tool and session_id")

    tool = request["tool"]
    session_id = request["session_id"]
    args = request.get("args", {})

    handler = getattr(runtime, tool, None)
    if handler is None or not callable(handler):
        raise PolicyError(f"unknown tool: {tool}")

    try:
        result = handler(session_id=session_id, **args)
        runtime._audit(session_id=session_id, tool=tool, args=args, result=result, status="ok")
        return result
    except Exception as exc:
        err = {"error": type(exc).__name__, "message": str(exc)}
        runtime._audit(session_id=session_id, tool=tool, args=args, result=err, status="error")
        raise


def main() -> None:
    policy_path = Path(__file__).resolve().parents[2] / "mvp-policy.yaml"
    policy = RuntimePolicy.from_yaml(policy_path)
    runtime = ToolRuntime(policy)

    payload = json.loads(input())
    result = dispatch(runtime, payload)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
