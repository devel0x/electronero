# Electronero Network

## EI-1.0 Electronero legacy Cryptonote coins
ETNX / ETNXP / LTNX / GLDX / CRFI  </br>
 
## EI-2.0 Electronero Smart Chain
xAssets & XRC-20 tokens are minted for token swaps & airdrops on Electronero Smart Chain. </br>
EI-2.0 is Deploying main net on 09/09/2021. EI-1.0 holders will be airdropped xAssets at various rates through cross-chain atomic swaps.</br>
More intel released on the website and through social media. </br>
Electronero Network Core contributors are mainly active on Telegram <a href='https://t.me/electronero'>join the community</a></br>
xAssets (airdrops & swaps): xETNX / xETNXP / xLTNX / xGLDX / xCRFI / xXMR / xETN

Source code forked from Monero, Blockchain forked from Electroneum. Many security updates and unique features have been added over the years. 

`Copyright (c) 2014-2018 The Monero Project.
Portions Copyright (c) 2012-2013 The Cryptonote developers.
Portions Copyright (c) 2017-2018 The Electroneum developers.  
Portions Copyright (c) ~2018 The Masari developers.
Portions Copyright (c) ~2018 The Sumokoin developers.
Portions Copyright (c) ~2018 The Stellite developers.
Portions Copyright (c) 2014-2018 The Electronero Project.  
Portions Copyright (c) 2014-2018 The Electronero Pulse Project.  
Portions Copyright (c) 2014-2018 The Litenero Project.  
Portions Copyright (c) 2014-2018 The Goldnero Project.`

## Table of Contents

  - [Development resources](#development-resources)
  - [Vulnerability response](#vulnerability-response)
  - [Research](#research)
  - [Announcements](#announcement)
  - [Introduction](#introduction)
  - [About this project](#about-this-project)
  - [Supporting the project](#supporting-the-project)
  - [License](#license)
  - [Contributing](#contributing)
  - [Compiling Electronero from source](#compiling-electronero-from-source)
    - [Dependencies](#dependencies)

## Development resources

electronero ETNX - Web: [electronero.org](https://electronero.org)
electronero pulse ETNXP - Web: [electroneropulse.org](https://electroneropulse.org)
litenero LTNX - Web: [litenero.org](https://litenero.org)
goldnero GLDX - Web: [goldnero.org](https://goldnero.org)
crystaleum CRFI - Web: [crystaleum.org](https://crystaleum.org)
electronero unnoffical - Chat: [t.me/electronero](https://t.me/electronero)
electronero network - Chat: [t.me/electronero_network](https://t.me/electronero_network)
electronero pulse - Chat: [t.me/etnxp](https://t.me/etnxp)
litenero - Chat: [t.me/litenero](https://t.me/litenero)
goldnero - Chat: [t.me/goldnero](https://t.me/goldnero)
crystaleum - Chat: [t.me/crystaleum](https://t.me/crystaleum)
electronero core - Mail: [support@electronero.org](mailto:support@electronero.org)
electronero network - GitHub: [github.com/electronero/electronero](https://github.com/electronero/electronero)

## Vulnerability response

- Monero source [Vulnerability Response Process](https://github.com/monero-project/meta/blob/master/VULNERABILITY_RESPONSE_PROCESS.md) encourages responsible disclosure
- Monero is also available via [HackerOne](https://hackerone.com/monero)

## Announcements

You can subscribe to [electronero announcements](https://t.me/etnxnews) to get critical announcements from Electronero core. The announcement list can be very helpful for knowing when software updates are needed, etc. 

## Introduction

Electronero is a private, secure, untraceable, decentralised digital currency. You are your bank, you control your funds, and nobody can trace your transfers unless you allow them to do so.

**Privacy:** Electronero uses a cryptographically sound system to allow you to send and receive funds without your transactions being easily revealed on the blockchain (the ledger of transactions that everyone has). This ensures that your purchases, receipts, and all transfers remain absolutely private by default.

**Security:** Using the power of a distributed peer-to-peer consensus network, every transaction on the network is cryptographically secured. Individual wallets have a 25 word mnemonic seed that is only displayed once, and can be written down to backup the wallet. Wallet files are encrypted with a passphrase to ensure they are useless if stolen.

**Untraceability:** By taking advantage of ring signatures, a special property of a certain type of cryptography, Electronero is able to ensure that transactions are not only untraceable, but have an optional measure of ambiguity that ensures that transactions cannot easily be tied back to an individual user or computer.

## Smart Contracts

Electronero ships with a minimal Ethereum Virtual Machine implementation. Accounts can deploy bytecode and call simple contracts directly on-chain. Contract actions are submitted via standard transactions, RPC using the `/deploy_contract` and `/call_contract` endpoints, or from the command‑line wallet. In `electronero-wallet-cli` you may run `compile_contract <file.sol>` to compile Solidity source into `<file>.bin`, then `deploy_contract <file.bin>` to deploy the resulting bytecode. The daemon returns the address of the new contract. `call_contract <address> <file|method> [params...] [write]` invokes a deployed contract with hex‑encoded input. Append `write` to pay the per-byte call fee and modify state. Contract files must reside in the same directory as the wallet so the CLI can find them. The embedded EVM supports basic opcodes for experimentation and learning purposes. Recent updates added storage and memory operations (`SSTORE`, `SLOAD`, `MSTORE`, `MLOAD`), a generic `PUSH` handler, the equality check `EQ` (0x14) opcode, and the `REVERT` opcode for greater compatibility with Solidity 0.8.

Deploying a contract incurs a fee proportional to its bytecode size. The wallet calculates this automatically using a rate of 10 atomic units per byte.
When you run `deploy_contract` the CLI displays the byte count and fee split between the network and governance address and asks for confirmation before submitting. The wallet RPC method `/deploy_contract` mirrors this behaviour by sending the deployment transaction and registering the contract under your wallet address.
Calls that modify contract state require a fee as well. The wallet uses 5 atomic units per byte of call data for such write operations, while read-only calls remain free. Half of every EVM fee is forwarded to a governance address configured in `cryptonote_config.h`.

Every contract maintains its own balance tracked by the EVM. You can deposit coins with `deposit_contract <address> <amount>` or `call_contract <address> deposit:<amount> write`. Deposits send the amount to a deterministic wallet address derived from the contract so the funds remain spendable. The full per‑byte call fee is forwarded to the governance wallet so you pay the normal network fee plus the EVM fee. Transfers between contracts or to regular addresses automatically craft a transaction using `create_transactions_2` and validate a transaction proof. The built‑in `transfer:` text command is restricted to the contract's owner and uses `call_contract <address> transfer:<dest>:<amount> write`.
Sending coins directly to a contract address with the normal `transfer` command will perform the same deposit logic automatically.
### Interacting with a contract

A basic workflow compiles, deploys and invokes Solidity contracts using
`electronero-wallet-cli`. Below is a minimal counter contract followed by the
commands needed to operate it.

```solidity
pragma solidity ^0.8.0;

contract Counter {
    uint256 private value;

    function increment(uint256 v) public {
        value += v;
    }

    function read() public view returns (uint256) {
        return value;
    }
}
```

Compile the source in your wallet directory:

```bash
electronero-wallet-cli compile_contract Counter.sol
```

Deploy the resulting bytecode:

```bash
electronero-wallet-cli deploy_contract Counter.bin
```

The wallet prints the new contract address (for example `c1`). You can invoke
functions by name without preparing the ABI payload yourself. The following
command increments the counter by `5` and automatically encodes
`increment(uint256)`:

```bash
electronero-wallet-cli call_contract c1 increment 5 write
```

If you prefer manual control, encode function calls with any Ethereum tool such
as `solc --abi` or `ethers.js`. The call `increment(5)` yields the hexadecimal
payload `d09de08a0000000000000000000000000000000000000000000000000000000000000005`.
Save this string to a file named `inc.data` next to your wallet and invoke the
contract:

```bash
electronero-wallet-cli call_contract c1 inc.data write
```

Read the counter value by calling the `read()` function using its encoded data
stored in `read.data`:

```bash
electronero-wallet-cli call_contract c1 read.data
```

The CLI prints the returned integer. The same payload can be sent over RPC:

```json
{"jsonrpc":"2.0","id":"0","method":"call_contract","params":{"account":"c1","caller":"<your address>","data":"d09de08a0000000000000000000000000000000000000000000000000000000000000005","write":true}}
```

Use `electronero-wallet-cli encode_call increment 5` to print the same hex
payload when crafting custom RPC requests.
<<<<<<< viwzn1-codex/expose-smart-contract-functions-over-cli-and-rpc
Alternatively, call the RPC method `encode_call` with `{ "call": "increment(5)" }`
to receive the encoded payload for use with `call_contract`.
=======
>>>>>>> master

This request performs the same state-changing call through the wallet RPC
server.

Regular Solidity code works on the embedded EVM. Inline `assembly` is only required for direct access to custom opcodes.

To send coins from one contract directly to another in Solidity you may invoke
the EVM transfer opcode from inline assembly. This opcode takes the destination
address and amount from the stack and moves funds from the current contract to
that destination. A simple helper looks like:

```solidity
pragma solidity ^0.4.0;

contract Faucet {
    function payout(address dest, uint64 amount) public {
        assembly {
            // push destination then amount for the TRANSFER (0xa0) opcode
            let d := dest
            let a := amount
            // the host interprets 0xa0 as a transfer from this contract
            // no value is returned other than success (ignored here)
            mstore(0x0, d)
            mstore(0x20, a)
            pop(call(gas(), 0xa0, 0, 0x0, 0x40, 0, 0))
        }
    }
}
```

Calling `payout` moves the requested `amount` from the contract balance to the
`dest` contract.

Alternatively you can use Solidity's standard `call` mechanism to forward coins
from a contract to any address. The following helper checks the contract's
balance and sends the requested amount:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleTreasury {
    function transferCoins(address payable _to, uint256 _amount) public {
        require(address(this).balance >= _amount, "Insufficient ether balance in contract");
        (bool sent, ) = _to.call{value: _amount}("");
        require(sent, "Failed to send Coins");
    }
}
```

Two additional opcodes help contracts introspect their state. `ADDRESS` (0x30)
pushes the executing contract's numeric identifier onto the stack, while
`BALANCE` (0x31) accepts a contract id and pushes its balance. For example a
contract can check its own balance in assembly:

```solidity
contract BalanceCheck {
    function getBalance() public view returns (uint256) {
        assembly {
            // ADDRESS (0x30) leaves this contract's id on the stack
            0x30
            // BALANCE (0x31) consumes the id and pushes its balance
            0x31
            return(0, 32)
        }
    }
}
```

Block metadata is also exposed through `TIMESTAMP` (0x42) and `NUMBER` (0x43).
`TIMESTAMP` pushes the current block or RPC time in seconds and `NUMBER` pushes
the blockchain height. A contract can query these values in assembly:

```solidity
contract BlockInfo {
    function current() public view returns (uint256 ts, uint256 height) {
        assembly {
            0x42 // TIMESTAMP
            0x43 // NUMBER
            return(0, 64)
        }
    }
}
```

Contracts can be destroyed to reclaim their remaining balance. The EVM now
supports the `SELFDESTRUCT` (0xff) opcode which removes a contract and transfers
its funds to another contract address. In Solidity you may use the built-in
`selfdestruct` function:

```solidity
pragma solidity ^0.8.0;

contract OneShot {
    function burn(address payable to) public {
        selfdestruct(to);
    }
}
```

The `LOG` (0xa1) opcode lets a contract record numeric values in an internal
log array. These entries can be listed later:

```solidity
contract Notifier {
    function log(uint256 id) public {
        assembly {
            // PUSH1 <id> followed by LOG
            0x60
            id
            0xa1
        }
    }
}
```

Run `contract_logs <address>` or call `/get_contract_logs` to dump the stored
numbers.

The file you pass to `call_contract` must contain the ABI‑encoded function data in hexadecimal. Generate this using `solc --abi` along with the function signature and arguments or any Ethereum toolkit like `ethers.js`. Write the hex string without a `0x` prefix to a file next to the wallet, then reference that filename with `call_contract`.
Input data can be examined from assembly using `CALLDATASIZE` (0x36) and `CALLDATALOAD` (0x35). `CALLDATASIZE` returns the number of bytes supplied to the call while `CALLDATALOAD` reads up to eight bytes starting at a given offset:

```solidity
contract Args {
    function first() public pure returns (uint64) {
        assembly {
            0x60 0x00 0x35
            0xf3
        }
    }
}
```


To inspect a value stored by a contract, use `contract_storage <address> <key>`.
The key is a numeric index in the contract's storage map and the command returns
the associated integer value. The same information is available remotely via the
`/get_contract_storage` RPC method:

```bash
electronero-wallet-cli contract_storage c1 0
```

To find out who deployed a contract, use `contract_owner <address>`. This prints
the account that originally created it and can also be fetched remotely via the
`/get_contract_owner` RPC method:

```bash
electronero-wallet-cli contract_owner c1
```

Display a contract's bytecode using `contract_code <address>` or call the
`/get_contract_code` RPC method:

```bash
electronero-wallet-cli contract_code c1
```

Verify that a deployed contract matches its published source with `verify_contract <address> <file.sol>`:

```bash
electronero-wallet-cli verify_contract c1 MyContract.sol
```
The same validation is available remotely using the `/verify_contract` RPC endpoint.

List all deployed contract addresses with `contract_addresses` or call `/get_contract_addresses`:

```bash
electronero-wallet-cli contract_addresses
```

Show contracts owned by a specific account with `contracts_by_owner <address>` or via `/get_contracts_by_owner`:

```bash
electronero-wallet-cli contracts_by_owner etnk...
```

To display the contracts owned by your wallet use `my_contracts`:

```bash
electronero-wallet-cli my_contracts
```

Change a contract's owner with `transfer_owner <address> <new_owner>` or call `/transfer_contract_owner`:

```bash
electronero-wallet-cli transfer_owner c1 etnk...
```

Retrieve numeric events emitted by a contract with `contract_logs <address>` or by calling the `/get_contract_logs` RPC endpoint.
Additional Solidity contract examples can be found in [SOLIDITY.md](SOLIDITY.md).

## Bulk Transfers

The command‑line wallet can send payouts to many addresses at once using `bulk_transfer`. Create a text file in the wallet directory containing one destination per line:

```
etnk...address1 1.5
etnk...address2 0.75
etnk...address3 10
```

Blank lines and any line beginning with `#` or `;` are ignored. This allows
annotating payout files with comments or temporarily disabling entries.

Invoke `bulk_transfer payouts.txt` to construct a single transaction with all of the listed outputs. Each line must provide a valid Electronero address and amount separated by whitespace. `bulk_transfer` simply feeds these pairs into the regular transfer logic.

The same capability is available over the wallet RPC interface via the `bulk_transfer` method. Send a JSON RPC request like:

```json
{"jsonrpc":"2.0","id":"0","method":"bulk_transfer","params":{"filename":"payouts.txt"}}
```

The filename is resolved relative to the directory containing the wallet.

## Supporting the project

Electronero is a 100% community driven endeavor. To join community efforts, the easiest thing you can do is support the project financially. Electronero donations can be made to the Electronero donation address via the `donate` command (type `help` in the command-line wallet for details). Else, here are our dev teams addresses. The funding goes to many developers, and volunteers who contribute, they are grateful for our donations! 

The Monero donation address is: `85PTaJNpkEEeJao2MNk1sRWTQXLUf1FGjZew8oR8R4cRUrXxFrTexa9GwrjmJD4Pyx6UrjgMQnuMoFNmaBKqxs7PPXVe9oX`

The Bitcoin donation address is: `38jiBKevQHp8zhQpZ42bTvK4QpzzqWkA3K`

The Ethereum donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The Tether USD donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The ZCash donation address is: `t1Kmnv9eDqw7VyDWmzSUbjBPrxoY7hMuUCc` 

The Liquid donation address is: `VJL9H2mk4tKBRgSkTNkSrFGQABiNxUs1UPbm4rHCsE8vF87kSJgSo8AQfGDt54nC59tEtb2W47GsMrw2` 

The Electronero donation address is: `etnkHfFuanNeTe3q9dux4d9cRiLkUR4hDffvhfTp6nbhEJ5R8TY4vdyZjT4BtWxnvSJ5nfD64eCAQfKMJHSym2dj8PQqeiKmBM` 

The Electroneum donation address is: `etnkHfFuanNeTe3q9dux4d9cRiLkUR4hDffvhfTp6nbhEJ5R8TY4vdyZjT4BtWxnvSJ5nfD64eCAQfKMJHSym2dj8PQqeiKmBM` 

The Dogecoin donation address is: `DTTez7ggKPzDcKuUUTns8VzMrKesZUKMCk` 

The Litecoin donation address is: `MAtV7sbBnmuf2bxVUPgCprpmJ5xX6euBwe`

The Sumokoin donation address is: `Sumoo47CGenbHfZtpCVV4PRMSsXP38idFdt5JSj7VuJrD1nABoPHTBHgR6owQJfn1JU8BiWWohw4oiefGEjAn4GmbFYYtCcfPeT`

The Aave donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The Attention Token  donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The Cardano ADA donation address is: `DdzFFzCqrhspgQJTD1r81KsmXjzySdu4Zb4pJf7iLxkcVKvoRLoVHss9f2147QTRCRkQAFjWwHdr77Snn3efEo9ne4YzM5UCwwnMGR15` 

The Compound donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The Dash donation address is: `XcFVDo2k3XRJwQKQQRgMBfhCEDFANawQ3B` 

The Maker donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The Paxos Standard donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The REN donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The TrueUSD donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 

The USDCoin donation address is: `0x59d26980a1cdd75e1c3af516b912a6233aa2f5e4` 


## About this project

This is a modified core implementation of Monero/Electroneum. It is open source and completely free to use without restrictions, except for those specified in the license agreement below. There are no restrictions on anyone creating an alternative implementation of Monero that uses the protocol and network in a compatible manner.

As with many development projects, the repository on Github is considered to be the "staging" area for the latest changes. Before changes are merged into that branch on the main repository, they are tested by individual developers in their own branches, submitted as a pull request, and then subsequently tested by contributors who focus on testing and code reviews. That having been said, the repository should be carefully considered before using it in a production environment, unless there is a patch in the repository for a particular show-stopping issue you are experiencing. It is generally a better idea to use a tagged release for stability.

**Anyone is welcome to contribute to Electronero's codebase!** If you have a fix or code change, feel free to submit it as a pull request directly to the "master" branch. In cases where the change is relatively small or does not affect other parts of the codebase it may be merged in immediately by any one of the collaborators. On the other hand, if the change is particularly large or complex, it is expected that it will be discussed at length either well in advance of the pull request being submitted, or even directly on the pull request.

## License

See [LICENSE](LICENSE).

## Contributing

If you want to help out, join Electronero Network Core Contributors. <a href="https://t.me/electronero">Contact us on Telegram.</a></br>
See [CONTRIBUTING](CONTRIBUTING.md) for a set of guidelines.

## Scheduled software upgrades

Electronero utilizes a software upgrade (hard fork) mechanism to implement new features. This means that users of Electronero (end users and service providers) should run current versions and upgrade their software on a regular basis. The required software for these upgrades will be available prior to the scheduled date. Please check the repository prior to this date for the proper Electronero software version. 

## Release staging schedule and protocol

Approximately three months prior to a scheduled software upgrade, a branch from Master will be created with the new release version tag. Pull requests that address bugs should then be made to both Master and the new release branch. Pull requests that require extensive review and testing (generally, optimizations and new features) should *not* be made to the release branch. 

## Compiling Electronero from source

### Dependencies

The following table summarizes the tools and libraries required to build. A
few of the libraries are also included in this repository (marked as
"Vendored"). By default, the build uses the library installed on the system,
and ignores the vendored sources. However, if no library is found installed on
the system, then the vendored source will be built and used. The vendored
sources are also used for statically-linked builds because distribution
packages often include only shared library binaries (`.so`) but not static
library archives (`.a`).

| Dep          | Min. version  | Vendored | Debian/Ubuntu pkg  | Arch pkg     | Fedora            | Optional | Purpose        |
| ------------ | ------------- | -------- | ------------------ | ------------ | ----------------- | -------- | -------------- |
| GCC          | 4.7.3         | NO       | `build-essential`  | `base-devel` | `gcc`             | NO       |                |
| CMake        | 3.0.0         | NO       | `cmake`            | `cmake`      | `cmake`           | NO       |                |
| pkg-config   | any           | NO       | `pkg-config`       | `base-devel` | `pkgconf`         | NO       |                |
| Boost        | 1.58          | NO       | `libboost-all-dev` | `boost`      | `boost-devel`     | NO       | C++ libraries  |
| OpenSSL      | basically any | NO       | `libssl-dev`       | `openssl`    | `openssl-devel`   | NO       | sha256 sum     |
| libzmq       | 3.0.0         | NO       | `libzmq3-dev`      | `zeromq`     | `cppzmq-devel`    | NO       | ZeroMQ library |
| libunbound   | 1.4.16        | YES      | `libunbound-dev`   | `unbound`    | `unbound-devel`   | NO       | DNS resolver   |
| libsodium    | ?             | NO       | `libsodium-dev`    | ?            | `libsodium-devel` | NO       | libsodium      |
| libminiupnpc | 2.0           | YES      | `libminiupnpc-dev` | `miniupnpc`  | `miniupnpc-devel` | YES      | NAT punching   |
| libunwind    | any           | NO       | `libunwind-dev`   | `libunwind`  | `libunwind-devel` | YES      | Stack traces   |
| liblzma      | any           | NO       | `liblzma-dev`      | `xz`         | `xz-devel`        | YES      | For libunwind  |
| libreadline  | 6.3.0         | NO       | `libreadline-dev` | `readline`   | `readline-devel`  | YES      | Input editing  |
| ldns         | 1.6.17        | NO       | `libldns-dev`      | `ldns`       | `ldns-devel`      | YES      | SSL toolkit    |
| expat        | 1.1           | NO       | `libexpat1-dev`    | `expat`      | `expat-devel`     | YES      | XML parsing    |
| GTest        | 1.5           | YES      | `libgtest-dev`^    | `gtest`      | `gtest-devel`     | YES      | Test suite     |
| Doxygen      | any           | NO       | `doxygen`          | `doxygen`    | `doxygen`         | YES      | Documentation  |
| Graphviz     | any           | NO       | `graphviz`         | `graphviz`   | `graphviz`        | YES      | Documentation  |


[1] On Debian/Ubuntu `libgtest-dev` only includes sources and headers. You must
build the library binary manually. This can be done with the following command `sudo apt-get install libgtest-dev && cd /usr/src/gtest && sudo cmake . && sudo make`
Then:

* on Debian:
  `sudo mv libg* /usr/lib/`
* on Ubuntu:
  `sudo mv lib/libg* /usr/lib/`

[2] libnorm-dev is needed if your zmq library was built with libnorm, and not needed otherwise

Install all dependencies at once on Debian/Ubuntu (tested on 22.04):

``` sudo apt update && sudo apt install build-essential cmake pkg-config libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind-dev liblzma-dev libreadline-dev libldns-dev libexpat1-dev libpgm-dev qttools5-dev-tools libhidapi-dev libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev libboost-locale-dev libboost-program-options-dev libboost-regex-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev ccache doxygen graphviz ```

Install all dependencies at once on openSUSE:

``` sudo zypper ref && sudo zypper in cppzmq-devel  ldns-devel libboost_chrono-devel libboost_date_time-devel libboost_filesystem-devel libboost_locale-devel libboost_program_options-devel libboost_regex-devel libboost_serialization-devel libboost_system-devel libboost_thread-devel libexpat-devel libminiupnpc-devel libsodium-devel libunwind-devel unbound-devel  cmake doxygen ccache fdupes gcc-c++ libevent-devel libopenssl-devel pkgconf-pkg-config readline-devel  xz-devel libqt5-qttools-devel patterns-devel-C-C++-devel_C_C++```

Install all dependencies at once on macOS with the provided Brewfile:
``` brew update && brew bundle --file=contrib/brew/Brewfile ```

FreeBSD 12.1 one-liner required to build dependencies:
```pkg install git gmake cmake pkgconf boost-libs libzmq4 libsodium```

### Cloning the repository

Clone recursively to pull-in needed submodule(s):

`$ git clone --recursive https://github.com/electronero/electronero`

If you already have a repo cloned, initialize and update:

`$ cd electronero && git submodule init && git submodule update && cd coins/electronero && git submodule init && git submodule update && make -j2 && cd ../electroneropulse && git submodule init && git submodule update && make -j2 && cd ../litenero && git submodule init && git submodule update && make -j2 && cd ../goldnero && git submodule init && git submodule update && make -j2 && cd ../crystaleum && git submodule init && git submodule update && make -j2`

*Note*: If there are submodule differences between branches, you may need 
to use ```git submodule sync && git submodule update``` after changing branches
to build successfully.

### Build instructions

Electronero uses the CMake build system and a top-level [Makefile](Makefile) that
invokes cmake commands as needed.

#### On Linux and OS X

* Install the dependencies
* Change to the root of the source code directory and build:

        `$ cd electronero && git submodule init && git submodule update && cd coins/electronero && git submodule init && git submodule update && make -j2 && cd ../electroneropulse && git submodule init && git submodule update && make -j2 && cd ../litenero && git submodule init && git submodule update && make -j2 && cd ../goldnero && git submodule init && git submodule update && make -j2 && cd ../crystaleum && git submodule init && git submodule update && make -j2`

    *Optional*: If your machine has several cores and enough memory, enable
    parallel build by running `make -j<number of threads>` instead of `make`. For
    this to be worthwhile, the machine should have one core and about 2GB of RAM
    available per thread.

    *Note*: If cmake can not find zmq.hpp file on OS X, installing `zmq.hpp` from
    https://github.com/zeromq/cppzmq to `/usr/local/include` should fix that error.

* The resulting Electronero Network executables can be found in `build/release/bin` for each Electronero Network coin in `coins/` dir

* Add `PATH="$PATH:$HOME/electronero/build/release/bin"` to `.profile`
* Add `PATH="$PATH:$HOME/electroneropulse/build/release/bin"` to `.profile`
* Add `PATH="$PATH:$HOME/litenero/build/release/bin"` to `.profile`
* Add `PATH="$PATH:$HOME/goldnero/build/release/bin"` to `.profile`
* Add `PATH="$PATH:$HOME/crystaleum/build/release/bin"` to `.profile`

* Run Electronero `electronerod`
* Run Electronero Pulse `pulsed`
* Run Litenero `litenerod`
* Run Goldnero `goldnerod`
* Run Crystaleum `crystaleumd`

* **Optional**: build and run the test suite to verify the binaries:

        make release-test

    *NOTE*: `core_tests` test may take a few hours to complete.

* **Optional**: to build binaries suitable for debugging:

         make debug

* **Optional**: to build statically-linked binaries:

         make release-static

Dependencies need to be built with -fPIC. Static libraries usually aren't, so you may have to build them yourself with -fPIC. Refer to their documentation for how to build them.

* **Optional**: build documentation in `doc/html` (omit `HAVE_DOT=YES` if `graphviz` is not installed):

        HAVE_DOT=YES doxygen Doxyfile

#### On the Raspberry Pi

Tested on a Raspberry Pi Zero with a clean install of minimal Raspbian Stretch (2017-09-07 or later) from https://www.raspberrypi.org/downloads/raspbian/. If you are using Raspian Jessie, [please see note in the following section](#note-for-raspbian-jessie-users).

* `apt-get update && apt-get upgrade` to install all of the latest software

* Install the dependencies for Electronero from the 'Debian' column in the table above.

* Increase the system swap size:
```
	sudo /etc/init.d/dphys-swapfile stop  
	sudo nano /etc/dphys-swapfile  
	CONF_SWAPSIZE=1024  
	sudo /etc/init.d/dphys-swapfile start  
```
* Clone electronero and checkout most recent release version:
```
        git clone https://github.com/electronero/electronero.git
```
* Build:
`$ cd electronero && git submodule init && git submodule update && cd coins/electronero && git submodule init && git submodule update && make -j2 && cd ../electroneropulse && git submodule init && git submodule update && make -j2 && cd ../litenero && git submodule init && git submodule update && make -j2 && cd ../goldnero && git submodule init && git submodule update && make -j2`

* Add `PATH="$PATH:$HOME/electronero/build/release/bin"` to `.profile`

* You may wish to reduce the size of the swap file after the build has finished, and delete the boost directory from your home directory

#### *Note for Raspbian Jessie users:*

If you are using the older Raspbian Jessie image, compiling Electronero is a bit more complicated. The version of Boost available in the Debian Jessie repositories is too old to use with Electronero, and thus you must compile a newer version yourself. The following explains the extra steps, and has been tested on a Raspberry Pi 2 with a clean install of minimal Raspbian Jessie.

* As before, `apt-get update && apt-get upgrade` to install all of the latest software, and increase the system swap size

```
	sudo /etc/init.d/dphys-swapfile stop  
	sudo nano /etc/dphys-swapfile  
	CONF_SWAPSIZE=1024  
	sudo /etc/init.d/dphys-swapfile start  
```

* Then, install the dependencies for Electronero except `libunwind` and `libboost-all-dev`

* Install the latest version of boost (this may first require invoking `apt-get remove --purge libboost*` to remove a previous version if you're not using a clean install):
```
	cd  
	wget https://sourceforge.net/projects/boost/files/boost/1.64.0/boost_1_64_0.tar.bz2  
	tar xvfo boost_1_64_0.tar.bz2  
	cd boost_1_64_0  
	./bootstrap.sh  
	sudo ./b2  
```
```
	sudo ./bjam install
```

* From here, follow the [general Raspberry Pi instructions](#on-the-raspberry-pi) from the "Clone Electronero and checkout most recent release version" step.

#### On Windows:

Binaries for Windows are built on Windows using the MinGW toolchain within
[MSYS2 environment](http://msys2.github.io). The MSYS2 environment emulates a
POSIX system. The toolchain runs within the environment and *cross-compiles*
binaries that can run outside of the environment as a regular Windows
application.

**Preparing the build environment**

* Download and install the [MSYS2 installer](http://msys2.github.io), either the 64-bit or the 32-bit package, depending on your system.
* Open the MSYS shell via the `MSYS2 Shell` shortcut
* Update packages using pacman:  

        pacman -Syuu  

* Exit the MSYS shell using Alt+F4  
* Edit the properties for the `MSYS2 Shell` shortcut changing "msys2_shell.bat" to "msys2_shell.cmd -mingw64" for 64-bit builds or "msys2_shell.cmd -mingw32" for 32-bit builds
* Restart MSYS shell via modified shortcut and update packages again using pacman:  

        pacman -Syuu  


* Install dependencies:

    To build for 64-bit Windows:

        pacman -S mingw-w64-x86_64-toolchain make mingw-w64-x86_64-cmake mingw-w64-x86_64-boost mingw-w64-x86_64-openssl mingw-w64-x86_64-zeromq mingw-w64-x86_64-libsodium

    To build for 32-bit Windows:

        pacman -S mingw-w64-i686-toolchain make mingw-w64-i686-cmake mingw-w64-i686-boost mingw-w64-i686-openssl mingw-w64-i686-zeromq mingw-w64-i686-libsodium

* Open the MingW shell via `MinGW-w64-Win64 Shell` shortcut on 64-bit Windows
  or `MinGW-w64-Win64 Shell` shortcut on 32-bit Windows. Note that if you are
  running 64-bit Windows, you will have both 64-bit and 32-bit MinGW shells.

**Building**

* If you are on a 64-bit system, run:

        make release-static-win64

* If you are on a 32-bit system, run:

        make release-static-win32

* The resulting executables can be found in `build/release/bin`

### On OpenBSD:

#### OpenBSD < 6.2

This has been tested on OpenBSD 5.8.

You will need to add a few packages to your system. `pkg_add db cmake gcc gcc-libs g++ miniupnpc gtest`.

The doxygen and graphviz packages are optional and require the xbase set.

The Boost package has a bug that will prevent librpc.a from building correctly. In order to fix this, you will have to Build boost yourself from scratch. Follow the directions here (under "Building Boost"):
https://github.com/bitcoin/bitcoin/blob/master/doc/build-openbsd.md

You will have to add the serialization, date_time, and regex modules to Boost when building as they are needed by Electronero.

To build: `env CC=egcc CXX=eg++ CPP=ecpp DEVELOPER_LOCAL_TOOLS=1 BOOST_ROOT=/path/to/the/boost/you/built make release-static-64`

#### OpenBSD >= 6.2

You will need to add a few packages to your system. `pkg_add cmake miniupnpc zeromq libiconv`.

The doxygen and graphviz packages are optional and require the xbase set.


Build the Boost library using clang. This guide is derived from: https://github.com/bitcoin/bitcoin/blob/master/doc/build-openbsd.md

We assume you are compiling with a non-root user and you have `doas` enabled.

Note: do not use the boost package provided by OpenBSD, as we are installing boost to `/usr/local`.

```
# Create boost building directory
mkdir ~/boost
cd ~/boost

# Fetch boost source
ftp -o boost_1_64_0.tar.bz2 https://netcologne.dl.sourceforge.net/project/boost/boost/1.64.0/boost_1_64_0.tar.bz2

# MUST output: (SHA256) boost_1_64_0.tar.bz2: OK
echo "7bcc5caace97baa948931d712ea5f37038dbb1c5d89b43ad4def4ed7cb683332 boost_1_64_0.tar.bz2" | sha256 -c
tar xfj boost_1_64_0.tar.bz2

# Fetch and apply boost patches, required for OpenBSD
ftp -o boost_test_impl_execution_monitor_ipp.patch https://raw.githubusercontent.com/openbsd/ports/bee9e6df517077a7269ff0dfd57995f5c6a10379/devel/boost/patches/patch-boost_test_impl_execution_monitor_ipp
ftp -o boost_config_platform_bsd_hpp.patch https://raw.githubusercontent.com/openbsd/ports/90658284fb786f5a60dd9d6e8d14500c167bdaa0/devel/boost/patches/patch-boost_config_platform_bsd_hpp

# MUST output: (SHA256) boost_config_platform_bsd_hpp.patch: OK
echo "1f5e59d1154f16ee1e0cc169395f30d5e7d22a5bd9f86358f738b0ccaea5e51d boost_config_platform_bsd_hpp.patch" | sha256 -c
# MUST output: (SHA256) boost_test_impl_execution_monitor_ipp.patch: OK
echo "30cec182a1437d40c3e0bd9a866ab5ddc1400a56185b7e671bb3782634ed0206 boost_test_impl_execution_monitor_ipp.patch" | sha256 -c

cd boost_1_64_0
patch -p0 < ../boost_test_impl_execution_monitor_ipp.patch
patch -p0 < ../boost_config_platform_bsd_hpp.patch

# Start building boost
echo 'using clang : : c++ : <cxxflags>"-fvisibility=hidden -fPIC" <linkflags>"" <archiver>"ar" <striper>"strip"  <ranlib>"ranlib" <rc>"" : ;' > user-config.jam
./bootstrap.sh --without-icu --with-libraries=chrono,filesystem,program_options,system,thread,test,date_time,regex,serialization,locale --with-toolset=clang
./b2 toolset=clang cxxflags="-stdlib=libc++" linkflags="-stdlib=libc++" -sICONV_PATH=/usr/local
doas ./b2 -d0 runtime-link=shared threadapi=pthread threading=multi link=static variant=release --layout=tagged --build-type=complete --user-config=user-config.jam -sNO_BZIP2=1 -sICONV_PATH=/usr/local --prefix=/usr/local install
```

Build cppzmq

Build the cppzmq bindings.

We assume you are compiling with a non-root user and you have `doas` enabled.

```
# Create cppzmq building directory
mkdir ~/cppzmq
cd ~/cppzmq

# Fetch cppzmq source
ftp -o cppzmq-4.2.3.tar.gz https://github.com/zeromq/cppzmq/archive/v4.2.3.tar.gz

# MUST output: (SHA256) cppzmq-4.2.3.tar.gz: OK
echo "3e6b57bf49115f4ae893b1ff7848ead7267013087dc7be1ab27636a97144d373 cppzmq-4.2.3.tar.gz" | sha256 -c
tar xfz cppzmq-4.2.3.tar.gz

# Start building cppzmq
cd cppzmq-4.2.3
mkdir build
cd build
cmake ..
doas make install
```

Build electronero: `env DEVELOPER_LOCAL_TOOLS=1 BOOST_ROOT=/usr/local make release-static`

### On Solaris:

The default Solaris linker can't be used, you have to install GNU ld, then run cmake manually with the path to your copy of GNU ld:

        mkdir -p build/release
        cd build/release
        cmake -DCMAKE_LINKER=/path/to/ld -D CMAKE_BUILD_TYPE=Release ../..
        cd ../..

Then you can run make as usual.

### On Linux for Android (using docker):

        # Build image (select android64.Dockerfile for aarch64)
        cd utils/build_scripts/ && docker build -f android32.Dockerfile -t electronero-android .
        # Create container
        docker create -it --name electronero-android electronero-android bash
        # Get binaries
        docker cp electronero-android:/opt/android/electronero/build/release/bin .

### Building portable statically linked binaries

By default, in either dynamically or statically linked builds, binaries target the specific host processor on which the build happens and are not portable to other processors. Portable binaries can be built using the following targets:

* ```make release-static-linux-x86_64``` builds binaries on Linux on x86_64 portable across POSIX systems on x86_64 processors
* ```make release-static-linux-i686``` builds binaries on Linux on x86_64 or i686 portable across POSIX systems on i686 processors
* ```make release-static-linux-armv8``` builds binaries on Linux portable across POSIX systems on armv8 processors
* ```make release-static-linux-armv7``` builds binaries on Linux portable across POSIX systems on armv7 processors
* ```make release-static-linux-armv6``` builds binaries on Linux portable across POSIX systems on armv6 processors
* ```make release-static-win64``` builds binaries on 64-bit Windows portable across 64-bit Windows systems
* ```make release-static-win32``` builds binaries on 64-bit or 32-bit Windows portable across 32-bit Windows systems

## Running electronerod

The build places the binary in `bin/` sub-directory within the build directory
from which cmake was invoked (repository root by default). To run in
foreground:

    ./bin/electronero

To list all available options, run `./bin/electronerod --help`.  Options can be
specified either on the command line or in a configuration file passed by the
`--config-file` argument.  To specify an option in the configuration file, add
a line with the syntax `argumentname=value`, where `argumentname` is the name
of the argument without the leading dashes, for example `log-level=1`.

To run in background:

    ./bin/electronerod --log-file electronerod.log

To run as a systemd service, copy
[electronerod.service](utils/systemd/electronerod.service) to `/etc/systemd/system/` and
[electronerod.conf](utils/conf/electronerod.conf) to `/etc/`. The [example
service](utils/systemd/electronerod.service) assumes that the user `electronero` exists
and its home is the data directory specified in the [example
config](utils/conf/electronerod.conf).

If you're on Mac, you may need to add the `--max-concurrency 1` option to
electronero-wallet-cli, and possibly electronerod, if you get crashes refreshing.

When restoring a wallet from private keys or a mnemonic seed, provide the
`--restore-height <block>` option to `electronero-wallet-cli` (or set the height
when prompted). Starting from a recent block dramatically reduces the scanning
time. After the wallet is created you can run `set refresh-type no-coinbase` to
skip miner transactions for even faster synchronization.
