from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RuntimePolicy:
    name: str
    ttl_seconds: int
    cpu_quota: str
    memory_limit_mb: int
    writable_paths: list[str]
    readonly_paths: list[str]
    allowed_tools: set[str]
    allowed_registries: set[str]
    allow_domains: set[str]


class PolicyError(ValueError):
    pass


def load_runtime_policy(policy_path: Path) -> RuntimePolicy:
    data: dict[str, Any] = yaml.safe_load(policy_path.read_text())

    profile = data["runtime_profile"]
    tools = profile["tools"]
    install_policy = tools["install_package"]

    return RuntimePolicy(
        name=profile["name"],
        ttl_seconds=int(profile["resources"]["ttl_seconds"]),
        cpu_quota=str(profile["resources"]["cpu_quota"]),
        memory_limit_mb=int(profile["resources"]["memory_limit_mb"]),
        writable_paths=list(profile["filesystem"]["writable"]),
        readonly_paths=list(profile["filesystem"]["readonly"]),
        allowed_tools=set(tools["allowed"]),
        allowed_registries=set(install_policy["allowed_registries"]),
        allow_domains=set(profile["network"]["allow_domains"]),
    )


def require_tool_allowed(policy: RuntimePolicy, tool_name: str) -> None:
    if tool_name not in policy.allowed_tools:
        raise PolicyError(f"Tool '{tool_name}' is not allowed by runtime profile '{policy.name}'.")


def require_registry_allowed(policy: RuntimePolicy, registry: str) -> None:
    if registry not in policy.allowed_registries:
        raise PolicyError(f"Registry '{registry}' is not allowlisted for installs.")
