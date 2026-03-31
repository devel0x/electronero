from pathlib import Path

import pytest

from pydesk.core.config import ConfigError, load_config


def test_load_config(tmp_path: Path) -> None:
    (tmp_path / "platform.toml").write_text(
        """
[app]
name = "demo"
id = "com.example.demo"
version = "0.1.0"

[desktop]
width = 1000
height = 700

[permissions]
filesystem = ["./data"]
clipboard = true
notifications = false
subprocess = false

[runtime]
plugins_enabled = true
strict_plugins = true
plugin_allowlist = ["echo"]
""".strip(),
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.name == "demo"
    assert cfg.width == 1000
    assert cfg.filesystem_roots == ("./data",)
    assert cfg.plugins_enabled is True
    assert cfg.plugin_allowlist == ("echo",)


def test_load_config_raises_for_small_window(tmp_path: Path) -> None:
    (tmp_path / "platform.toml").write_text(
        """
[app]
name = "demo"
id = "com.example.demo"
version = "0.1.0"

[desktop]
width = 200
height = 100
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(tmp_path)
