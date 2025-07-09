Interchained Core integration/staging tree
=====================================

https://interchainedcore.org

What is Interchained?
----------------

Interchained is an experimental digital currency that enables instant payments to
anyone, anywhere in the world. Interchained uses peer-to-peer technology to operate
with no central authority: managing transactions and issuing money are carried
out collectively by the network. Interchained Core is the name of open source
software which enables the use of this currency.

For more information, as well as an immediately usable, binary version of
the Interchained Core software, see https://interchainedcore.org/en/download/, or read the
[original whitepaper](https://interchainedcore.org/interchained.pdf).

License
-------

Interchained Core is released under the terms of the MIT license. See [COPYING](COPYING) for more
information or see https://opensource.org/licenses/MIT.

Development Process
-------------------

The `master` branch is regularly built (see `doc/build-*.md` for instructions) and tested, but it is not guaranteed to be
completely stable. [Tags](https://github.com/interchained/interchained/tags) are created
regularly from release branches to indicate new official, stable release versions of Interchained Core.

The https://github.com/interchained-core/gui repository is used exclusively for the
development of the GUI. Its master branch is identical in all monotree
repositories. Release branches and tags do not exist, so please do not fork
that repository unless it is for development reasons.


The contribution workflow is described in [CONTRIBUTING.md](CONTRIBUTING.md)
and useful hints for developers can be found in [doc/developer-notes.md](doc/developer-notes.md).

New Feature
-----------

Interchained Core now exposes a `getbestheaderhash` RPC call to retrieve the
hash of the tip of the best known header chain. This will match the
`getbestblockhash` result during normal operation, but can differ while the
node is still validating blocks.

The wallet introduces a `burn` RPC for destroying coins by sending them to a
provably unspendable address.

Transactions can now carry short notes via the `sendwithmemo` RPC, which
attaches the provided text to an OP_RETURN output.

Support for an embedded Ethereum Virtual Machine (EVM) relies on the external
`evmone` project. The repository no longer ships the submodule by default. To
build with EVM support, add the dependency after cloning:

```
git submodule add https://github.com/ethereum/evmone.git evmone
git submodule update --init
```

Wallets can lock coins for transfer to the Ethereum sidechain using the
`bridgefunds` RPC. Coins are sent to a special bridge address and the
destination Ethereum address is included in an OP_RETURN output. The example
script `contrib/bridge/bridge_watcher.py` demonstrates how to automate
sidechain credits by watching for these deposits and submitting matching
transactions on chain B.
The companion script `contrib/bridge/return_watcher.py` listens for burn events
on the Ethereum sidechain. When users lock or destroy their sidechain tokens, it
releases the original coins on chain A by calling the wallet RPC.

### Using the embedded EVM

With the `evmone` submodule initialized, Interchained exposes RPC calls for
deploying and interacting with Ethereum-style contracts.

1. **Import a key**

   Load an Ethereum account so the node can sign transactions:

   ```
   importethkey 0x0123456789abcdef...
   ```

   The command returns the address associated with the private key.

2. **Deploy a contract**

   Compile your Solidity code and submit the bytecode using `evmdeploy`:

   ```
   evmdeploy <address> 0x60806040...
   ```

   The RPC broadcasts the transaction and replies with the new contract address
   once mined.

3. **Call a contract**

   Invoke a method via `evmcall` by supplying ABI-encoded data:

   ```
   evmcall <address> <contract> 0xa9059cbb000000000000000000000000...
   ```

   The call executes inside the embedded EVM and returns the result as hex.

These RPCs wrap the `evmone` interpreter so simple smart contract workflows can
run directly from Interchained without relying on external chains.

Mining defaults were improved: `setgenerate` now uses all CPU cores when
`genproclimit` is set to 0 or a negative value, and the miner periodically
logs total hashrate across threads. Block timestamps are updated less
frequently during hashing to cut overhead and boost hashrate. Difficulty
retargeting now uses a 12‑block window and the yespower PoW limit was
eased so blocks can be found roughly every 30 seconds.
The yespower algorithm now switches to a smaller N=512 parameter at block
2500, reducing memory usage and speeding up hashing after the fork.

Testing
-------

Testing and code review is the bottleneck for development; we get more pull
requests than we can review and test on short notice. Please be patient and help out by testing
other people's pull requests, and remember this is a security-critical project where any mistake might cost people
lots of money.

### Automated Testing

Developers are strongly encouraged to write [unit tests](src/test/README.md) for new code, and to
submit new unit tests for old code. Unit tests can be compiled and run
(assuming they weren't disabled in configure) with: `make check`. Further details on running
and extending unit tests can be found in [/src/test/README.md](/src/test/README.md).

There are also [regression and integration tests](/test), written
in Python, that are run automatically on the build server.
These tests can be run (if the [test dependencies](/test) are installed) with: `test/functional/test_runner.py`

The Travis CI system makes sure that every pull request is built for Windows, Linux, and macOS, and that unit/sanity tests are run automatically.

### Manual Quality Assurance (QA) Testing

Changes should be tested by somebody other than the developer who wrote the
code. This is especially important for large or high-risk changes. It is useful
to add a test plan to the pull request description if testing the changes is
not straightforward.

Translations
------------

Changes to translations as well as new translations can be submitted to
[Interchained Core's Transifex page](https://www.transifex.com/interchained/interchained/).

Translations are periodically pulled from Transifex and merged into the git repository. See the
[translation process](doc/translation_process.md) for details on how this works.

**Important**: We do not accept translation changes as GitHub pull requests because the next
pull from Transifex would automatically overwrite them again.

Translators should also subscribe to the [mailing list](https://groups.google.com/forum/#!forum/interchained-translators).
