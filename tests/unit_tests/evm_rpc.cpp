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

TEST(EVM_RPC, BlockInfoOpcodes)
{
  EVM evm;
  std::string c = evm.deploy("owner", {0x42, 0xf3});
  EXPECT_EQ(10, evm.call(c, {}, 5, 10));
  c = evm.deploy("owner", {0x43, 0xf3});
  EXPECT_EQ(5, evm.call(c, {}, 5, 10));
}

TEST(EVM_RPC, LogOpcode)
{
  EVM evm;
  std::string c = evm.deploy("owner", {0x60, 0x2a, 0xa1, 0x00});
  evm.call(c, {});
  auto logs = evm.logs_of(c);
  ASSERT_EQ(1u, logs.size());
  EXPECT_EQ(42u, logs[0]);
}

TEST(EVM_RPC, CalldataOpcodes)
{
  EVM evm;
  std::string c = evm.deploy("owner", {0x36, 0xf3});
  EXPECT_EQ(3, evm.call(c, {1,2,3}));
  c = evm.deploy("owner", {0x60,0x00,0x35,0xf3});
  EXPECT_EQ(0x01020304, evm.call(c, {1,2,3,4}));
}
