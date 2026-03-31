from pathlib import Path

from pydesk.core.plugins import load_plugins


class Bridge:
    pass


def test_load_plugins_registers_capability(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "demo.py").write_text(
        """
class DemoPlugin:
    name = "demo"

    def register(self, bridge):
        bridge.demo_feature = lambda: {"ok": True}

PLUGIN = DemoPlugin()
""".strip(),
        encoding="utf-8",
    )

    bridge = Bridge()
    result = load_plugins(plugins_dir, bridge, allowlist=("demo",), strict=True)
    assert len(result.loaded) == 1
    assert result.loaded[0].name == "demo"
    assert not result.errors
    assert bridge.demo_feature()["ok"] is True


def test_load_plugins_rejects_non_allowlisted(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "blocked.py").write_text("PLUGIN = object()", encoding="utf-8")

    bridge = Bridge()
    result = load_plugins(plugins_dir, bridge, allowlist=("demo",), strict=False)
    assert not result.loaded
    assert result.errors
    assert "allowlisted" in result.errors[0].message
