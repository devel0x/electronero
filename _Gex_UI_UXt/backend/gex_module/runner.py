from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import httpx

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build", ".next", ".cache", "_gex"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", ".DS_Store"}
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java", ".css", ".html", ".sql", ".sh", ".toml", ".yaml", ".yml", ".md"}


@dataclass
class GexConfig:
    api_base: str = os.getenv("AIAS_API_URL", "https://api.aiassist.net")
    api_key: str = os.getenv("AIAS_API_KEY", "")
    model: str = os.getenv("AIAS_MODEL", "moonshotai/kimi-k2-instruct")
    provider: str = os.getenv("AIAS_PROVIDER", "groq")
    max_context_chars: int = 100_000


class GexRunner:
    def __init__(self, config: Optional[GexConfig] = None):
        self.config = config or GexConfig()

    def run_on_file(self, path: str, *, stop_event: Optional[threading.Event] = None, log: Optional[Callable[[dict], None]] = None) -> dict:
        file_path = Path(path).resolve()
        repo_root = file_path.parent
        result = self._run(repo_root=repo_root, files=[file_path], stop_event=stop_event, log=log)
        return result

    def run_file(self, path: str, **kwargs) -> dict:
        return self.run_on_file(path, **kwargs)

    def run_on_repo(self, path: str, mode: str = "sequential", *, stop_event: Optional[threading.Event] = None, log: Optional[Callable[[dict], None]] = None) -> dict:
        if mode != "sequential":
            raise ValueError("Only sequential mode is currently supported")
        repo_root = Path(path).resolve()
        files = self._scan_code_files(repo_root)
        return self._run(repo_root=repo_root, files=files, stop_event=stop_event, log=log)

    def run_repo(self, path: str, mode: str = "sequential", **kwargs) -> dict:
        return self.run_on_repo(path, mode=mode, **kwargs)

    def _scan_code_files(self, repo_root: Path) -> list[Path]:
        out: list[Path] = []
        for path in sorted(repo_root.rglob("*")):
            if not path.is_file():
                continue
            if any(skip in path.parts for skip in SKIP_DIRS):
                continue
            if path.name in SKIP_FILES or path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            out.append(path)
        return out

    def _run(self, repo_root: Path, files: list[Path], *, stop_event: Optional[threading.Event], log: Optional[Callable[[dict], None]]) -> dict:
        if not self.config.api_key:
            raise RuntimeError("AIAS_API_KEY is not configured")

        run_diffs: list[dict] = []
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        if self.config.provider:
            headers["X-AiAssist-Provider"] = self.config.provider

        with httpx.Client(timeout=120) as client:
            total = len(files)
            for index, file_path in enumerate(files, start=1):
                if stop_event and stop_event.is_set():
                    break

                before = file_path.read_text(errors="replace")
                rel_path = file_path.relative_to(repo_root).as_posix()
                if log:
                    log({"type": "progress", "current": index, "total": total, "file": rel_path})

                user_prompt = self._build_file_prompt(rel_path, before)
                llm_output = self._send_to_llm(client, headers, user_prompt)
                blocks = self._parse_surgical_blocks(llm_output)
                file_blocks = [b for b in blocks if b["path"] == rel_path]
                status = "unchanged"

                if file_blocks:
                    content = before
                    for block in file_blocks:
                        if block["action"] == "write":
                            content = block["content"]
                        elif block["action"] == "patch":
                            content, _, _ = self._apply_patch_operations(content, block["operations"])
                    if content != before:
                        file_path.write_text(content)
                        status = "modified"
                after = file_path.read_text(errors="replace")
                run_diffs.append({"file": rel_path, "before": before, "after": after, "status": status})
                if log:
                    log({"type": "log", "message": f"{rel_path}: {status}"})

        return {"files": run_diffs, "processed": len(run_diffs)}

    def _send_to_llm(self, client: httpx.Client, headers: dict, user_prompt: str) -> str:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": GEX_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        response = client.post(f"{self.config.api_base}/v1/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _build_file_prompt(self, path: str, content: str) -> str:
        numbered = "\n".join(f"{i + 1:>4}| {line}" for i, line in enumerate(content.splitlines()))
        return f"Analyze and surgically improve this file. Return edits only via <<<WRITE>>> or <<<PATCH>>> for {path}.\n\n```\n{numbered}\n```"

    def _parse_surgical_blocks(self, llm_output: str) -> list[dict]:
        blocks = []
        pattern = re.compile(r"<<<(WRITE|PATCH):(.+?)>>>\\s*\\n(.*?)<<<END>>>", re.DOTALL)
        for match in pattern.finditer(llm_output):
            action, path, body = match.group(1), match.group(2).strip(), match.group(3).strip()
            if action == "WRITE":
                blocks.append({"action": "write", "path": path, "content": body})
            else:
                raw = body
                if raw.startswith("```"):
                    raw = re.sub(r"^```\\w*\\n?", "", raw)
                    raw = re.sub(r"\\n?```$", "", raw)
                operations = json.loads(raw)
                if isinstance(operations, dict):
                    operations = operations.get("operations", [operations])
                blocks.append({"action": "patch", "path": path, "operations": operations})
        return blocks

    def _apply_patch_operations(self, content: str, operations: list[dict]) -> tuple[str, int, int]:
        lines = content.split("\n")
        added = removed = 0
        for op in sorted(operations, key=lambda value: value.get("start_line", 0), reverse=True):
            action = op.get("action")
            start = max(op.get("start_line", 1) - 1, 0)
            end = op.get("end_line", op.get("start_line", 1))
            if action == "insert":
                new_lines = op.get("content", "").split("\n")
                lines = lines[:start] + new_lines + lines[start:]
                added += len(new_lines)
            elif action == "replace":
                new_lines = op.get("content", "").split("\n")
                lines = lines[:start] + new_lines + lines[end:]
                added += len(new_lines)
                removed += max(end - start, 0)
            elif action == "delete":
                lines = lines[:start] + lines[end:]
                removed += max(end - start, 0)
        return "\n".join(lines), added, removed


GEX_SYSTEM_PROMPT = """You are Gex, an expert code surgeon.\nUse only <<<WRITE:path>>>...<<<END>>> and <<<PATCH:path>>> JSON ops ...<<<END>>> blocks for changes.\nUse exact paths and line numbers."""
