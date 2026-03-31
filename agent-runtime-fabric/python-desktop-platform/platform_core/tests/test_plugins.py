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
    loaded = load_plugins(plugins_dir, bridge)
    assert len(loaded) == 1
    assert loaded[0].name == "demo"
    assert bridge.demo_feature()["ok"] is True
