import json
from pathlib import Path
from typing import Iterable

from models import ToolLog


class PersistenceStore:
    def __init__(self, base: Path):
        self.base = base
        self.base.mkdir(parents=True, exist_ok=True)
        self.logs_file = self.base / "tool_ledger.jsonl"

    def append_tool_log(self, log: ToolLog) -> None:
        with self.logs_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log.model_dump(mode="json")) + "\n")

    def read_logs(self, limit: int = 200) -> list[dict]:
        if not self.logs_file.exists():
            return []
        lines = self.logs_file.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:]]

    def write_manifest(self, session_id: str, ecosystem: str, packages: Iterable[str]) -> Path:
        manifest = self.base / f"{session_id}.{ecosystem}.manifest.json"
        manifest.write_text(json.dumps({"packages": list(packages)}, indent=2), encoding="utf-8")
        return manifest
