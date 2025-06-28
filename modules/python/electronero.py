"""High level helpers for Electronero RPC endpoints.

This module provides thin wrappers around the daemon and
wallet JSON RPC interfaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Callable

import requests


class RPCError(Exception):
    """Raised when the RPC server returns an error."""


@dataclass
class RPCClient:
    host: str = "127.0.0.1"
    port: int = 0
    user: Optional[str] = None
    password: Optional[str] = None
    timeout: Optional[int] = 30

    def _request(self, method: str, params: Optional[Any] = None) -> Any:
        url = f"http://{self.host}:{self.port}/json_rpc"
        payload = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        auth = (self.user, self.password) if self.user else None
        response = requests.post(url, json=payload, auth=auth, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RPCError(data["error"])
        return data.get("result")

    def call(self, method: str, params: Optional[Any] = None) -> Any:
        """Call an arbitrary RPC method."""
        return self._request(method, params)

    def __getattr__(self, name: str) -> Callable[..., Any]:
        """Provide attribute access as RPC calls."""

        def rpc_method(**params: Any) -> Any:
            return self.call(name, params or None)

        return rpc_method


class DaemonRPC(RPCClient):
    """Client for the Electronero daemon RPC."""

    def __init__(self, host: str = "127.0.0.1", port: int = 12090, **kw: Any) -> None:
        super().__init__(host=host, port=port, **kw)

    def get_block_count(self) -> int:
        result = self.call("getblockcount")
        return result.get("count")

    def get_block_hash(self, height: int) -> str:
        result = self.call("on_getblockhash", [height])
        return result

    def get_block_header_by_height(self, height: int) -> Dict[str, Any]:
        params = {"height": height}
        result = self.call("getblockheaderbyheight", params)
        return result.get("block_header")

    def send_raw_transaction(self, tx_as_hex: str) -> Dict[str, Any]:
        params = {"tx_as_hex": tx_as_hex}
        return self.call("send_raw_transaction", params)


class WalletRPC(RPCClient):
    """Client for the Electronero wallet RPC."""

    def __init__(self, host: str = "127.0.0.1", port: int = 18082, **kw: Any) -> None:
        super().__init__(host=host, port=port, **kw)

    def get_balance(self, account_index: int = 0) -> Dict[str, Any]:
        params = {"account_index": account_index}
        return self.call("get_balance", params)

    def get_address(self, account_index: int = 0, address_index: Optional[List[int]] = None) -> Dict[str, Any]:
        params: Dict[str, Any] = {"account_index": account_index}
        if address_index is not None:
            params["address_index"] = address_index
        return self.call("get_address", params)

    def transfer(self, destinations: List[Dict[str, Any]], account_index: int = 0, **options: Any) -> Dict[str, Any]:
        params = {
            "destinations": destinations,
            "account_index": account_index,
        }
        params.update(options)
        return self.call("transfer", params)

    def get_transfers(self, **params: Any) -> Dict[str, Any]:
        """Return incoming and outgoing transfers matching the given filters."""
        return self.call("get_transfers", params)
