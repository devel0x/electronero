from __future__ import annotations


class SamplePlugin:
    name = "sample"

    def register(self, bridge: object) -> None:
        setattr(bridge, "plugin_ping", lambda: {"ok": True, "plugin": self.name})


PLUGIN = SamplePlugin()
