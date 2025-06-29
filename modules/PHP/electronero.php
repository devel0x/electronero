<?php
/**
 * Electronero PHP RPC Module
 *
 * Provides helper functions to interact with Electronero daemon and wallet RPC interfaces.
 */

class ElectroneroRPC {
    /** @var string Wallet RPC endpoint */
    private $walletUrl;
    /** @var string Daemon RPC endpoint */
    private $daemonUrl;
    /** @var array  cURL options */
    private $curlOpts;

    /**
     * Wallet RPC method names extracted from the Electronero sources.
     * These can be called directly on the class instance.
     */
    private const WALLET_METHODS = [
        'get_balance',
        'get_address',
        'getbalance',
        'getaddress',
        'create_address',
        'label_address',
        'get_accounts',
        'create_account',
        'label_account',
        'get_account_tags',
        'tag_accounts',
        'untag_accounts',
        'set_account_tag_description',
        'get_height',
        'getheight',
        'transfer',
        'transfer_split',
        'sweep_dust',
        'sweep_unmixable',
        'sweep_all',
        'sweep_single',
        'relay_tx',
        'store',
        'get_payments',
        'get_bulk_payments',
        'incoming_transfers',
        'query_key',
        'make_integrated_address',
        'split_integrated_address',
        'stop_wallet',
        'rescan_blockchain',
        'set_tx_notes',
        'get_tx_notes',
        'set_attribute',
        'get_attribute',
        'get_tx_key',
        'check_tx_key',
        'get_tx_proof',
        'check_tx_proof',
        'get_spend_proof',
        'check_spend_proof',
        'get_reserve_proof',
        'check_reserve_proof',
        'get_transfers',
        'get_transfer_by_txid',
        'sign',
        'verify',
        'export_key_images',
        'import_key_images',
        'make_uri',
        'parse_uri',
        'get_address_book',
        'add_address_book',
        'delete_address_book',
        'rescan_spent',
        'rescan_token_tx',
        'start_mining',
        'stop_mining',
        'get_languages',
        'create_wallet',
        'open_wallet',
        'is_multisig',
        'prepare_multisig',
        'make_multisig',
        'export_multisig_info',
        'import_multisig_info',
        'finalize_multisig',
        'sign_multisig',
        'submit_multisig',
        'token_create',
        'token_balance',
        'token_transfer',
        'token_approve',
        'token_transfer_from',
        'token_burn',
        'token_mint',
        'token_info',
        'all_tokens',
        'tokens_deployed',
        'my_tokens',
        'token_history',
        'token_history_addr',
        'token_set_fee',
        'token_lock_fee',
    ];

    /**
     * Daemon RPC method names extracted from the Electronero sources.
     */
    private const DAEMON_METHODS = [
        'get_alt_blocks_hashes',
        'get_block',
        'get_block_count',
        'get_block_header_by_hash',
        'get_block_header_by_height',
        'get_block_headers_range',
        'get_block_template',
        'get_blocks.bin',
        'get_blocks_by_height.bin',
        'get_fee_estimate',
        'get_hashes.bin',
        'get_height',
        'get_info',
        'get_last_block_header',
        'get_limit',
        'get_o_indexes.bin',
        'get_output_distribution',
        'get_output_histogram',
        'get_outs',
        'get_outs.bin',
        'get_peer_list',
        'get_random_outs.bin',
        'get_random_rctouts.bin',
        'get_transaction_pool',
        'get_transaction_pool_hashes.bin',
        'get_transaction_pool_stats',
        'get_transactions',
        'get_txpool_backlog',
        'get_version',
        'getblock',
        'getblockcount',
        'getblockheaderbyhash',
        'getblockheaderbyheight',
        'getblockheadersrange',
        'getblocks.bin',
        'getblocks_by_height.bin',
        'getblocktemplate',
        'gethashes.bin',
        'getheight',
        'getinfo',
        'getlastblockheader',
        'getrandom_outs.bin',
        'getrandom_rctouts.bin',
        'gettransactions',
        'hard_fork_info',
        'in_peers',
        'is_key_image_spent',
        'mining_status',
        'on_get_block_hash',
        'on_getblockhash',
        'out_peers',
        'save_bc',
        'send_raw_transaction',
        'sendrawtransaction',
        'set_limit',
        'set_log_categories',
        'set_log_hash_rate',
        'set_log_level',
        'start_mining',
        'start_save_graph',
        'stop_daemon',
        'stop_mining',
        'stop_save_graph',
        'submit_block',
        'submitblock',
        'update',
    ];

    /**
     * Constructor.
     *
     * @param string $walletUrl Base URL of wallet RPC endpoint, e.g. http://127.0.0.1:11212/json_rpc
     * @param string $daemonUrl Base URL of daemon RPC endpoint, e.g. http://127.0.0.1:26969/json_rpc
     * @param array $curlOpts Optional cURL options to merge with defaults
     */
    public function __construct($walletUrl = 'http://127.0.0.1:11212/json_rpc', $daemonUrl = 'http://127.0.0.1:26969/json_rpc', array $curlOpts = []) {
        $this->walletUrl = rtrim($walletUrl, '/');
        $this->daemonUrl = rtrim($daemonUrl, '/');
        $this->curlOpts = $curlOpts;
    }

    /**
     * Perform a JSON-RPC request.
     *
     * @param string $url  Endpoint URL
     * @param string $method RPC method name
     * @param array $params Parameters for the call
     * @return mixed Response decoded from JSON
     * @throws Exception on cURL error or invalid response
     */
    private function jsonRpc($url, $method, array $params = []) {
        $id = uniqid('rpc_', true);
        $payload = json_encode([
            'jsonrpc' => '2.0',
            'id'      => $id,
            'method'  => $method,
            'params'  => $params
        ]);

        $ch = curl_init($url);
        $opts = [
            CURLOPT_POST => true,
            CURLOPT_HTTPHEADER => [
                'Content-Type: application/json'
            ],
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_TIMEOUT => 30,
            CURLOPT_POSTFIELDS => $payload
        ] + $this->curlOpts;
        curl_setopt_array($ch, $opts);
        $res = curl_exec($ch);
        if ($res === false) {
            $err = curl_error($ch);
            curl_close($ch);
            throw new Exception('RPC request failed: ' . $err);
        }
        curl_close($ch);
        $data = json_decode($res, true);
        if ($data === null) {
            throw new Exception('Invalid JSON response: ' . $res);
        }
        return $data;
    }

    /**
     * Call a wallet RPC method.
     *
     * @param string $method RPC method name
     * @param array $params Parameters for the call
     * @return mixed Response decoded from JSON
     */
    public function wallet($method, array $params = []) {
        return $this->jsonRpc($this->walletUrl, $method, $params);
    }

    /**
     * Call a daemon RPC method.
     *
     * @param string $method RPC method name
     * @param array $params Parameters for the call
     * @return mixed Response decoded from JSON
     */
    public function daemon($method, array $params = []) {
        return $this->jsonRpc($this->daemonUrl, $method, $params);
    }

    /**
     * Magic handler to allow direct calls to wallet or daemon RPC methods.
     * Example: $rpc->get_balance(['account_index' => 0]);
     */
    public function __call($name, $arguments) {
        $params = $arguments[0] ?? [];
        if (in_array($name, self::WALLET_METHODS, true)) {
            return $this->wallet($name, $params);
        }
        if (in_array($name, self::DAEMON_METHODS, true)) {
            return $this->daemon($name, $params);
        }
        throw new BadMethodCallException("Unknown RPC method: $name");
    }

    /**
     * Return list of available wallet RPC method names.
     */
    public function listWalletMethods() {
        return self::WALLET_METHODS;
    }

    /**
     * Return list of available daemon RPC method names.
     */
    public function listDaemonMethods() {
        return self::DAEMON_METHODS;
    }
}
?>
