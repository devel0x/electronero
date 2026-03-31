from __future__ import annotations

import json
import platform
from pathlib import Path

from pydesk.core.config import AppConfig
from pydesk.core.permissions import assert_path_allowed


class Bridge:
    """Bridge endpoints exposed to the frontend."""

    def __init__(self, *, config: AppConfig, app_root: Path):
        self._config = config
        self._app_root = app_root

    def system_info(self) -> dict[str, str]:
        return {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        }

    def save_settings(self, payload: dict) -> dict[str, str]:
        requested = self._app_root / "data" / "settings.json"
        safe_path = assert_path_allowed(self._config, requested, self._app_root)
        safe_path.parent.mkdir(exist_ok=True)
        safe_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"status": "saved", "path": str(safe_path)}
