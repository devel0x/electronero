from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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


def load_config(root: Path) -> AppConfig:
    config_path = root / "platform.toml"
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig(
        name=raw["app"]["name"],
        app_id=raw["app"]["id"],
        version=raw["app"]["version"],
        width=raw["desktop"].get("width", 1200),
        height=raw["desktop"].get("height", 780),
    )
