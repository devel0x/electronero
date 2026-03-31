from __future__ import annotations

import json
import platform
from pathlib import Path


class Bridge:
    """Bridge endpoints exposed to the frontend.

    Design choice: expose explicit methods instead of generic eval/dispatch.
    This keeps permission review and auditing straightforward.
    """

    def system_info(self) -> dict[str, str]:
        return {
            "os": platform.system(),
            "release": platform.release(),
            "python": platform.python_version(),
        }

    def save_settings(self, payload: dict) -> dict[str, str]:
        data_dir = Path(__file__).resolve().parents[1] / "data"
        data_dir.mkdir(exist_ok=True)
        path = data_dir / "settings.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"status": "saved", "path": str(path)}
