#!/usr/bin/env python3
"""Test bridgefunds RPC."""
from decimal import Decimal
from test_framework.test_framework import InterchainedTestFramework
from test_framework.util import assert_equal

BRIDGE_ADDR = "2222222222222222222224oLvT3"

class BridgeFundsTest(InterchainedTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        txid = self.nodes[0].bridgefunds(Decimal('1'), '0xdeadbeef')
        self.nodes[0].generate(1)
        tx = self.nodes[0].getrawtransaction(txid, True)
        has_bridge = any(BRIDGE_ADDR in vout['scriptPubKey'].get('addresses', []) for vout in tx['vout'] if vout['scriptPubKey'].get('type') != 'nulldata')
        has_memo = any(vout['scriptPubKey'].get('type') == 'nulldata' for vout in tx['vout'])
        assert_equal(has_bridge and has_memo, True)

if __name__ == '__main__':
    BridgeFundsTest().main()
