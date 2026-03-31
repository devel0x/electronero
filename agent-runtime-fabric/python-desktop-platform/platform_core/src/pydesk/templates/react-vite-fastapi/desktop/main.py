from __future__ import annotations

import argparse
from pathlib import Path

import webview

from pydesk.core.config import load_config
from pydesk.core.plugins import load_plugins


class Bridge:
    def __init__(self, app_root: Path):
        self._app_root = app_root

    def app_paths(self) -> dict[str, str]:
        return {
            "root": str(self._app_root),
            "data": str((self._app_root / "data").resolve()),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Use Vite dev server URL")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    config = load_config(root)

    bridge = Bridge(root)
    result = load_plugins(
        root / "plugins",
        bridge,
        allowlist=config.plugin_allowlist,
        strict=config.strict_plugins,
    ) if config.plugins_enabled else None

    if result and result.errors:
        for error in result.errors:
            print(f"Plugin load error ({error.source.name}): {error.message}")

    if args.dev:
        url = "http://127.0.0.1:5173"
    else:
        url = (root / "frontend" / "dist" / "index.html").as_uri()

    webview.create_window(config.name, url, js_api=bridge, width=config.width, height=config.height)
    webview.start(debug=args.dev)


if __name__ == "__main__":
    main()
