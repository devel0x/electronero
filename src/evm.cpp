#include "evm.h"
#include <crypto/sha3.h>
#include <key.h>
#include <pubkey.h>
#include <util/strencodings.h>
#include <map>
#include <vector>
#include <cstring>
#ifdef ENABLE_EVM
#include <evmone/evmone.h>
#include <evmc/evmc.hpp>
#include <evmc/hex.hpp>
#include <evmc/bytes.hpp>
#include <evmc/mocked_host.hpp>
#endif

static std::map<std::string, CKey> g_eth_keys;
#ifdef ENABLE_EVM
static evmc::VM g_vm{evmc_create_evmone()};
static evmc::MockedHost g_host;
static uint64_t g_next_nonce = 1;

static evmc::address ParseAddr(const std::string& hex)
{
    evmc::address out{};
    auto bytes = evmc::from_hex(hex);
    if (bytes && bytes->size() == 20)
        std::memcpy(out.bytes, bytes->data(), 20);
    return out;
}

static std::string HexAddr(const evmc::address& addr)
{
    return "0x" + evmc::hex({addr.bytes, sizeof(addr.bytes)});
}
#endif

std::string ImportEthKey(const std::string& key_hex)
{
    std::vector<unsigned char> key = ParseHex(key_hex);
    CKey priv;
    priv.Set(key.begin(), key.end(), true);
    if (!priv.IsValid()) throw std::runtime_error("Invalid Ethereum key");
    CPubKey pub = priv.GetPubKey();
    unsigned char hash[32];
    SHA3_256().Write(pub.begin() + 1, pub.size() - 1).Finalize(hash);
    std::string addr = "0x" + HexStr(hash + 12, hash + 32);
    g_eth_keys[addr] = priv;
    return addr;
}

std::string EVMDeploy(const std::string& from, const std::string& bytecode)
{
#ifdef ENABLE_EVM
    auto sender = ParseAddr(from);
    auto code_bytes = evmc::from_hex(bytecode);
    if (!code_bytes)
        throw std::runtime_error("Invalid bytecode hex");

    evmc_message msg{};
    msg.kind = EVMC_CREATE;
    msg.sender = sender;
    msg.gas = 5'000'000;

    auto& bytes = *code_bytes;
    auto result = g_vm.execute(g_host, EVMC_CANCUN, msg, bytes.data(), bytes.size());
    if (result.status_code != EVMC_SUCCESS)
        throw std::runtime_error("EVM deployment failed");

    unsigned char hash[32];
    SHA3_256().Write(sender.bytes, 20).Write((unsigned char*)&g_next_nonce, sizeof(g_next_nonce)).Finalize(hash);
    evmc::address addr{};
    std::memcpy(addr.bytes, hash + 12, 20);
    g_host.accounts[addr].code.assign(result.output_data, result.output_data + result.output_size);
    ++g_next_nonce;
    return HexAddr(addr);
#else
    unsigned char hash[32];
    std::vector<unsigned char> code = ParseHex(bytecode);
    SHA3_256().Write(code.data(), code.size()).Finalize(hash);
    return "0x" + HexStr(hash + 12, hash + 32);
#endif
}

std::string EVMCall(const std::string& from, const std::string& contract, const std::string& data)
{
#ifdef ENABLE_EVM
    auto sender = ParseAddr(from);
    auto to = ParseAddr(contract);
    auto it = g_host.accounts.find(to);
    if (it == g_host.accounts.end())
        throw std::runtime_error("Unknown contract");

    auto input_bytes = evmc::from_hex(data);
    if (!input_bytes)
        throw std::runtime_error("Invalid data hex");

    evmc_message msg{};
    msg.kind = EVMC_CALL;
    msg.sender = sender;
    msg.recipient = to;
    msg.input_data = input_bytes->data();
    msg.input_size = input_bytes->size();
    msg.gas = 5'000'000;

    auto& code = it->second.code;
    auto result = g_vm.execute(g_host, EVMC_CANCUN, msg, code.data(), code.size());
    if (result.status_code != EVMC_SUCCESS && result.status_code != EVMC_REVERT)
        throw std::runtime_error("EVM call failed");
    return "0x" + evmc::hex({result.output_data, result.output_size});
#else
    (void)from;
    (void)contract;
    (void)data;
    return "0x";
#endif
}
