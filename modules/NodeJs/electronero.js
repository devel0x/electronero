'use strict';

/**
 * ElectroneroRPC provides helper methods to access wallet and daemon RPC APIs.
 * Both RPC servers use the standard JSON-RPC 2.0 protocol over HTTP.
 */
class ElectroneroRPC {
  /**
   * Create a new RPC helper.
   *
   * @param {Object} [options]
   * @param {string} [options.daemonRpcUrl]  URL of the daemon rpc endpoint
   * @param {string} [options.walletRpcUrl]  URL of the wallet rpc endpoint
   * @param {string} [options.username]      HTTP basic auth username
   * @param {string} [options.password]      HTTP basic auth password
   */
  constructor(options = {}) {
    this.daemonRpcUrl = options.daemonRpcUrl || 'http://127.0.0.1:26968/json_rpc';
    this.walletRpcUrl = options.walletRpcUrl || 'http://127.0.0.1:26969/json_rpc';
    this.username = options.username;
    this.password = options.password;
    this.daemonBaseUrl = this.daemonRpcUrl.replace(/\/json_rpc$/, '');
  }

  /**
   * Internal method to issue a JSON RPC request.
   * @private
   */
  async _jsonRequest(url, method, params = {}, id = Date.now()) {
    const headers = { 'Content-Type': 'application/json' };
    if (this.username || this.password) {
      const auth = Buffer.from(`${this.username || ''}:${this.password || ''}`).toString('base64');
      headers['Authorization'] = `Basic ${auth}`;
    }
    const body = JSON.stringify({ jsonrpc: '2.0', id, method, params });
    const response = await fetch(url, { method: 'POST', headers, body });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    const data = await response.json();
    if (data.error) {
      const { code, message } = data.error;
      throw new Error(`RPC error ${code}: ${message}`);
    }
    return data.result;
  }

  /**
   * Internal helper for plain HTTP RPC endpoints.
   * @private
   */
  async _httpRequest(url, params = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (this.username || this.password) {
      const auth = Buffer.from(`${this.username || ''}:${this.password || ''}`).toString('base64');
      headers['Authorization'] = `Basic ${auth}`;
    }
    const body = JSON.stringify(params);
    const response = await fetch(url, { method: 'POST', headers, body });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Call a wallet RPC method.
   * @param {string} method RPC method name
   * @param {Object} [params] Parameters to send
   * @returns {Promise<Object>} RPC result
   */
  async wallet(method, params = {}) {
    return this._jsonRequest(this.walletRpcUrl, method, params);
  }

  /**
   * Call a daemon RPC method.
   * @param {string} method RPC method name
   * @param {Object} [params] Parameters to send
   * @returns {Promise<Object>} RPC result
   */
  async daemon(method, params = {}) {
    if (method.startsWith('/')) {
      const url = this.daemonBaseUrl + method;
      return this._httpRequest(url, params);
    }
    return this._jsonRequest(this.daemonRpcUrl, method, params);
  }

}

function camel(str) {
  return str
    .replace(/^\//, '')
    .split(/[._\/-]/)
    .map((s, i) => (i === 0 ? s : s.charAt(0).toUpperCase() + s.slice(1)))
    .join('');
}

const WALLET_METHODS = [
  'add_address_book', 'all_tokens', 'check_reserve_proof', 'check_spend_proof',
  'check_tx_key', 'check_tx_proof', 'create_account', 'create_address',
  'create_wallet', 'delete_address_book', 'export_key_images',
  'export_multisig_info', 'finalize_multisig', 'get_account_tags', 'get_accounts',
  'get_address', 'get_address_book', 'get_attribute', 'get_balance',
  'get_bulk_payments', 'get_height', 'get_languages', 'get_payments',
  'get_reserve_proof', 'get_spend_proof', 'get_transfer_by_txid', 'get_transfers',
  'get_tx_key', 'get_tx_notes', 'get_tx_proof', 'getaddress', 'getbalance',
  'getheight', 'import_key_images', 'import_multisig_info', 'incoming_transfers',
  'is_multisig', 'label_account', 'label_address', 'make_integrated_address',
  'make_multisig', 'make_uri', 'tokens_deployed', 'my_tokens', 'open_wallet', 'parse_uri',
  'prepare_multisig', 'query_key', 'relay_tx', 'rescan_blockchain', 'rescan_spent',
  'rescan_token_tx', 'set_account_tag_description', 'set_attribute', 'set_tx_notes',
  'sign', 'sign_multisig', 'split_integrated_address', 'start_mining',
  'stop_mining', 'stop_wallet', 'store', 'submit_multisig', 'sweep_all',
  'sweep_dust', 'sweep_single', 'sweep_unmixable', 'tag_accounts', 'token_approve',
  'token_balance', 'token_burn', 'token_create', 'token_history', 'token_history_addr',
  'token_info', 'token_mint', 'token_set_fee', 'token_transfer', 'token_transfer_from',
  'transfer', 'transfer_split', 'untag_accounts', 'verify'
];

const DAEMON_JSON_METHODS = [
  'flush_txpool', 'get_alternate_chains', 'get_bans', 'get_block', 'get_block_count',
  'get_block_header_by_hash', 'get_block_header_by_height', 'get_block_headers_range',
  'get_block_template', 'get_coinbase_tx_sum', 'get_connections', 'get_fee_estimate',
  'get_info', 'get_last_block_header', 'get_output_distribution', 'get_output_histogram',
  'get_txpool_backlog', 'get_version', 'getblock', 'getblockcount', 'getblockheaderbyhash',
  'getblockheaderbyheight', 'getblockheadersrange', 'getblocktemplate', 'getlastblockheader',
  'hard_fork_info', 'on_get_block_hash', 'on_getblockhash', 'relay_tx', 'rescan_token_tx',
  'set_bans', 'submit_block', 'submitblock', 'sync_info'
];

const DAEMON_HTTP_METHODS = [
  '/get_alt_blocks_hashes', '/get_height', '/get_info', '/get_limit', '/get_outs',
  '/get_transaction_pool', '/get_transaction_pool_hashes.bin', '/get_transaction_pool_stats',
  '/get_transactions', '/getheight', '/getinfo', '/gettransactions', '/is_key_image_spent',
  '/send_raw_transaction', '/sendrawtransaction', '/get_peer_list', '/in_peers', '/mining_status',
  '/out_peers', '/save_bc', '/set_limit', '/set_log_categories', '/set_log_hash_rate',
  '/set_log_level', '/start_mining', '/start_save_graph', '/stop_daemon', '/stop_mining',
  '/stop_save_graph', '/update'
];

for (const method of WALLET_METHODS) {
  const name = camel(method);
  if (!ElectroneroRPC.prototype[name]) {
    ElectroneroRPC.prototype[name] = function (params = {}) {
      return this.wallet(method, params);
    };
  }
}

for (const method of DAEMON_JSON_METHODS) {
  const name = camel(method);
  if (!ElectroneroRPC.prototype[name]) {
    ElectroneroRPC.prototype[name] = function (params = {}) {
      return this.daemon(method, params);
    };
  }
}

for (const path of DAEMON_HTTP_METHODS) {
  const name = camel(path);
  if (!ElectroneroRPC.prototype[name]) {
    ElectroneroRPC.prototype[name] = function (params = {}) {
      return this.daemon(path, params);
    };
  }
}

module.exports = ElectroneroRPC;
