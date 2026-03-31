from pathlib import Path

import pytest

from pydesk.core.config import AppConfig
from pydesk.core.permissions import PermissionError, assert_path_allowed


def _cfg() -> AppConfig:
    return AppConfig(
        name="demo",
        app_id="com.example.demo",
        version="0.1.0",
        width=1000,
        height=700,
        filesystem_roots=("./data",),
        clipboard=True,
        notifications=False,
        subprocess_enabled=False,
        plugins_enabled=True,
        plugin_allowlist=("echo",),
        strict_plugins=True,
    )


def test_assert_path_allowed_accepts_subpath(tmp_path: Path) -> None:
    cfg = _cfg()
    target = tmp_path / "data" / "a.txt"
    result = assert_path_allowed(cfg, target, tmp_path)
    assert result == target.resolve()


def test_assert_path_allowed_rejects_outside_root(tmp_path: Path) -> None:
    cfg = _cfg()
    target = tmp_path / "outside" / "a.txt"
    with pytest.raises(PermissionError):
        assert_path_allowed(cfg, target, tmp_path)


def test_assert_path_allowed_rejects_path_traversal(tmp_path: Path) -> None:
    cfg = _cfg()
    target = tmp_path / "data" / ".." / "secrets" / "token.txt"
    with pytest.raises(PermissionError):
        assert_path_allowed(cfg, target, tmp_path)
