from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python <3.11 support for local dev environments
    import tomli as tomllib


@dataclass(slots=True)
class AppConfig:
    name: str
    app_id: str
    version: str
    width: int
    height: int
    filesystem_roots: tuple[str, ...]
    clipboard: bool
    notifications: bool
    subprocess_enabled: bool
    plugins_enabled: bool


def _load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def load_config(root: Path) -> AppConfig:
    config_path = root / "platform.toml"
    raw = _load_toml(config_path)

    desktop = raw.get("desktop", {})
    permissions = raw.get("permissions", {})
    runtime = raw.get("runtime", {})

    return AppConfig(
        name=raw["app"]["name"],
        app_id=raw["app"]["id"],
        version=raw["app"]["version"],
        width=int(desktop.get("width", 1200)),
        height=int(desktop.get("height", 780)),
        filesystem_roots=tuple(permissions.get("filesystem", [])),
        clipboard=bool(permissions.get("clipboard", False)),
        notifications=bool(permissions.get("notifications", False)),
        subprocess_enabled=bool(permissions.get("subprocess", False)),
        plugins_enabled=bool(runtime.get("plugins_enabled", True)),
    )
