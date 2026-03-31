from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path


class NativeBridge:
    """Methods on this class are exposed to frontend JavaScript via pywebview.

    Keep these methods small and permission-checked. In V1 we expose a single
    safe read/write demo endpoint and system info endpoint.
    """

    def get_system_info(self) -> dict[str, str]:
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "utc_now": datetime.now(timezone.utc).isoformat(),
        }

    def write_note(self, text: str) -> dict[str, str]:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        note_file = data_dir / "note.txt"
        note_file.write_text(text, encoding="utf-8")
        return {"status": "ok", "path": str(note_file)}
