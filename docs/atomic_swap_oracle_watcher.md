# Atomic Swap Oracle Watcher

This document covers two Python scripts located in `contrib/` that implement a simple oracle-based atomic swap mechanism. Both scripts monitor an address on **chain A** and trigger transfers on **chain B** when they detect an incoming transaction with a chain B address.

- `atomic_swap_oracle_watcher.py` – generic version that uses JSON‑RPC 1.0 on both chains
- `atomic_swap_oracle_watcher_v2.py` – version 2 where chain B is Monero and uses the Monero wallet RPC

Each script reads its configuration from environment variables which simplifies deployment.

## Operation

1. The script connects to the RPC interfaces for chain A and chain B using the credentials provided via environment variables.
2. It repeatedly polls the recent transactions to the oracle address on chain A.
3. If a new transaction is found, the script extracts a destination address for chain B.
   - The destination can be encoded in an `OP_RETURN` output as a hex string or included as a normal output address that differs from the oracle address.
4. The amount received by the oracle is then sent on chain B to the extracted address.
   - Version 1 issues a `sendtoaddress` JSON‑RPC call.
   - Version 2 calculates atomic units for Monero and issues a `transfer` wallet RPC call.

## Required Environment Variables

Both scripts use the same set of variables. Example exports are shown below. Values should be adjusted for your setup.

```bash
export ORACLE_ADDRESS="A_ORACLE_ADDRESS_HERE"
export CHAINA_RPCHOST="127.0.0.1"
export CHAINA_RPCPORT="8332"
export CHAINA_RPCUSER="rpcuser_a"
export CHAINA_RPCPASSWORD="secret_a"
export CHAINB_RPCHOST="127.0.0.1"
export CHAINB_RPCPORT="8332"  # use Monero RPC port for version 2
export CHAINB_RPCUSER="rpcuser_b"
export CHAINB_RPCPASSWORD="secret_b"
export POLL_INTERVAL="30"
```

## Usage Examples

Compile‑time checks can be run with Python:

```bash
python3 -m py_compile contrib/atomic_swap_oracle_watcher.py \
    contrib/atomic_swap_oracle_watcher_v2.py
```

Run version 1:

```bash
python3 contrib/atomic_swap_oracle_watcher.py
```

Run version 2 (Monero chain B):

```bash
python3 contrib/atomic_swap_oracle_watcher_v2.py
```

Both scripts will continue running and polling for new transactions until interrupted.
