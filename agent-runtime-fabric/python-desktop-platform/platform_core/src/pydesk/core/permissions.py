from __future__ import annotations

from pathlib import Path

from pydesk.core.config import AppConfig


class PermissionError(RuntimeError):
    """Raised when bridge operations violate the app permission policy."""


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def assert_path_allowed(config: AppConfig, requested_path: Path, app_root: Path) -> Path:
    resolved = requested_path.resolve()
    allowed_roots = [(app_root / root).resolve() for root in config.filesystem_roots]

    if not allowed_roots:
        raise PermissionError("No filesystem roots are configured; all path access is denied")

    if not any(_is_relative_to(resolved, root) for root in allowed_roots):
        roots = ", ".join(str(root) for root in allowed_roots)
        raise PermissionError(f"Path '{resolved}' is not in allowed roots: {roots}")

    return resolved
