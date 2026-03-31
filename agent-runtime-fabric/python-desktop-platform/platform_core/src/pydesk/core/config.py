from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python <3.11 support for local dev environments
    import tomli as tomllib


class ConfigError(ValueError):
    """Raised when platform.toml is malformed or missing required fields."""


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
    plugin_allowlist: tuple[str, ...]
    strict_plugins: bool


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Missing config file: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _require_str(section: dict[str, Any], key: str, *, section_name: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"'{section_name}.{key}' must be a non-empty string")
    return value


def load_config(root: Path) -> AppConfig:
    config_path = root / "platform.toml"
    raw = _load_toml(config_path)

    app = raw.get("app")
    if not isinstance(app, dict):
        raise ConfigError("Missing [app] section")

    desktop = raw.get("desktop", {})
    permissions = raw.get("permissions", {})
    runtime = raw.get("runtime", {})

    width = int(desktop.get("width", 1200))
    height = int(desktop.get("height", 780))
    if width < 400 or height < 300:
        raise ConfigError("desktop.width/height must be at least 400x300")

    filesystem_roots = tuple(permissions.get("filesystem", []))
    if not all(isinstance(path, str) and path for path in filesystem_roots):
        raise ConfigError("permissions.filesystem must be a list of non-empty strings")

    plugin_allowlist = tuple(runtime.get("plugin_allowlist", []))
    if not all(isinstance(name, str) and name for name in plugin_allowlist):
        raise ConfigError("runtime.plugin_allowlist must be a list of non-empty strings")

    return AppConfig(
        name=_require_str(app, "name", section_name="app"),
        app_id=_require_str(app, "id", section_name="app"),
        version=_require_str(app, "version", section_name="app"),
        width=width,
        height=height,
        filesystem_roots=filesystem_roots,
        clipboard=bool(permissions.get("clipboard", False)),
        notifications=bool(permissions.get("notifications", False)),
        subprocess_enabled=bool(permissions.get("subprocess", False)),
        plugins_enabled=bool(runtime.get("plugins_enabled", True)),
        plugin_allowlist=plugin_allowlist,
        strict_plugins=bool(runtime.get("strict_plugins", True)),
    )
