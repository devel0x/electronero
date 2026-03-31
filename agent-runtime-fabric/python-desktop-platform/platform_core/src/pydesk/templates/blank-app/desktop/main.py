from __future__ import annotations

import argparse
from pathlib import Path

import webview

from backend.bridge import NativeBridge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true", help="Enable dev-mode logging")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    index_html = root / "frontend" / "index.html"

    bridge = NativeBridge()
    window = webview.create_window(
        title="PyDesk Blank App",
        url=index_html.as_uri(),
        js_api=bridge,
        width=1100,
        height=760,
    )
    webview.start(debug=args.dev)


if __name__ == "__main__":
    main()
