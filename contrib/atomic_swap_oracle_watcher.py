#!/usr/bin/env python3
"""Watch an oracle address for atomic swap requests.

This script monitors transactions to a specific chain A address. If a
transaction to the oracle address contains a chain B address in an
``OP_RETURN`` output, the same amount received is automatically sent to
the provided chain B address using chain B RPC.
"""

import argparse
import base64
import json
import time
from http.client import HTTPConnection
from typing import List, Optional, Set


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
            "id": "oracle-watcher",
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


class OracleWatcher:
    def __init__(
        self,
        oracle_address: str,
        chaina_rpc: RPCClient,
        chainb_rpc: RPCClient,
        interval: int = 30,
    ) -> None:
        self.oracle_address = oracle_address
        self.chaina_rpc = chaina_rpc
        self.chainb_rpc = chainb_rpc
        self.interval = interval
        self.seen: Set[str] = set()

    def run(self) -> None:
        while True:
            try:
                self.poll()
            except Exception as e:
                print(f"Error: {e}")
            time.sleep(self.interval)

    def poll(self) -> None:
        txs = self.chaina_rpc.call("listtransactions", ["*", 100, 0, True])
        for tx in txs:
            if tx.get("category") != "receive" or tx.get("address") != self.oracle_address:
                continue
            txid = tx.get("txid")
            if not txid or txid in self.seen:
                continue
            raw = self.chaina_rpc.call("getrawtransaction", [txid, True])
            chainb_address = self._extract_chainb_address(raw)
            if not chainb_address:
                continue
            amount = self._amount_to_oracle(raw)
            if amount <= 0:
                continue
            self.chainb_rpc.call("sendtoaddress", [chainb_address, amount])
            print(f"Sent {amount} on chain B to {chainb_address} for tx {txid}")
            self.seen.add(txid)

    def _amount_to_oracle(self, raw: dict) -> float:
        total = 0.0
        for vout in raw.get("vout", []):
            spk = vout.get("scriptPubKey", {})
            if self.oracle_address in spk.get("addresses", []):
                total += float(vout.get("value", 0))
        return total

    def _extract_chainb_address(self, raw: dict) -> Optional[str]:
        for vout in raw.get("vout", []):
            spk = vout.get("scriptPubKey", {})
            asm = spk.get("asm", "")
            if asm.startswith("OP_RETURN "):
                data_hex = asm.split(" ", 1)[1]
                try:
                    data = bytes.fromhex(data_hex).decode()
                    return data.strip()
                except Exception:
                    continue
            for addr in spk.get("addresses", []):
                if addr != self.oracle_address:
                    return addr
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch oracle address for atomic swaps")
    parser.add_argument("--oracle", required=True, help="Oracle address on chain A")
    parser.add_argument("--chaina-rpchost", default="127.0.0.1")
    parser.add_argument("--chaina-rpcport", type=int, default=8332)
    parser.add_argument("--chaina-rpcuser", required=True)
    parser.add_argument("--chaina-rpcpassword", required=True)
    parser.add_argument("--chainb-rpchost", default="127.0.0.1")
    parser.add_argument("--chainb-rpcport", type=int, default=8332)
    parser.add_argument("--chainb-rpcuser", required=True)
    parser.add_argument("--chainb-rpcpassword", required=True)
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chaina = RPCClient(args.chaina_rpchost, args.chaina_rpcport, args.chaina_rpcuser, args.chaina_rpcpassword)
    chainb = RPCClient(args.chainb_rpchost, args.chainb_rpcport, args.chainb_rpcuser, args.chainb_rpcpassword)
    watcher = OracleWatcher(args.oracle, chaina, chainb, args.interval)
    watcher.run()


if __name__ == "__main__":
    main()
