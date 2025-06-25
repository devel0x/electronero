# PHP Module for Electronero RPC

This module contains the `ElectroneroRPC` class for interacting with both wallet and daemon RPC interfaces. PHP with the cURL extension is required.

## Usage

```php
require 'modules/PHP/electronero.php';

$rpc = new ElectroneroRPC();

// direct wallet RPC call
$balance = $rpc->get_balance(['account_index' => 0]);

// direct daemon RPC call
$info = $rpc->get_info();
```

By default the wallet RPC endpoint is `http://127.0.0.1:11212/json_rpc` and the daemon RPC endpoint is `http://127.0.0.1:26969/json_rpc`. Custom endpoints can be supplied to the constructor:

```php
$rpc = new ElectroneroRPC('http://wallet:11212/json_rpc', 'http://daemon:26969/json_rpc');
```

Every RPC method can be invoked directly on the `$rpc` instance. Unknown method names will throw a `BadMethodCallException`.

The helper methods `wallet()` and `daemon()` are still available for manual calls:

```php
$result = $rpc->wallet('transfer', ['destinations' => [/*...*/]]);
$info   = $rpc->daemon('get_info');
```

## Wallet RPC methods
- get_balance
- get_address
- getbalance
- getaddress
- create_address
- label_address
- get_accounts
- create_account
- label_account
- get_account_tags
- tag_accounts
- untag_accounts
- set_account_tag_description
- get_height
- getheight
- transfer
- transfer_split
- sweep_dust
- sweep_unmixable
- sweep_all
- sweep_single
- relay_tx
- store
- get_payments
- get_bulk_payments
- incoming_transfers
- query_key
- make_integrated_address
- split_integrated_address
- stop_wallet
- rescan_blockchain
- set_tx_notes
- get_tx_notes
- set_attribute
- get_attribute
- get_tx_key
- check_tx_key
- get_tx_proof
- check_tx_proof
- get_spend_proof
- check_spend_proof
- get_reserve_proof
- check_reserve_proof
- get_transfers
- get_transfer_by_txid
- sign
- verify
- export_key_images
- import_key_images
- make_uri
- parse_uri
- get_address_book
- add_address_book
- delete_address_book
- rescan_spent
- rescan_token_tx
- start_mining
- stop_mining
- get_languages
- create_wallet
- open_wallet
- is_multisig
- prepare_multisig
- make_multisig
- export_multisig_info
- import_multisig_info
- finalize_multisig
- sign_multisig
- submit_multisig
- token_create
- token_balance
- token_transfer
- token_approve
- token_transfer_from
- token_burn
- token_mint
- token_info
- all_tokens
- tokens_deployed
- my_tokens
- token_history
- token_history_addr
- token_set_fee

## Daemon RPC methods
- get_alt_blocks_hashes
- get_block
- get_block_count
- get_block_header_by_hash
- get_block_header_by_height
- get_block_headers_range
- get_block_template
- get_blocks.bin
- get_blocks_by_height.bin
- get_fee_estimate
- get_hashes.bin
- get_height
- get_info
- get_last_block_header
- get_limit
- get_o_indexes.bin
- get_output_distribution
- get_output_histogram
- get_outs
- get_outs.bin
- get_peer_list
- get_random_outs.bin
- get_random_rctouts.bin
- get_transaction_pool
- get_transaction_pool_hashes.bin
- get_transaction_pool_stats
- get_transactions
- get_txpool_backlog
- get_version
- getblock
- getblockcount
- getblockheaderbyhash
- getblockheaderbyheight
- getblockheadersrange
- getblocks.bin
- getblocks_by_height.bin
- getblocktemplate
- gethashes.bin
- getheight
- getinfo
- getlastblockheader
- getrandom_outs.bin
- getrandom_rctouts.bin
- gettransactions
- hard_fork_info
- in_peers
- is_key_image_spent
- mining_status
- on_get_block_hash
- on_getblockhash
- out_peers
- save_bc
- send_raw_transaction
- sendrawtransaction
- set_limit
- set_log_categories
- set_log_hash_rate
- set_log_level
- start_mining
- start_save_graph
- stop_daemon
- stop_mining
- stop_save_graph
- submit_block
- submitblock
- update
