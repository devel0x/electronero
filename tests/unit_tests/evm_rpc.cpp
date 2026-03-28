#include "gtest/gtest.h"
#include "evm/evm.h"

using namespace CryptoNote;

TEST(EVM_RPC, DepositAndTransfer)
{
  EVM evm;
  std::string c1 = evm.deploy("owner", {0});
  std::string c2 = evm.deploy("owner", {0});
  EXPECT_TRUE(evm.deposit(c1, 50));
  EXPECT_EQ(50u, evm.balance_of(c1));
  EXPECT_TRUE(evm.transfer(c1, c2, 20, "owner"));
  EXPECT_EQ(30u, evm.balance_of(c1));
  EXPECT_EQ(20u, evm.balance_of(c2));
  EXPECT_FALSE(evm.transfer(c1, c2, 5, "other"));
}

TEST(EVM_RPC, InvalidOperations)
{
  EVM evm;
  std::string c1 = evm.deploy("owner", {0});
  std::string c2 = evm.deploy("owner2", {0});
  EXPECT_FALSE(evm.transfer(c1, c2, 1, "owner"));
  EXPECT_FALSE(evm.deposit("missing", 10));
}
