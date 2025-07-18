#!/usr/bin/env python3
"""Watch inbound token transactions and trigger actions based on memos."""
import argparse
import base64
import json
import subprocess
import time
from http.client import HTTPConnection
from typing import Dict, List


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
            "id": "memo-watcher",
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


def parse_actions(entries: List[str]) -> Dict[str, str]:
    actions: Dict[str, str] = {}
    for entry in entries:
        if ":" not in entry:
            continue
        memo, cmd = entry.split(":", 1)
        actions[memo] = cmd
    return actions


class TokenMemoWatcher:
    def __init__(self, rpc: RPCClient, token: str, address: str, actions: Dict[str, str], interval: int) -> None:
        self.rpc = rpc
        self.token = token
        self.address = address
        self.interval = interval
        self.actions = actions
        self.seen = set()

    def poll(self) -> None:
        history = self.rpc.call("token_history", [self.token, self.address])
        for item in history:
            memo = item.get("memo")
            if not memo:
                continue
            key = json.dumps(item, sort_keys=True)
            if key in self.seen:
                continue
            self.seen.add(key)
            if memo in self.actions:
                cmd = self.actions[memo].format(**item)
                subprocess.call(cmd, shell=True)
            else:
                print(json.dumps(item))

    def run(self) -> None:
        while True:
            try:
                self.poll()
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(self.interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch token memos and trigger actions")
    parser.add_argument("--rpchost", default="127.0.0.1")
    parser.add_argument("--rpcport", default=8332, type=int)
    parser.add_argument("--rpcuser", required=True)
    parser.add_argument("--rpcpassword", required=True)
    parser.add_argument("--token", required=True, help="Token identifier")
    parser.add_argument("--address", required=True, help="Wallet address filter")
    parser.add_argument("--interval", default=60, type=int, help="Polling interval in seconds")
    parser.add_argument(
        "--on-memo",
        action="append",
        default=[],
        metavar="MEMO:CMD",
        help="Command to run when memo seen. Placeholders {from},{to},{amount},{memo}",
    )
    args = parser.parse_args()

    actions = parse_actions(args.on_memo)
    rpc = RPCClient(args.rpchost, args.rpcport, args.rpcuser, args.rpcpassword)
    watcher = TokenMemoWatcher(rpc, args.token, args.address, actions, args.interval)
    watcher.run()


if __name__ == "__main__":
    main()
