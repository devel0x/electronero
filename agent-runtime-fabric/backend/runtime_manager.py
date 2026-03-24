from __future__ import annotations

import ast
import re
import subprocess
import tempfile
import uuid
from pathlib import Path

from models import RuntimePolicy, SessionState
from policy import ensure_readable, ensure_writable


class RuntimeManager:
    def __init__(self, runtime_root: Path):
        self.runtime_root = runtime_root
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.sessions: dict[str, SessionState] = {}

    def create_session(self, policy: RuntimePolicy | None = None) -> SessionState:
        sid = str(uuid.uuid4())
        state = SessionState(session_id=sid, policy=policy or RuntimePolicy())
        self.sessions[sid] = state

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
            path = self.runtime_root / zone / session_id
            if path.exists():
                for child in path.iterdir():
                    if child.is_file():
                        child.unlink(missing_ok=True)
                    elif child.is_dir():
                        for nested in child.rglob("*"):
                            if nested.is_file():
                                nested.unlink(missing_ok=True)
                        for nested in sorted(child.rglob("*"), reverse=True):
                            if nested.is_dir():
                                nested.rmdir()
                        child.rmdir()
        state.status = "active"
        return state

    def destroy_session(self, session_id: str) -> None:
        state = self.get_session(session_id)
        state.status = "destroyed"

    def resolve_runtime_path(self, runtime_path: str, must_be_writable: bool = False) -> Path:
        if must_be_writable:
            ensure_writable(runtime_path)
        else:
            ensure_readable(runtime_path)
        return self.runtime_root / runtime_path.lstrip("/").replace("runtime/", "")

    def run_code(self, language: str, code: str, timeout: int) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            if language == "python":
                source = tmp / "snippet.py"
                source.write_text(code, encoding="utf-8")
                cmd = ["python3", str(source)]
            else:
                source = tmp / "snippet.js"
                source.write_text(code, encoding="utf-8")
                cmd = ["node", str(source)]

            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            return {
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }

    def functions_mapping(self, code: str) -> list[dict]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []
        mapped = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                mapped.append({"name": node.name, "line": node.lineno, "args": [a.arg for a in node.args.args]})
        return mapped

    def bracket_tracker(self, code: str) -> dict:
        stack = []
        pairs = {')': '(', ']': '[', '}': '{'}
        opens = set(pairs.values())
        for idx, char in enumerate(code, start=1):
            if char in opens:
                stack.append((char, idx))
            elif char in pairs:
                if not stack or stack[-1][0] != pairs[char]:
                    return {"balanced": False, "error_at": idx}
                stack.pop()
        return {"balanced": len(stack) == 0, "unclosed": stack}

    def search_in_files(self, root: Path, pattern: str) -> list[dict]:
        compiled = re.compile(pattern)
        hits = []
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            text = file_path.read_text(encoding="utf-8", errors="ignore")
            for ln, line in enumerate(text.splitlines(), start=1):
                if compiled.search(line):
                    hits.append({"file": str(file_path), "line": ln, "content": line[:240]})
        return hits[:200]
