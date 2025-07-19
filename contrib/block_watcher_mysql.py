#!/usr/bin/env python3
"""Watch token history and update MySQL balances.

This script monitors token transactions via the ``token_history`` RPC and
triggers a database update whenever funds are received by one of the
target addresses. The memo field is used to identify a user in MySQL.
"""

import argparse
import base64
import json
import time
from http.client import HTTPConnection
from typing import Dict, List, Optional, Set

import mysql.connector  # type: ignore


class RPCClient:
    """Minimal JSON-RPC client."""

    def __init__(self, host: str, port: int, user: str, password: str) -> None:
        auth = f"{user}:{password}".encode()
        self.authhdr = b"Basic " + base64.b64encode(auth)
        self.conn = HTTPConnection(host, port=port, timeout=30)

    def call(self, method: str, params: Optional[List] = None):
        if params is None:
            params = []
        obj = {
            "jsonrpc": "1.0",
            "id": "token-watcher",
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


class TokenBlockWatcher:
    def __init__(self, rpc: RPCClient, token: str, addresses: List[str], interval: int, db_cfg: Dict[str, str]) -> None:
        self.rpc = rpc
        self.token = token
        self.addresses = addresses
        self.interval = interval
        self.db_cfg = db_cfg
        self.seen: Set[str] = set()

    def poll(self) -> None:
        for address in self.addresses:
            history = self.rpc.call("token_history", [self.token, address])
            for item in history:
                if item.get("to") != address:
                    continue
                key = json.dumps(item, sort_keys=True)
                if key in self.seen:
                    continue
                self.seen.add(key)
                self.handle_entry(item)

    def handle_entry(self, entry: Dict) -> None:
        memo = entry.get("memo")
        if not memo:
            return
        conn = mysql.connector.connect(**self.db_cfg)
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, balance FROM users WHERE memo=%s", (memo,))
        row = cur.fetchone()
        if row:
            new_balance = row["balance"] + float(entry.get("amount", 0))
            cur.execute("UPDATE users SET balance=%s WHERE id=%s", (new_balance, row["id"]))
            conn.commit()
        cur.close()
        conn.close()

    def run(self) -> None:
        while True:
            try:
                self.poll()
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(self.interval)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch token history and update MySQL")
    parser.add_argument("--rpchost", default="127.0.0.1")
    parser.add_argument("--rpcport", default=8332, type=int)
    parser.add_argument("--rpcuser", required=True)
    parser.add_argument("--rpcpassword", required=True)
    parser.add_argument("--token", required=True, help="Token identifier")
    parser.add_argument("--address", action="append", dest="addresses", required=True, help="Address to watch (can be repeated)")
    parser.add_argument("--interval", default=60, type=int, help="Polling interval in seconds")
    parser.add_argument("--dbhost", default="127.0.0.1")
    parser.add_argument("--dbuser", default="root")
    parser.add_argument("--dbpassword", default="")
    parser.add_argument("--dbname", default="tokens")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_cfg = {"host": args.dbhost, "user": args.dbuser, "password": args.dbpassword, "database": args.dbname}
    rpc = RPCClient(args.rpchost, args.rpcport, args.rpcuser, args.rpcpassword)
    watcher = TokenBlockWatcher(rpc, args.token, args.addresses, args.interval, db_cfg)
    watcher.run()


if __name__ == "__main__":
    main()
