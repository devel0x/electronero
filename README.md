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

Token subsystem
---------------

The optional token module allows wallets to create and transfer custom tokens identified by a 54‑character hex string ending in `tok`.

Recent additions improve robustness:

* **Persistent ledger** – token balances and history are stored on disk using LevelDB so that restarts keep token state.
* **On‑chain records** – each token operation is embedded in an `OP_RETURN` transaction, enabling miners to include the data in blocks.
* **Event logging** – operations are written to the debug log for wallet UIs or other processes to monitor.
* **Dynamic fees** – governance fees are charged per‑byte at a configurable rate and paid to a chosen wallet.
* **ERC‑20 style upgrades** – tokens now carry metadata including name, symbol and decimals, and a mint operation is available.
