#!/usr/bin/env python3
"""Test sendwithmemo RPC."""
from decimal import Decimal
from test_framework.test_framework import InterchainedTestFramework
from test_framework.util import assert_equal

class SendWithMemoTest(InterchainedTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        addr = self.nodes[0].getnewaddress()
        txid = self.nodes[0].sendwithmemo(addr, Decimal('1'), 'hello')
        self.nodes[0].generate(1)
        tx = self.nodes[0].getrawtransaction(txid, True)
        found = any(vout['scriptPubKey'].get('type') == 'nulldata' for vout in tx['vout'])
        assert_equal(found, True)

if __name__ == '__main__':
    SendWithMemoTest().main()
