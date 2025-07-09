#!/usr/bin/env python3
"""Simple watcher for bridgefunds deposits.

This example polls an Interchained node for blocks containing outputs
sent to ``ETH_BRIDGE_ADDRESS``. When a deposit is found, it creates a
corresponding transaction on the Ethereum sidechain via Web3. The script
requires ``requests`` and ``web3`` (optional if only monitoring).

Environment variables control RPC endpoints::

    INTERCHAINED_RPC=http://user:pass@127.0.0.1:18443
    ETH_RPC=http://127.0.0.1:8545
    ETH_KEY=<private key used for sidechain transactions>

Run ``python3 bridge_watcher.py`` to start polling.
"""
import os
import time
import json
import requests

try:
    from web3 import Web3
except ImportError:  # pragma: no cover - optional dependency
    Web3 = None

BRIDGE_ADDR = "2222222222222222222224oLvT3"
CHECK_INTERVAL = 30  # seconds
CONFIRMATIONS = 6

RPC_URL = os.getenv("INTERCHAINED_RPC", "http://user:pass@127.0.0.1:18443")
ETH_RPC = os.getenv("ETH_RPC", "http://127.0.0.1:8545")
ETH_KEY = os.getenv("ETH_KEY")


def rpc_call(method, params=None):
    payload = json.dumps({"jsonrpc": "1.0", "id": "bridge", "method": method, "params": params or []})
    r = requests.post(RPC_URL, data=payload)
    r.raise_for_status()
    return r.json()["result"]


def find_bridge_output(tx):
    dest = None
    amount = 0
    for vout in tx.get("vout", []):
        spk = vout.get("scriptPubKey", {})
        if spk.get("addresses") == [BRIDGE_ADDR]:
            amount += vout["value"]
        if spk.get("type") == "nulldata" and "asm" in spk:
            parts = spk["asm"].split()
            if len(parts) == 2:
                try:
                    dest = bytes.fromhex(parts[1]).decode("utf-8")
                except ValueError:
                    pass
    return dest, amount if dest else (None, None)


def submit_sidechain_tx(to_addr, amount):
    if Web3 is None or ETH_KEY is None:
        print(f"Would credit {amount} ETH to {to_addr}. Install web3 and set ETH_KEY to send.")
        return
    w3 = Web3(Web3.HTTPProvider(ETH_RPC))
    acct = w3.eth.account.from_key(ETH_KEY)
    tx = {
        "to": to_addr,
        "value": w3.to_wei(amount, "ether"),
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
    }
    signed = acct.sign_transaction(tx)
    txid = w3.eth.send_raw_transaction(signed.rawTransaction)
    print("Sent sidechain tx", txid.hex())


def main():
    last = rpc_call("getblockcount") - CONFIRMATIONS
    while True:
        tip = rpc_call("getblockcount") - CONFIRMATIONS
        while last < tip:
            last += 1
            blockhash = rpc_call("getblockhash", [last])
            block = rpc_call("getblock", [blockhash, 2])
            for tx in block.get("tx", []):
                eth_addr, amount = find_bridge_output(tx)
                if eth_addr:
                    print(f"Lock {amount} to {eth_addr} in block {last}")
                    submit_sidechain_tx(eth_addr, amount)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
