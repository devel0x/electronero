from pathlib import Path

from pydesk.cli.main import _template_root


def test_react_vite_fastapi_template_exists() -> None:
    root = _template_root()
    template = root / "react-vite-fastapi"
    assert template.exists()
    assert (template / "backend" / "main.py").exists()
    assert (template / "frontend" / "package.json").exists()
    assert (template / "desktop" / "main.py").exists()
