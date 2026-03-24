"""Runtime-safe server launcher.

Use this when running in constrained shells (mobile/iOS terminals, embedded shells)
where uvicorn signal handler registration may fail.
"""

import os

import uvicorn


class NoSignalServer(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # pragma: no cover
        # Some environments (e.g. iOS shells) cannot register POSIX handlers.
        return


def main() -> None:
    host = os.getenv("ARF_HOST", "0.0.0.0")
    port = int(os.getenv("ARF_PORT", "8080"))
    app_path = os.getenv("ARF_APP", "app:app")
    reload_enabled = os.getenv("ARF_RELOAD", "0") == "1"

    config = uvicorn.Config(app_path, host=host, port=port, reload=reload_enabled, log_level="info")

    # In constrained environments disable signal handlers explicitly.
    if os.getenv("ARF_DISABLE_SIGNALS", "1") == "1":
        server = NoSignalServer(config)
        server.run()
    else:
        uvicorn.Server(config).run()


if __name__ == "__main__":
    main()
