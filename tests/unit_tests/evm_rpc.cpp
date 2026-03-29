#include "string_tools.h"
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
  EXPECT_EQ(42u, static_cast<uint64_t>(logs[0]));
}

TEST(EVM_RPC, CalldataOpcodes)
{
  EVM evm;
  std::string c = evm.deploy("owner", {0x36, 0xf3});
  EXPECT_EQ(3, evm.call(c, {1,2,3}));
  c = evm.deploy("owner", {0x60,0x00,0x35,0xf3});
  EXPECT_EQ(0x01020304, evm.call(c, {1,2,3,4}));
}

TEST(EVM_RPC, CodeAccessor)
{
  EVM evm;
  std::vector<uint8_t> code = {0x01, 0x02, 0x03};
  std::string c = evm.deploy("owner", code);
  const auto& out = evm.code_of(c);
  ASSERT_EQ(code, out);
}

TEST(EVM_RPC, VerifyBytecode)
{
  EVM evm;
  std::vector<uint8_t> code = {0x60, 0x01, 0x00};
  std::string c = evm.deploy("owner", code);
  std::string hex = epee::string_tools::buff_to_hex_nodelimer(std::string(code.begin(), code.end()));
  std::string deployed = epee::string_tools::buff_to_hex_nodelimer(std::string(evm.code_of(c).begin(), evm.code_of(c).end()));
  EXPECT_EQ(hex, deployed);
}

TEST(EVM_RPC, ListContracts)
{
  EVM evm;
  std::string a = evm.deploy("alice", {0});
  std::string b = evm.deploy("bob", {0});
  std::string c = evm.deploy("alice", {0});
  auto all = evm.all_addresses();
  EXPECT_EQ(3u, all.size());
  auto owned = evm.contracts_of_owner("alice");
  EXPECT_EQ(2u, owned.size());
  EXPECT_TRUE(std::find(owned.begin(), owned.end(), a) != owned.end());
  EXPECT_TRUE(std::find(owned.begin(), owned.end(), c) != owned.end());
}

TEST(EVM_RPC, TransferOwner)
{
  EVM evm;
  std::string c = evm.deploy("alice", {0});
  EXPECT_EQ("alice", evm.owner_of(c));
  EXPECT_TRUE(evm.transfer_owner(c, "bob", "alice"));
  EXPECT_EQ("bob", evm.owner_of(c));
  EXPECT_FALSE(evm.transfer_owner(c, "carol", "alice"));
}

TEST(EVM_RPC, JumpAndCompare)
{
  EVM evm;
  std::vector<uint8_t> code = {
    0x60,0x01, // PUSH1 1
    0x60,0x02, // PUSH1 2
    0x10,      // LT
    0x60,0x0b, // PUSH1 11
    0x57,      // JUMPI
    0x60,0x00, // PUSH1 0
    0xf3,      // RETURN
    0x5b,      // JUMPDEST
    0x60,0x01, // PUSH1 1
    0xf3       // RETURN
  };
  std::string c = evm.deploy("owner", code);
  EXPECT_EQ(1, evm.call(c, {}));
}

TEST(EVM_RPC, BadJump)
{
  EVM evm;
  std::vector<uint8_t> code = {0x60,0x05,0x56};
  std::string c = evm.deploy("owner", code);
  EXPECT_THROW(evm.call(c, {}), std::runtime_error);
}

TEST(EVM_RPC, DupAndSwap)
{
  EVM evm;
  // ((1 + 1) - 2) = 0
  std::vector<uint8_t> code = {
    0x60,0x01,      // PUSH1 1
    0x80,           // DUP1 -> [1,1]
    0x01,           // ADD   -> [2]
    0x60,0x02,      // PUSH1 2 -> [2,2]
    0x90,           // SWAP1 -> [2,2]
    0x03,           // SUB   -> [0]
    0xf3            // RETURN
  };
  std::string c = evm.deploy("owner", code);
  EXPECT_EQ(0, evm.call(c, {}));
}

TEST(EVM_RPC, ShiftAndReturn)
{
  EVM evm;
  // 2 << 1 = 4
  std::vector<uint8_t> code = {
    0x60,0x02, // PUSH1 2 (value)
    0x60,0x01, // PUSH1 1 (shift)
    0x1b,      // SHL
    0xf3       // RETURN
  };
  std::string c = evm.deploy("owner", code);
  EXPECT_EQ(4, evm.call(c, {}));

  // memory return
  code = {
    0x60,0x2a, // PUSH1 42
    0x60,0x00, // PUSH1 0
    0x52,      // MSTORE
    0x60,0x20, // PUSH1 32
    0x60,0x00, // PUSH1 0
    0xf3       // RETURN
  };
  c = evm.deploy("owner", code);
  EXPECT_EQ(42, evm.call(c, {}));
}
