#!/usr/bin/env python3
"""Test getbestheaderhash RPC."""
from test_framework.test_framework import InterchainedTestFramework
from test_framework.util import assert_equal

class GetBestHeaderHashTest(InterchainedTestFramework):
    def set_test_params(self):
        self.num_nodes = 1

    def run_test(self):
        # Initially best header hash should be same as best block hash
        assert_equal(self.nodes[0].getbestheaderhash(), self.nodes[0].getbestblockhash())
        # Generate a block and verify hashes still match
        self.nodes[0].generate(1)
        assert_equal(self.nodes[0].getbestheaderhash(), self.nodes[0].getbestblockhash())

if __name__ == '__main__':
    GetBestHeaderHashTest().main()
