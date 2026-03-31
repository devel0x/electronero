from __future__ import annotations

from pathlib import Path

import webview

from backend.bridge import Bridge


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    url = (root / "frontend" / "index.html").as_uri()
    webview.create_window("Sample Workbench", url, js_api=Bridge(), width=1200, height=800)
    webview.start(debug=True)
