#!/usr/bin/env python3
"""Watch an oracle address for atomic swap requests (version 2).

This version uses Monero as chain B. Incoming transactions to the
oracle address on chain A are scanned for a Monero address in an
``OP_RETURN`` output. When detected, the same amount is transferred to
that Monero address using the wallet RPC.
"""

import os
import base64
import json
import time
from http.client import HTTPConnection
from typing import Dict, List, Optional, Set


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


class MoneroRPCClient(RPCClient):
    """RPC client that speaks JSON-RPC 2.0 used by Monero."""

    def call(self, method: str, params: Optional[Dict] = None):
        if params is None:
            params = {}
        obj = {
            "jsonrpc": "2.0",
            "id": "oracle-watcher",
            "method": method,
            "params": params,
        }
        self.conn.request(
            "POST",
            "/json_rpc",
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
            atomic_amount = int(amount * 1_000_000_000_000)
            params = {"destinations": [{"address": chainb_address, "amount": atomic_amount}]}
            self.chainb_rpc.call("transfer", params)
            print(f"Sent {amount} XMR to {chainb_address} for tx {txid}")
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


def load_env() -> dict:
    """Load configuration from environment variables."""
    def env(name: str, default: Optional[str] = None, required: bool = False):
        value = os.getenv(name, default)
        if required and value is None:
            raise RuntimeError(f"Missing required env var {name}")
        return value

    cfg = {
        "oracle": env("ORACLE_ADDRESS", required=True),
        "chaina_rpchost": env("CHAINA_RPCHOST", "127.0.0.1"),
        "chaina_rpcport": int(env("CHAINA_RPCPORT", "8332")),
        "chaina_rpcuser": env("CHAINA_RPCUSER", required=True),
        "chaina_rpcpassword": env("CHAINA_RPCPASSWORD", required=True),
        "chainb_rpchost": env("CHAINB_RPCHOST", "127.0.0.1"),
        "chainb_rpcport": int(env("CHAINB_RPCPORT", "8332")),
        "chainb_rpcuser": env("CHAINB_RPCUSER", required=True),
        "chainb_rpcpassword": env("CHAINB_RPCPASSWORD", required=True),
        "interval": int(env("POLL_INTERVAL", "30")),
    }
    return cfg


def main() -> None:
    cfg = load_env()
    chaina = RPCClient(cfg["chaina_rpchost"], cfg["chaina_rpcport"], cfg["chaina_rpcuser"], cfg["chaina_rpcpassword"])
    chainb = MoneroRPCClient(cfg["chainb_rpchost"], cfg["chainb_rpcport"], cfg["chainb_rpcuser"], cfg["chainb_rpcpassword"])
    watcher = OracleWatcher(cfg["oracle"], chaina, chainb, cfg["interval"])
    watcher.run()


if __name__ == "__main__":
    main()
