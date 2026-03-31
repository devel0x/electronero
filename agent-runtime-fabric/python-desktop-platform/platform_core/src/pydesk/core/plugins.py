from __future__ import annotations

import importlib.util
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


def load_plugins(plugins_dir: Path, bridge: object) -> list[LoadedPlugin]:
    loaded: list[LoadedPlugin] = []
    if not plugins_dir.exists():
        return loaded

    for plugin_file in sorted(plugins_dir.glob("*.py")):
        if plugin_file.name.startswith("_"):
            continue

        spec = importlib.util.spec_from_file_location(f"pydesk_plugin_{plugin_file.stem}", plugin_file)
        if spec is None or spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        plugin = getattr(module, "PLUGIN", None)
        if plugin is None:
            continue

        plugin.register(bridge)
        loaded.append(LoadedPlugin(name=getattr(plugin, "name", plugin_file.stem), source=plugin_file, module=module))

    return loaded
