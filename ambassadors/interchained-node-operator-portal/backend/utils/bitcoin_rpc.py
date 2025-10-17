"""Helpers for performing lightweight node health checks."""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

import httpx


@dataclass
class NodeHealth:
    is_online: bool
    latency_ms: float
    block_height: Optional[int]
    rpc_responding: bool
    p2p_online: bool = False
    is_fully_online: bool = False


async def _check_tcp_connectivity(host: str, port: int, timeout: float = 2.0) -> float:
    start = time.perf_counter()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
    except (OSError, asyncio.TimeoutError):
        return -1.0
    else:
        writer.close()
        await writer.wait_closed()
        return (time.perf_counter() - start) * 1000


async def _fetch_rpc_height(rpc_url: str, timeout: float = 2.0) -> tuple[bool, Optional[int]]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                rpc_url,
                json={"jsonrpc": "1.0", "id": "health", "method": "getblockcount", "params": []},
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return False, None

    height = None
    if isinstance(payload, dict):
        height = payload.get("result")
        if isinstance(height, str) and height.isdigit():
            height = int(height)
    return True, height if isinstance(height, int) else None


async def check_node_health(p2p_address: str, rpc_url: str) -> NodeHealth:
    """Check whether a node responds over P2P and RPC interfaces."""

    latency_ms = -1.0
    rpc_ok = False
    block_height: Optional[int] = None

    if ":" in p2p_address:
        host, port_str = p2p_address.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 0
        if host and port:
            latency_ms = await _check_tcp_connectivity(host, port)

    parsed = urlparse(rpc_url)
    if parsed.scheme and parsed.netloc:
        rpc_ok, block_height = await _fetch_rpc_height(rpc_url)

    p2p_ok = latency_ms >= 0
    is_online = p2p_ok
    return NodeHealth(
        is_online=is_online,
        latency_ms=latency_ms if latency_ms >= 0 else -1,
        block_height=block_height,
        rpc_responding=rpc_ok,
        p2p_online=p2p_ok,
        is_fully_online=p2p_ok and rpc_ok,
    )
