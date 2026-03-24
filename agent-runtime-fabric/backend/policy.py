from __future__ import annotations

from pathlib import PurePosixPath

ALLOWED_INSTALL_REGISTRIES = {
    "python": {"pypi.org"},
    "node": {"registry.npmjs.org"},
}

WRITEABLE_PREFIXES = [
    "/runtime/workspaces",
    "/runtime/tmp",
    "/runtime/output",
    "/runtime/cache",
]

BLOCKED_SEGMENTS = {"..", "~", "/etc", "/root", "/var/run", "/proc", "/sys"}


def normalize_path(path: str) -> str:
    normalized = str(PurePosixPath(path))
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    return normalized


def ensure_writable(path: str) -> None:
    normalized = normalize_path(path)
    if any(segment in normalized for segment in BLOCKED_SEGMENTS):
        raise ValueError(f"blocked path segment in '{path}'")

    if not any(normalized.startswith(prefix) for prefix in WRITEABLE_PREFIXES):
        raise ValueError(f"path '{path}' is outside writable zones")


def ensure_readable(path: str) -> None:
    normalized = normalize_path(path)
    if any(segment in normalized for segment in BLOCKED_SEGMENTS):
        raise ValueError(f"blocked path segment in '{path}'")


def validate_install(package: str, version: str | None) -> None:
    if not package or " " in package:
        raise ValueError("invalid package name")
    if version and any(c in version for c in ";|&"):
        raise ValueError("invalid version")
