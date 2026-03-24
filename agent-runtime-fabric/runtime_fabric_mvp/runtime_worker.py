from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from policy import PolicyError, RuntimePolicy, require_registry_allowed, require_tool_allowed
from schemas import InstallPackageRequest, Language, RunCodeRequest, ToolResult


class RuntimeWorker:
    def __init__(self, root: Path, policy: RuntimePolicy):
        self.root = root
        self.policy = policy
        self.workspaces = self.root / "workspaces"
        self.tmp = self.root / "tmp"
        self.output = self.root / "output"
        self.cache = self.root / "cache"

        for path in (self.workspaces, self.tmp, self.output, self.cache):
            path.mkdir(parents=True, exist_ok=True)

    def workspace_for_session(self, session_id: str) -> Path:
        workspace = self.workspaces / session_id
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def run_code(self, request: RunCodeRequest) -> ToolResult:
        require_tool_allowed(self.policy, "run_code")

        workspace = self.workspace_for_session(request.session_id)
        start = time.monotonic()

        if request.language == Language.python:
            script_path = workspace / "main.py"
            script_path.write_text(request.code)
            cmd = ["python3", str(script_path)]
        else:
            script_path = workspace / "main.mjs"
            script_path.write_text(request.code)
            cmd = ["node", str(script_path)]

        proc = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=request.timeout_seconds,
            check=False,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        return ToolResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_ms=duration_ms,
        )

    def install_package(self, request: InstallPackageRequest) -> ToolResult:
        require_tool_allowed(self.policy, "install_package")
        require_registry_allowed(self.policy, request.registry)
        workspace = self.workspace_for_session(request.session_id)

        start = time.monotonic()
        if request.language == Language.python:
            package_spec = request.package if request.version is None else f"{request.package}=={request.version}"
            cmd = [
                "python3",
                "-m",
                "pip",
                "install",
                package_spec,
                "--index-url",
                f"https://{request.registry}/simple",
                "--target",
                str(workspace / ".pydeps"),
            ]
        else:
            package_spec = request.package if request.version is None else f"{request.package}@{request.version}"
            cmd = [
                "npm",
                "install",
                package_spec,
                "--registry",
                f"https://{request.registry}",
                "--prefix",
                str(workspace / ".nodedeps"),
                "--ignore-scripts",
            ]

        proc = subprocess.run(
            cmd,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=min(self.policy.ttl_seconds, 180),
            check=False,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        return ToolResult(
            ok=proc.returncode == 0,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_ms=duration_ms,
        )

    def export_artifact(self, session_id: str, relative_path: str) -> Path:
        require_tool_allowed(self.policy, "export_artifact")

        workspace = self.workspace_for_session(session_id)
        source = workspace / relative_path
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Artifact '{relative_path}' not found in session '{session_id}'.")

        destination = self.output / f"{session_id}-{source.name}"
        shutil.copy2(source, destination)
        return destination

    def reset_session(self, session_id: str) -> None:
        workspace = self.workspaces / session_id
        if workspace.exists():
            shutil.rmtree(workspace)

    def destroy_runtime(self) -> None:
        for path in (self.workspaces, self.tmp, self.cache):
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
