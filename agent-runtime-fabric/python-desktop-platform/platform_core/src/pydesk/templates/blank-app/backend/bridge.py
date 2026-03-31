from __future__ import annotations

import platform
from datetime import datetime, timezone
from pathlib import Path

from pydesk.core.config import AppConfig
from pydesk.core.permissions import assert_path_allowed


class NativeBridge:
    """Bridge API exposed to frontend JavaScript via pywebview.

    V2-ready behavior:
    - pulls permissions from platform.toml
    - validates filesystem writes
    - keeps explicit method surface for auditability
    """

    def __init__(self, *, config: AppConfig, app_root: Path):
        self._config = config
        self._app_root = app_root

    def get_system_info(self) -> dict[str, str]:
        return {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "utc_now": datetime.now(timezone.utc).isoformat(),
        }

    def write_note(self, text: str) -> dict[str, str]:
        note_file = self._app_root / "data" / "note.txt"
        safe_path = assert_path_allowed(self._config, note_file, self._app_root)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(text, encoding="utf-8")
        return {"status": "ok", "path": str(safe_path)}
