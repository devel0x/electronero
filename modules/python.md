# Electronero Python Helpers

This directory contains utilities for interacting with the Electronero daemon and wallet RPC servers.

## `electronero.py`

The module exposes two simple client classes:

* `DaemonRPC` – communicate with a running `electronerod` instance
* `WalletRPC` – communicate with `electronero-wallet-rpc`

Both classes share the same constructor arguments:

```python
client = DaemonRPC(host="127.0.0.1", port=12090)
wallet = WalletRPC(host="127.0.0.1", port=18082)
```
If omitted, ports default to `12090` for the daemon and `18082` for the wallet,
matching the values in `src/cryptonote_config.h`.

### Examples

Fetch the current daemon height:

```python
from modules.python.electronero import DaemonRPC

rpc = DaemonRPC()
print("Height:", rpc.get_block_count())
```

Calling any daemon RPC method dynamically:

```python
info = rpc.call("get_info")
print(info["status"])
```

Transfer funds from the wallet:

```python
from modules.python.electronero import WalletRPC

wallet = WalletRPC()
result = wallet.transfer([
    {"address": "YOUR_ADDRESS", "amount": 1000000000000}
])
print(result)
```

List recent transfers:

```python
history = wallet.get_transfers(in=True, out=True, filter_by_height=True, min_height=0)
print(history["in"])
```

Every RPC method defined in the Electronero daemon and wallet servers can be
called using the :py:meth:`~modules.python.electronero.RPCClient.call` method or
attribute access. For example:

```python
# using attribute access
height = wallet.get_height()["height"]

# or explicitly with call()
accounts = wallet.call("get_accounts")
```

Refer to `src/rpc/core_rpc_server.h` and `src/wallet/wallet_rpc_server.h` for a
complete list of method names. The Python helpers simply forward parameters as
provided and return the decoded JSON result.

The RPC clients raise `RPCError` when a request fails.
