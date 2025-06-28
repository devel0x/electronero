# Token Utilities

This directory contains the lightweight token implementation used by the Electronero wallet.
Tokens are stored in `tokens.bin` and synchronized across peers. See the main
project README for the list of available RPC commands.

## Token Marketplace Example

`token_marketplace` provides a simple limit-order marketplace using the token
store. Sellers deposit tokens into the marketplace and list a price in coins.
Buyers purchase tokens directly from these orders and the marketplace transfers
the tokens after each successful trade.

Marketplace data is persisted to `marketplace.bin` so orders survive restarts.
Operations can be encoded in transaction extra fields allowing peers to
synchronize order activity once transactions are confirmed on chain.
