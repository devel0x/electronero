from __future__ import annotations


class EchoPlugin:
    name = "echo"

    def register(self, bridge: object) -> None:
        setattr(
            bridge,
            "echo_plugin_status",
            lambda: {"status": "ok", "plugin": self.name, "message": "plugin loaded"},
        )


PLUGIN = EchoPlugin()
