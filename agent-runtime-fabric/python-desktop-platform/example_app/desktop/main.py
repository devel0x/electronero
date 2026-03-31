from __future__ import annotations

from pathlib import Path

import webview

from backend.bridge import Bridge
from pydesk.core.config import load_config
from pydesk.core.plugins import load_plugins


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    config = load_config(root)
    bridge = Bridge(config=config, app_root=root)

    result = load_plugins(
        root / "plugins",
        bridge,
        allowlist=config.plugin_allowlist,
        strict=config.strict_plugins,
    ) if config.plugins_enabled else None

    if result is not None:
        print(f"Loaded plugins: {[plugin.name for plugin in result.loaded]}")
        if result.errors:
            for error in result.errors:
                print(f"Plugin load error ({error.source.name}): {error.message}")

    url = (root / "frontend" / "index.html").as_uri()
    webview.create_window(config.name, url, js_api=bridge, width=config.width, height=config.height)
    webview.start(debug=True)
