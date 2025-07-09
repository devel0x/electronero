#!/usr/bin/env python3
"""Watch bridge contract events to release funds on chain A.

This script monitors a contract on the Ethereum sidechain for events that
represent tokens being burned or locked for withdrawal back to chain A. When
an event is detected, it uses the Interchained RPC to send the corresponding
coins to the user's address on chain A.

Environment variables control RPC endpoints and contract details:

    INTERCHAINED_RPC=http://user:pass@127.0.0.1:18443
    ETH_RPC=http://127.0.0.1:8545
    BRIDGE_CONTRACT=<Ethereum address of the bridge contract>
    BRIDGE_ABI=<path to a JSON file containing the contract ABI>

Install ``web3`` and ``requests`` to run the watcher.
"""
import json
import os
import time
import requests

from web3 import Web3

RPC_URL = os.getenv("INTERCHAINED_RPC", "http://user:pass@127.0.0.1:18443")
ETH_RPC = os.getenv("ETH_RPC", "http://127.0.0.1:8545")
CONTRACT_ADDR = os.getenv("BRIDGE_CONTRACT")
ABI_PATH = os.getenv("BRIDGE_ABI")
CHECK_INTERVAL = 30  # seconds

if not CONTRACT_ADDR or not ABI_PATH:
    raise SystemExit("BRIDGE_CONTRACT and BRIDGE_ABI must be set")

with open(ABI_PATH, "r", encoding="utf-8") as f:
    ABI = json.load(f)

w3 = Web3(Web3.HTTPProvider(ETH_RPC))
contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDR), abi=ABI)

def rpc_call(method, params=None):
    payload = json.dumps({"jsonrpc": "1.0", "id": "bridge", "method": method, "params": params or []})
    r = requests.post(RPC_URL, data=payload)
    r.raise_for_status()
    return r.json()["result"]

# Assume the contract emits an event ``BridgeBurn(address indexed sender, string dest, uint256 amount)``
EVENT = contract.events.BridgeBurn

def handle_event(evt):
    dest = evt["args"]["dest"]
    amount = evt["args"]["amount"] / 1e8  # assume satoshi precision
    print(f"Release {amount} to {dest} from {evt['args']['sender']}")
    try:
        txid = rpc_call("sendtoaddress", [dest, amount])
        print("Sent chain A tx", txid)
    except requests.HTTPError as e:
        print("RPC error", e)

def main():
    last = w3.eth.block_number
    while True:
        for evt in EVENT.get_logs(fromBlock=last + 1, toBlock='latest'):
            last = max(last, evt.blockNumber)
            handle_event(evt)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
