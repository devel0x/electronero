# Electronero Wallet RPC

Electronero exposes a JSON-RPC service that allows programs to control a running wallet. The helper libraries in this repository make it easy to interact with the service from Node.js, PHP, Go and Python.

## Example

```javascript
const ElectroneroRPC = require('../modules/NodeJs/electronero');
const rpc = new ElectroneroRPC();

rpc.getBalance().then(bal => console.log(bal));
```

## Available Methods

The wallet RPC supports many commands. Below is a list generated from the source code:

- add_address_book
- all_tokens
- check_reserve_proof
- check_spend_proof
- check_tx_key
- check_tx_proof
- create_account
- create_address
- create_wallet
- delete_address_book
- export_key_images
- export_multisig_info
- finalize_multisig
- get_account_tags
- get_accounts
- get_address
- get_address_book
- get_attribute
- get_balance
- get_bulk_payments
- get_height
- get_languages
- get_payments
- get_reserve_proof
- get_spend_proof
- get_transfer_by_txid
- get_transfers
- get_tx_key
- get_tx_notes
- get_tx_proof
- getaddress
- getbalance
- getheight
- import_key_images
- import_multisig_info
- incoming_transfers
- is_multisig
- label_account
- label_address
- make_integrated_address
- make_multisig
- make_uri
- my_tokens
- open_wallet
- parse_uri
- prepare_multisig
- query_key
- relay_tx
- rescan_blockchain
- rescan_spent
- rescan_token_tx
- set_account_tag_description
- set_attribute
- set_tx_notes
- sign
- sign_multisig
- split_integrated_address
- start_mining
- stop_mining
- stop_wallet
- store
- submit_multisig
- sweep_all
- sweep_dust
- sweep_single
- sweep_unmixable
- tag_accounts
- token_approve
- token_balance
- token_burn
- token_create
- token_history
- token_history_addr
- token_info
- token_mint
- token_set_fee
- token_transfer
- token_transfer_from
- transfer
- transfer_split
- untag_accounts
- verify

