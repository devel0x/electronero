#include "evm.h"
#include <crypto/sha3.h>
#include <key.h>
#include <pubkey.h>
#include <util/strencodings.h>
#include <map>
#include <vector>
#include <cstring>
#include <streams.h>
#include <serialize.h>
#include <span.h>
#include <fs.h>
#include <util/system.h>
#include <logging.h>
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
static const char* EVM_STATE_FILENAME = "evmstate.dat";

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

#ifdef ENABLE_EVM

template <typename Stream>
void Serialize(Stream& s, const evmc::address& addr)
{
    s.write((char*)addr.bytes, sizeof(addr.bytes));
}

template <typename Stream>
void Unserialize(Stream& s, evmc::address& addr)
{
    s.read((char*)addr.bytes, sizeof(addr.bytes));
}

template <typename Stream>
void Serialize(Stream& s, const evmc::bytes32& b)
{
    s.write((char*)b.bytes, sizeof(b.bytes));
}

template <typename Stream>
void Unserialize(Stream& s, evmc::bytes32& b)
{
    s.read((char*)b.bytes, sizeof(b.bytes));
}

struct StoredAccount
{
    evmc::address addr{};
    std::vector<unsigned char> code;
    std::vector<std::pair<evmc::bytes32, evmc::bytes32>> storage;

    SERIALIZE_METHODS(StoredAccount, obj)
    {
        READWRITE(Span{obj.addr.bytes, sizeof(obj.addr.bytes)}, obj.code, obj.storage);
    }
};

static fs::path GetEVMStatePath()
{
    return GetDataDir() / EVM_STATE_FILENAME;
}

void DumpEVMState()
{
    fs::path path_tmp = GetEVMStatePath().string() + ".new";
    FILE* file = fsbridge::fopen(path_tmp, "wb");
    if (!file) return;
    CAutoFile f(file, SER_DISK, CLIENT_VERSION);
    try {
        uint8_t version = 1;
        f << version;
        f << g_next_nonce;
        std::map<std::string, std::vector<unsigned char>> keymap;
        for (const auto& it : g_eth_keys) {
            keymap[it.first] = std::vector<unsigned char>(it.second.begin(), it.second.end());
        }
        f << keymap;
        std::vector<StoredAccount> accounts;
        for (const auto& it : g_host.accounts) {
            StoredAccount acc;
            acc.addr = it.first;
            acc.code = it.second.code;
            for (const auto& st : it.second.storage) {
                acc.storage.emplace_back(st.first, st.second.current);
            }
            accounts.push_back(std::move(acc));
        }
        f << accounts;
        if (!FileCommit(f.Get())) throw std::runtime_error("FileCommit failed");
        f.fclose();
        RenameOver(path_tmp, GetEVMStatePath());
    } catch (const std::exception& e) {
        LogPrintf("Failed to write EVM state: %s\n", e.what());
    }
}

void LoadEVMState()
{
    fs::path path = GetEVMStatePath();
    FILE* file = fsbridge::fopen(path, "rb");
    if (!file) return;
    CAutoFile f(file, SER_DISK, CLIENT_VERSION);
    try {
        uint8_t version;
        f >> version;
        if (version != 1) throw std::runtime_error("Unsupported EVM state");
        f >> g_next_nonce;
        std::map<std::string, std::vector<unsigned char>> keymap;
        f >> keymap;
        g_eth_keys.clear();
        for (auto& it : keymap) {
            CKey k;
            k.Set(it.second.begin(), it.second.end(), true);
            if (k.IsValid()) g_eth_keys[it.first] = k;
        }
        std::vector<StoredAccount> accounts;
        f >> accounts;
        g_host.accounts.clear();
        for (auto& st : accounts) {
            auto& acc = g_host.accounts[st.addr];
            acc.code = st.code;
            for (auto& kv : st.storage) {
                acc.storage[kv.first] = {kv.second, kv.second};
            }
        }
    } catch (const std::exception& e) {
        LogPrintf("Failed to load EVM state: %s\n", e.what());
    }
}

#else

void DumpEVMState() {}
void LoadEVMState() {}

#endif
