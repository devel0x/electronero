#!/usr/bin/env python3
"""Test burn RPC."""
from decimal import Decimal
from test_framework.test_framework import InterchainedTestFramework
from test_framework.util import assert_greater_than

class BurnRPCTest(InterchainedTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        start_balance = self.nodes[0].getbalance()
        self.nodes[0].burn(Decimal('1'))
        self.nodes[0].generate(1)
        end_balance = self.nodes[0].getbalance()
        assert_greater_than(start_balance - end_balance, Decimal('0.999'))

if __name__ == '__main__':
    BurnRPCTest().main()
