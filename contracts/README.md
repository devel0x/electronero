# Token Marketplace

This directory contains a sample Solidity smart contract implementing a simple
limit-order token marketplace. Users can list tokens for sale in exchange for
another ERC‑20 token (referred to as `coin` in the contract). Orders are held by
the contract until they are filled or cancelled.

## Key Features

- **Sell orders**: Sellers deposit tokens and specify a price per token.
- **Buy orders**: Buyers purchase any portion of an open sell order by paying the
  required amount of `coin` tokens. Tokens are transferred to the buyer after
  payment.
- **Order cancellation**: Sellers may cancel their orders and retrieve any
  remaining tokens that have not been sold.
- **Query helpers**: Functions to list trading pairs and open orders for a pair.

The contract does not depend on external libraries and is provided purely as an
example implementation.
