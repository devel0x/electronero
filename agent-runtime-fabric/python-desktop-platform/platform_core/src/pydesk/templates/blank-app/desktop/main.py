from __future__ import annotations

import argparse
from pathlib import Path

import webview

from backend.bridge import NativeBridge
from pydesk.core.config import load_config
from pydesk.core.plugins import load_plugins


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Enable dev-mode logging")
    args = parser.parse_args()

    app_root = Path(__file__).resolve().parents[1]
    index_html = app_root / "frontend" / "index.html"

    config = load_config(app_root)
    bridge = NativeBridge(config=config, app_root=app_root)

    result = load_plugins(
        app_root / "plugins",
        bridge,
        allowlist=config.plugin_allowlist,
        strict=config.strict_plugins,
    ) if config.plugins_enabled else None

    if result is not None:
        print(f"PyDesk startup: loaded {len(result.loaded)} plugin(s)")
        if result.errors:
            for error in result.errors:
                print(f"Plugin load error ({error.source.name}): {error.message}")

    webview.create_window(
        title=f"{config.name} ({config.version})",
        url=index_html.as_uri(),
        js_api=bridge,
        width=config.width,
        height=config.height,
    )
    webview.start(debug=args.dev)


if __name__ == "__main__":
    main()
