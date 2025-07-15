#!/usr/bin/env python3
"""Basic token RPC integration test"""
from test_framework.test_framework import InterchainedTestFramework
from test_framework.util import assert_equal

class TokenWalletTest(InterchainedTestFramework):
    def set_test_params(self):
        self.num_nodes = 1
        self.setup_clean_chain = True
        self.extra_args = [[]]

    def skip_test_if_missing_module(self):
        self.skip_if_no_wallet()

    def run_test(self):
        node = self.nodes[0]
        node.generate(101)
        token_id = "0x" + "1"*54 + "tok"
        node.createtoken(token_id, 100, "TestToken", "TST", 0)
        assert node.getsigneraddress()
        assert_equal(node.gettokenbalance(token_id), 100)
        node.createwallet(wallet_name="bob")
        node.tokentransfer("bob", token_id, 25)
        assert_equal(node.gettokenbalanceof(token_id, "bob"), 25)
        bob = node.get_wallet_rpc("bob")
        assert bob.getsigneraddress()
        node.tokentransfer("bob", token_id, 25)
        assert_equal(node.gettokenbalanceof(token_id, "bob"), 25)
        assert_equal(bob.gettokenbalance(token_id), 25)
        node.tokenapprove("bob", token_id, 10)
        assert_equal(node.tokenallowance(node.getwalletinfo()["walletname"], "bob", token_id), 10)
        bob.tokentransferfrom(node.getwalletinfo()["walletname"], "bob", token_id, 5)
        assert_equal(bob.gettokenbalance(token_id), 30)
        assert_equal(node.gettokenbalanceof(token_id, "bob"), 30)

if __name__ == '__main__':
    TokenWalletTest().main()
