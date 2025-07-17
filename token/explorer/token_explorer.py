#!/usr/bin/env python3
"""Simple token explorer using the `token_history` RPC.

This script connects to an Interchained node via JSON-RPC and prints the
history of a given token. Optionally, results can be filtered by address.
"""

import argparse
import base64
import json
from http.client import HTTPConnection
from typing import List


class RPCClient:
    """Minimal JSON-RPC client."""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        auth = f"{user}:{password}".encode()
        self.authhdr = b"Basic " + base64.b64encode(auth)
        self.conn = HTTPConnection(host, port=port, timeout=30)

    def call(self, method: str, params: List = None):
        if params is None:
            params = []
        obj = {
            "jsonrpc": "1.0",
            "id": "token-explorer",
            "method": method,
            "params": params,
        }
        self.conn.request(
            "POST",
            "/",
            json.dumps(obj),
            {"Authorization": self.authhdr, "Content-type": "application/json"},
        )
        resp = self.conn.getresponse()
        if resp is None:
            raise ConnectionError("no response from RPC server")
        body = resp.read().decode()
        reply = json.loads(body)
        if reply.get("error"):
            raise RuntimeError(reply["error"])
        return reply["result"]


def format_history(entries: List[dict]) -> str:
    header = f"{'OP':<8}{'FROM':<36}{'TO':<36}{'AMOUNT':<15}{'MEMO'}"
    lines = [header, "-" * len(header)]
    for e in entries:
        line = f"{e.get('op',''):<8}{e.get('from',''):<36}{e.get('to',''):<36}{e.get('amount',''):<15}{e.get('memo','')}"
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore token history")
    parser.add_argument("--rpchost", default="127.0.0.1")
    parser.add_argument("--rpcport", default=8332, type=int)
    parser.add_argument("--rpcuser", required=True)
    parser.add_argument("--rpcpassword", required=True)
    parser.add_argument("token", help="Token identifier")
    parser.add_argument("filter", nargs="?", help="Optional address filter")
    args = parser.parse_args()

    rpc = RPCClient(args.rpchost, args.rpcport, args.rpcuser, args.rpcpassword)
    params = [args.token]
    if args.filter:
        params.append(args.filter)
    history = rpc.call("token_history", params)
    print(format_history(history))


if __name__ == "__main__":
    main()
