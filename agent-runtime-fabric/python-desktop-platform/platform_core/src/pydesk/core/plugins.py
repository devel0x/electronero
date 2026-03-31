from __future__ import annotations

import importlib.util
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Protocol


class PluginProtocol(Protocol):
    name: str

    def register(self, bridge: object) -> None:
        ...


@dataclass(slots=True)
class LoadedPlugin:
    name: str
    source: Path
    module: ModuleType


@dataclass(slots=True)
class PluginLoadError:
    source: Path
    message: str


@dataclass(slots=True)
class PluginLoadResult:
    loaded: list[LoadedPlugin]
    errors: list[PluginLoadError]


def load_plugins(
    plugins_dir: Path,
    bridge: object,
    *,
    allowlist: tuple[str, ...] = (),
    strict: bool = True,
) -> PluginLoadResult:
    loaded: list[LoadedPlugin] = []
    errors: list[PluginLoadError] = []

    if not plugins_dir.exists():
        return PluginLoadResult(loaded=loaded, errors=errors)

    allowed = set(allowlist)

    for plugin_file in sorted(plugins_dir.glob("*.py")):
        if plugin_file.name.startswith("_"):
            continue

        if allowed and plugin_file.stem not in allowed:
            errors.append(PluginLoadError(source=plugin_file, message="plugin is not allowlisted"))
            if strict:
                break
            continue

        try:
            spec = importlib.util.spec_from_file_location(f"pydesk_plugin_{plugin_file.stem}", plugin_file)
            if spec is None or spec.loader is None:
                raise RuntimeError("could not create module spec")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            plugin = getattr(module, "PLUGIN", None)
            if plugin is None:
                raise RuntimeError("PLUGIN attribute missing")

            plugin.register(bridge)
            loaded.append(LoadedPlugin(name=getattr(plugin, "name", plugin_file.stem), source=plugin_file, module=module))
        except Exception as exc:  # deliberate: plugin code is untrusted extension code
            msg = f"{exc}\n{traceback.format_exc(limit=2)}"
            errors.append(PluginLoadError(source=plugin_file, message=msg))
            if strict:
                break

    return PluginLoadResult(loaded=loaded, errors=errors)
