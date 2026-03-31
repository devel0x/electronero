from __future__ import annotations

from pathlib import Path

from pydesk.core.config import AppConfig


class PermissionError(RuntimeError):
    """Raised when bridge operations violate the app permission policy."""


def assert_path_allowed(config: AppConfig, requested_path: Path, app_root: Path) -> Path:
    resolved = requested_path.resolve()
    allowed_roots = []
    for root in config.filesystem_roots:
        candidate = (app_root / root).resolve()
        allowed_roots.append(candidate)

    if not any(str(resolved).startswith(str(root)) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots) or "<none>"
        raise PermissionError(f"Path '{resolved}' is not in allowed roots: {roots}")

    return resolved
