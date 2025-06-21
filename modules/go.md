# Electronero Go Module

The `electronero` package provides a lightweight wrapper for the RPC interfaces of
`electronerod` and `electronero-wallet-rpc`.  It exposes a generic `Client` type
to call any RPC method as well as a few helper functions for common actions.

## Installation

```bash
cd modules/go
go mod tidy
```

The package can then be imported using its module path:

```go
import "electronero"
```

## Usage

Create clients for the daemon and wallet RPC servers using the appropriate URLs.
Calls are performed using JSON RPC. Any method supported by Electronero can be
invoked via `Client.Call`.

```go
package main

import (
        "fmt"
        "electronero"
)

func main() {
        daemon := electronero.NewDaemonClient("http://localhost:26969")
        wallet := electronero.NewWalletClient("http://localhost:26968")

        // Query daemon block height
        height, err := daemon.GetBlockCount()
        if err != nil {
                panic(err)
        }
        fmt.Println("daemon height:", height)

        // Query wallet balance for account 0
        bal, unlocked, err := wallet.GetBalance(0)
        if err != nil {
                panic(err)
        }
        fmt.Println("balance:", bal, "unlocked:", unlocked)

        // Example of calling a custom method
        var netStatus interface{}
        if err := daemon.Call("get_info", nil, &netStatus); err != nil {
                panic(err)
        }
        fmt.Printf("network status: %+v\n", netStatus)
}
```

The `Do` method allows posting JSON to non‑RPC paths for commands that do not
use the standard `/json_rpc` endpoint.



## RPC Method Constants

All daemon and wallet RPC endpoints are represented by constants. Use these with `Client.Call` or `Client.Do` to invoke any RPC method.

```go
// retrieve daemon info using a constant
var info struct{ Height uint64 `json:"height"` }
if err := daemon.Call(electronero.RPCDaemonGetHeight, nil, &info); err != nil {
        panic(err)
}

// call a non-JSON path endpoint
var status interface{}
if err := daemon.Do(electronero.EndpointGetInfo, nil, &status); err != nil {
        panic(err)
}
```

The constants cover every RPC method available in Electronero daemon and wallet RPC servers. Examples include `electronero.RPCWalletTransfer` for sending transactions and `electronero.RPCDaemonGetInfo` for retrieving daemon state. See `consts.go` for the full list.
