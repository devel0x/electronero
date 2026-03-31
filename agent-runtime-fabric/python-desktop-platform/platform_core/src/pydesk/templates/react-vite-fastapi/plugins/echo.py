from __future__ import annotations


class EchoPlugin:
    name = "echo"

    def register(self, bridge: object) -> None:
        setattr(bridge, "plugin_echo", lambda: {"plugin": self.name, "status": "loaded"})


PLUGIN = EchoPlugin()
