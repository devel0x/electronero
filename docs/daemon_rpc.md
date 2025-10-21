# Electronero Daemon RPC

The daemon (`electronerod`) offers a JSON-RPC interface for interacting with the blockchain network. Clients can query data or submit transactions programmatically.

## Example

```javascript
const ElectroneroRPC = require('../modules/NodeJs/electronero');
const rpc = new ElectroneroRPC();

rpc.getInfo().then(info => console.log(info.height));
```

## Available Methods

The daemon RPC exposes the following commands:

- flush_txpool
- get_alternate_chains
- get_bans
- get_block
- get_block_count
- get_block_header_by_hash
- get_block_header_by_height
- get_block_headers_range
- get_block_template
- get_coinbase_tx_sum
- get_connections
- get_fee_estimate
- get_info
- get_last_block_header
- get_output_distribution
- get_output_histogram
- get_txpool_backlog
- get_version
- getblock
- getblockcount
- getblockheaderbyhash
- getblockheaderbyheight
- getblockheadersrange
- getblocktemplate
- getlastblockheader
- hard_fork_info
- on_get_block_hash
- on_getblockhash
- relay_tx
- rescan_token_tx
- set_bans
- submit_block
- submitblock
- sync_info
- /get_alt_blocks_hashes
- /get_height
- /get_info
- /get_limit
- /get_outs
- /get_transaction_pool
- /get_transaction_pool_hashes.bin
- /get_transaction_pool_stats
- /get_transactions
- /getheight
- /getinfo
- /gettransactions
- /is_key_image_spent
- /send_raw_transaction
- /sendrawtransaction
- /get_peer_list
- /in_peers
- /mining_status
- /out_peers
- /save_bc
- /set_limit
- /set_log_categories
- /set_log_hash_rate
- /set_log_level
- /start_mining
- /start_save_graph
- /stop_daemon
- /stop_mining
- /stop_save_graph
- /update

