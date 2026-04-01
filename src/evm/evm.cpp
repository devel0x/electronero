#include "evm.h"

#include <stdexcept>
#include "misc_log_ex.h"
#include "common/boost_serialization_helper.h"
#include "wallet/wallet2.h"
#include "wipeable_string.h"
#include <boost/filesystem.hpp>

#include <unordered_map>
#include <set>
#include <ctime>
#include <cstring>
#include "cryptonote_config.h"
#include "cryptonote_basic/cryptonote_format_utils.h"
#include "crypto/keccak.h"
#include <boost/multiprecision/cpp_int.hpp>
#include "crypto/hash.h"
#include "string_tools.h"

namespace CryptoNote {

void EVM::rebuild_id_map()
{
  id_map.clear();
  for (const auto &kv : contracts)
  {
    id_map[kv.second.id] = kv.first;
  }
}

std::string EVM::deploy(const std::string& owner, const std::vector<uint8_t>& bytecode) {
  const uint64_t id = ++next_id;
  uint64_t ts = static_cast<uint64_t>(time(nullptr));
  std::string data = owner + std::to_string(id) + std::to_string(ts);
  crypto::hash h = crypto::cn_fast_hash(data.data(), data.size());
  std::string hex = epee::string_tools::pod_to_hex(h);
  hex.resize(50);
  std::string address = config::CRYPTONOTE_PUBLIC_EVM_ADDRESS_PREFIX + hex;
  Contract c;
  c.code = bytecode;
  c.owner = owner;
  c.id = id;
  crypto::hash secret;
  crypto::generate_random_bytes_not_thread_safe(sizeof(secret), &secret);
  c.secret_enc = secret;
  for (size_t i = 0; i < sizeof(secret.data); ++i)
    c.secret_enc.data[i] ^= config::EVM_SECRET_XOR[i % config::EVM_SECRET_XOR.size()];
  memwipe(&secret, sizeof(secret));
  contracts[address] = c;
  id_map[id] = address;
  return address;
}

bool EVM::deposit(const std::string& address, const std::string& amount_str)
{
  uint64_t amount = 0;
  if (!cryptonote::parse_amount(amount, amount_str))
    return false;
  auto it = contracts.find(address);
  if (it == contracts.end()) return false;
  double amount_parsed = amount / 1e8;
  it->second.balance += amount_parsed;
  return true;
}

bool EVM::transfer(const std::string& from, const std::string& to, const std::string& amount_str, const std::string& caller)
{
  uint64_t amount = 0;
  if (!cryptonote::parse_amount(amount, amount_str))
    return false;
  auto it_from = contracts.find(from);
  if (it_from == contracts.end() || it_from->second.balance < amount)
    return false;
  if (it_from->second.owner != caller)
    return false;
  crypto::secret_key spend_key, view_key;
  if (!get_contract_keys(from, spend_key, view_key))
    return false;

  cryptonote::account_public_address from_addr = deposit_address(from);
  tools::wallet2 w(cryptonote::MAINNET);
  epee::wipeable_string pwd;
  w.generate(from, pwd, from_addr, spend_key, view_key, false);
  w.init("localhost:11882"); 
  // todo programatically determine localhost port based on cryptonote_config or console arguments 

  cryptonote::address_parse_info info;
  if (!cryptonote::get_account_address_from_str_or_url(info, w.nettype(), to, nullptr))
    return false;
  
  double amount_parsed = amount / 1e8;
  cryptonote::tx_destination_entry de;
  de.addr = info.address;
  de.amount = amount;
  de.is_subaddress = info.is_subaddress;

  std::vector<cryptonote::tx_destination_entry> dsts{de};
  std::set<uint32_t> subaddr;
  try {
    auto ptx = w.create_transactions_2(dsts, 0, 0, 0, std::vector<uint8_t>(), 0, subaddr, true, 0);
    if (ptx.empty())
      return false;
    w.commit_tx(ptx[0]);
  } catch (const std::exception &e) {
    MERROR("contract transfer tx failed: " << e.what());
    return false;
  }

  it_from->second.balance -= amount_parsed;
  contracts[to].balance += amount_parsed;
  return true;
}

bool EVM::destroy(const std::string& address, const std::string& dest, const std::string& caller)
{
  auto it = contracts.find(address);
  if (it == contracts.end())
    return false;
  if (it->second.owner != caller)
    return false;
  contracts[dest].balance += it->second.balance;
  contracts.erase(it);
  return true;
}

bool EVM::transfer_owner(const std::string& address, const std::string& new_owner, const std::string& caller)
{
  auto it = contracts.find(address);
  if (it == contracts.end())
    return false;
  if (it->second.owner != caller)
    return false;
  it->second.owner = new_owner;
  return true;
}

uint64_t EVM::balance_of(const std::string& address) const
{
  auto it = contracts.find(address);
  return it == contracts.end() ? 0 : it->second.balance;
}

std::string EVM::owner_of(const std::string& address) const
{
  auto it = contracts.find(address);
  return it == contracts.end() ? std::string() : it->second.owner;
}

const std::vector<uint256>& EVM::logs_of(const std::string& address) const
{
  static const std::vector<uint256> empty;
  auto it = contracts.find(address);
  return it == contracts.end() ? empty : it->second.logs;
}

const std::vector<uint8_t>& EVM::code_of(const std::string& address) const
{
  static const std::vector<uint8_t> empty;
  auto it = contracts.find(address);
  return it == contracts.end() ? empty : it->second.code;
}

bool EVM::get_contract_keys(const std::string& address, crypto::secret_key &spend, crypto::secret_key &view) const
{
  auto it = contracts.find(address);
  if (it == contracts.end())
    return false;

  crypto::hash secret = it->second.secret_enc;
  for (size_t i = 0; i < sizeof(secret.data); ++i)
    secret.data[i] ^= config::EVM_SECRET_XOR[i % config::EVM_SECRET_XOR.size()];

  crypto::hash mix;
  crypto::cn_fast_hash(address.data(), address.size(), mix);
  for (size_t i = 0; i < sizeof(mix.data); ++i)
    mix.data[i] ^= secret.data[i];
  crypto::hash h2;
  crypto::cn_fast_hash(&mix, sizeof(mix), h2);

  memcpy(spend.data, &mix, sizeof(spend.data));
  memcpy(view.data, &h2, sizeof(view.data));
  sc_reduce32(reinterpret_cast<unsigned char*>(spend.data));
  sc_reduce32(reinterpret_cast<unsigned char*>(view.data));

  memwipe(&secret, sizeof(secret));
  return true;
}

cryptonote::account_public_address EVM::deposit_address(const std::string& address) const
{
  cryptonote::account_public_address out{crypto::null_pkey, crypto::null_pkey};
  auto it = contracts.find(address);
  if (it == contracts.end())
    return out;

  crypto::hash secret = it->second.secret_enc;
  for (size_t i = 0; i < sizeof(secret.data); ++i)
    secret.data[i] ^= config::EVM_SECRET_XOR[i % config::EVM_SECRET_XOR.size()];

  crypto::hash mix;
  crypto::cn_fast_hash(address.data(), address.size(), mix);
  for (size_t i = 0; i < sizeof(mix.data); ++i)
    mix.data[i] ^= secret.data[i];
  crypto::hash h2;
  crypto::cn_fast_hash(&mix, sizeof(mix), h2);

  crypto::secret_key spend_key, view_key;
  memcpy(spend_key.data, &mix, sizeof(spend_key.data));
  memcpy(view_key.data, &h2, sizeof(view_key.data));
  sc_reduce32(reinterpret_cast<unsigned char*>(spend_key.data));
  sc_reduce32(reinterpret_cast<unsigned char*>(view_key.data));

  crypto::public_key spend_pub, view_pub;
  crypto::secret_key_to_public_key(spend_key, spend_pub);
  crypto::secret_key_to_public_key(view_key, view_pub);

  out.m_spend_public_key = spend_pub;
  out.m_view_public_key  = view_pub;

  memwipe(&spend_key, sizeof(spend_key));
  memwipe(&view_key, sizeof(view_key));
  memwipe(&secret, sizeof(secret));
  return out;
}

std::string EVM::smart_wallet_address(const std::string& address) const
{
  crypto::hash h;
  keccak(reinterpret_cast<const uint8_t*>(address.data()), address.size(), reinterpret_cast<uint8_t*>(&h), sizeof(h));
  std::string hex = epee::string_tools::pod_to_hex(h);
  smart_map[hex] = address;
  return hex;
}

std::string EVM::public_wallet_address(const std::string& smart) const
{
  auto it = smart_map.find(smart);
  if (it == smart_map.end())
    return std::string();
  return it->second;
}

std::vector<std::string> EVM::contracts_of_owner(const std::string& owner) const
{
  std::vector<std::string> out;
  for (const auto& kv : contracts)
  {
    if (kv.second.owner == owner)
      out.push_back(kv.first);
  }
  return out;
}

std::vector<std::string> EVM::all_addresses() const
{
  std::vector<std::string> out;
  for (const auto& kv : contracts)
    out.push_back(kv.first);
  return out;
}

bool EVM::is_owner(const std::string& contract, const std::string& address) const
{
  auto it = contracts.find(contract);
  return it != contracts.end() && it->second.owner == address;
}

uint256 EVM::storage_at(const std::string& address, uint256 key) const
{
  auto it = contracts.find(address);
  if (it == contracts.end())
    return 0;
  auto jt = it->second.storage.find(key);
  return jt == it->second.storage.end() ? uint256(0) : jt->second;
}

int64_t EVM::call(const std::string& address, const std::vector<uint8_t>& input,
                  uint64_t block_height, uint64_t timestamp,
                  const std::string& caller, uint64_t call_value) {
  auto it = contracts.find(address);
  if (it == contracts.end()) {
    return 0;
  }
  MWARNING("EVM call to " << address <<
           " from " << (caller.empty() ? "<none>" : caller) <<
           " value=" << call_value <<
           " data=" << epee::string_tools::buff_to_hex_nodelimer(std::string(input.begin(), input.end())) <<
           " height=" << block_height <<
           " ts=" << timestamp);
  last_return_data.clear();
  int64_t res = execute(address, it->second, input, block_height, timestamp, caller, call_value);
  MDEBUG("EVM::call result:" << res);
  return res;
}

int64_t EVM::execute(const std::string& self, Contract& contract, const std::vector<uint8_t>& input,
                     uint64_t block_height, uint64_t timestamp,
                     const std::string& caller, uint64_t call_value) {
  struct Value {
    bool is_string;
    uint256 num;
    std::string str;
    Value() : is_string(false), num(0) {}
    Value(uint256 n) : is_string(false), num(n) {}
    Value(const std::string &s) : is_string(true), num(0), str(s) {}
  };

  std::vector<Value> stack;
  std::unordered_map<uint64_t, Value> memory;

  MWARNING("EVM execute self=" << self <<
           " owner=" << contract.owner <<
           " id=" << contract.id <<
           " balance=" << contract.balance <<
           " caller=" << (caller.empty() ? "<none>" : caller) <<
           " value=" << call_value <<
           " data=" << epee::string_tools::buff_to_hex_nodelimer(std::string(input.begin(), input.end())) <<
           " height=" << block_height <<
           " ts=" << timestamp);

  auto pop_value = [&]() -> Value {
    if (stack.empty()) throw std::runtime_error("stack underflow");
    Value v = stack.back();
    stack.pop_back();
    return v;
  };

  auto pop_num = [&]() -> uint256 {
    Value v = pop_value();
    if (v.is_string) throw std::runtime_error("expected numeric value");
    return v.num;
  };

  auto push_num = [&](uint256 n) { stack.emplace_back(n); };
  auto push_str = [&](const std::string &s) { stack.emplace_back(s); };
  const auto& code = contract.code;
  std::unordered_set<size_t> jumpdests;
  for (size_t i = 0; i < code.size(); ++i)
    if (code[i] == 0x5b)
      jumpdests.insert(i);

  for (size_t pc = 0; pc < code.size();) {
    uint8_t op = code[pc++];
    MWARNING("EVM opcode 0x" << std::hex << (int)op << std::dec << " pc=" << (pc-1) << " stack=" << stack.size());
    switch (op) {
      case 0x00: // STOP
        if (stack.empty()) return 0;
        if (stack.back().is_string) return 0;
        return static_cast<int64_t>(stack.back().num);
      case 0x01: { // ADD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a + b);
        break;
      }
      case 0x02: { // MUL
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a * b);
        break;
      }
      case 0x03: { // SUB
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a - b);
        break;
      }
      case 0x04: { // DIV
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(b == 0 ? 0 : a / b);
        break;
      }
      case 0x06: { // MOD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(b == 0 ? 0 : a % b);
        break;
      }
      case 0x07: { // SMOD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 b = static_cast<int256>(pop_num());
        int256 a = static_cast<int256>(pop_num());
        if (b == 0) push_num(0);
        else push_num(static_cast<uint256>(a % b));
        break;
      }
      case 0x05: { // SDIV
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 b = static_cast<int256>(pop_num());
        int256 a = static_cast<int256>(pop_num());
        push_num(b == 0 ? 0 : static_cast<uint256>(a / b));
        break;
      }
      case 0x08: { // ADDMOD
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 c = pop_num();
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(c == 0 ? 0 : (a + b) % c);
        break;
      }
      case 0x09: { // MULMOD
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 m = pop_num();
        uint256 b = pop_num();
        uint256 a = pop_num();
        if (m == 0) { push_num(0); break; }
        push_num((a * b) % m);
        break;
      }
      case 0x0a: { // EXP
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 exp = pop_num();
        uint256 base = pop_num();
        uint256 res = 1;
        for (uint256 i = 0; i < exp; ++i)
          res *= base;
        push_num(res);
        break;
      }
      case 0x0b: { // SIGNEXTEND
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 x = pop_num();
        const unsigned n = b.convert_to<unsigned>();
        if (n >= 32) { push_num(x); break; }
        uint256 mask = ((uint256(1) << 8*(n+1)) - 1);
        uint256 sign_bit = uint256(1) << (8*(n+1)-1);
        uint256 res = x & mask;
        if (res & sign_bit)
          res |= (~mask);
        push_num(res);
        break;
      }
      case 0x10: { // LT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 a = pop_num();
        uint256 b = pop_num();
        push_num(a < b);
        break;
      }
      case 0x11: { // GT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 a = pop_num();
        uint256 b = pop_num();
        push_num(a > b);
        break;
      }
      case 0x12: { // SLT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 a = static_cast<int256>(pop_num());
        int256 b = static_cast<int256>(pop_num());
        push_num(a < b);
        break;
      }
      case 0x13: { // SGT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 a = static_cast<int256>(pop_num());
        int256 b = static_cast<int256>(pop_num());
        push_num(a > b);
        break;
      }
      case 0x14: { // EQ
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a == b);
        break;
      }
      case 0x15: { // ISZERO
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 a = pop_num();
        push_num(a == 0);
        break;
      }
      case 0x16: { // AND
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a & b);
        break;
      }
      case 0x17: { // OR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a | b);
        break;
      }
      case 0x18: { // XOR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = pop_num();
        uint256 a = pop_num();
        push_num(a ^ b);
        break;
      }
      case 0x19: { // NOT
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 a = pop_num();
        push_num(~a);
        break;
      }
      case 0x1a: { // BYTE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 pos = pop_num();
        uint256 word = pop_num();
        unsigned int p = pos.convert_to<unsigned int>();
        if (p >= 32) push_num(0);
        else push_num((word >> ((31 - p) * 8)) & 0xff);
        break;
      }
      case 0x1b: { // SHL
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 shift = pop_num();
        uint256 value = pop_num();
        const unsigned s = shift.convert_to<unsigned>();
        push_num(s >= 256 ? 0 : (value << s));
        break;
      }
      case 0x1c: { // SHR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 shift = pop_num();
        uint256 value = pop_num();
        const unsigned s = shift.convert_to<unsigned>();
        push_num(s >= 256 ? 0 : (value >> s));
        break;
      }
      case 0x1d: { // SAR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 shift = pop_num();
        int256 value = static_cast<int256>(pop_num());
        const unsigned s = shift.convert_to<unsigned>();
        if (s >= 256)
          push_num(value < 0 ? static_cast<uint256>(-1) : 0);
        else
          push_num(static_cast<uint256>(value >> s));
        break;
      }
      case 0x20: { // KECCAK256
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 offset = pop_num();
        uint256 len = pop_num();
        std::vector<uint8_t> buf;
        buf.reserve(len.convert_to<size_t>());
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          Value mv = memory[static_cast<uint64_t>((offset + i).convert_to<uint64_t>())];
          uint256 v = mv.is_string ? 0 : mv.num;
          buf.push_back(v.convert_to<uint8_t>());
        }
        crypto::hash h;
        keccak(buf.data(), buf.size(), reinterpret_cast<uint8_t*>(&h), sizeof(h));
        uint256 v = 0;
        for (int i = 0; i < 32; ++i)
        {
          v <<= 8;
          v |= ((const unsigned char*)&h)[i];
        }
        push_num(v);
        break;
      }
      case 0x34: { // CALLVALUE
        push_num(call_value);
        break;
      }
      case 0x35: { // CALLDATALOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 off = pop_num();
        // Solidity passes arguments as 32-byte big-endian words. Load the
        // entire word and truncate to 64 bits so typical uint256 arguments
        // work correctly.
        uint256 v = 0;
        for (unsigned i = 0; i < 32; ++i, ++off) {
          v <<= 8;
          size_t pos = off.convert_to<size_t>();
          if (pos < input.size())
            v |= input[pos];
        }
        push_num(v);
        break;
      }
      case 0x36: { // CALLDATASIZE
        push_num(input.size());
        break;
      }
      case 0x37: { // CALLDATACOPY
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 dest = pop_num();
        uint256 src = pop_num();
        uint256 len = pop_num();
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          size_t pos = (src + i).convert_to<size_t>();
          uint256 b = pos < input.size() ? input[pos] : 0;
          memory[(dest + i).convert_to<uint64_t>()] = Value(b);
        }
        break;
      }
      case 0x38: { // CODESIZE
        push_num(code.size());
        break;
      }
      case 0x39: { // CODECOPY
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 dest = pop_num();
        uint256 src = pop_num();
        uint256 len = pop_num();
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          size_t pos = (src + i).convert_to<size_t>();
          uint256 b = pos < code.size() ? code[pos] : 0;
          memory[(dest + i).convert_to<uint64_t>()] = Value(b);
        }
        break;
      }
      case 0x3a: { // GASPRICE
        push_num(0);
        break;
      }
      case 0x3b: { // EXTCODESIZE
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 id = pop_num();
        auto it = id_map.find(id.convert_to<uint64_t>());
        if (it == id_map.end()) { push_num(0); break; }
        push_num(code_of(it->second).size());
        break;
      }
      case 0x3c: { // EXTCODECOPY
        if (stack.size() < 4) throw std::runtime_error("stack underflow");
        uint256 dest_off = pop_num();
        uint256 off = pop_num();
        uint256 len = pop_num();
        uint256 id = pop_num();
        const std::vector<uint8_t>* ext = nullptr;
        auto it = id_map.find(id.convert_to<uint64_t>());
        if (it != id_map.end())
          ext = &code_of(it->second);
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          size_t pos = (off + i).convert_to<size_t>();
          uint256 b = (ext && pos < ext->size()) ? (*ext)[pos] : 0;
          memory[(dest_off + i).convert_to<uint64_t>()] = Value(b);
        }
        break;
      }
      case 0x3d: { // RETURNDATASIZE
        push_num(last_return_data.size());
        break;
      }
      case 0x3e: { // RETURNDATACOPY
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 len = pop_num();
        uint256 offset = pop_num();
        uint256 dest_off = pop_num();
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          size_t pos = (offset + i).convert_to<size_t>();
          uint256 b = pos < last_return_data.size() ? last_return_data[pos] : 0;
          memory[(dest_off + i).convert_to<uint64_t>()] = Value(b);
        }
        break;
      }
      case 0x3f: { // EXTCODEHASH
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 id = pop_num();
        auto it = id_map.find(id.convert_to<uint64_t>());
        if (it == id_map.end()) { push_num(0); break; }
        const auto& ext_code = code_of(it->second);
        crypto::hash h;
        crypto::cn_fast_hash(ext_code.data(), ext_code.size(), h);
        uint256 v = 0;
        for (int i = 0; i < 32; ++i)
        {
          v <<= 8;
          v |= ((const unsigned char*)&h)[i];
        }
        push_num(v);
        break;
      }
      case 0x30: { // ADDRESS
        // push the current contract id onto the stack
        push_num(contract.id);
        break;
      }
      case 0x31: { // BALANCE
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 id = pop_num();
        auto it = id_map.find(id.convert_to<uint64_t>());
        if (it == id_map.end()) { push_num(0); break; }
        push_num(balance_of(it->second));
        break;
      }
      case 0x32: { // ORIGIN
        if (caller.empty())
          push_num(0);
        else
        {
          auto itc = contracts.find(caller);
          if (itc != contracts.end())
            push_num(itc->second.id);
          else
            push_str(caller);
        }
        break;
      }
      case 0x33: { // CALLER
        if (caller.empty())
        {
          push_num(0);
        }
        else
        {
          auto itc = contracts.find(caller);
          if (itc != contracts.end())
          {
            push_num(itc->second.id);
          }
          else
          {
            push_str(caller);
          }
        }
        break;
      }
      case 0x40: { // BLOCKHASH
        crypto::hash h;
        keccak(reinterpret_cast<const uint8_t*>(&block_height), sizeof(block_height), reinterpret_cast<uint8_t*>(&h), sizeof(h));
        uint256 v = 0;
        for (int i = 0; i < 32; ++i)
        {
          v <<= 8;
          v |= ((const unsigned char*)&h)[i];
        }
        push_num(v);
        break;
      }
      case 0x41: { // COINBASE
        push_num(contract.id);
        break;
      }
      case 0x42: { // TIMESTAMP
        push_num(timestamp);
        break;
      }
      case 0x43: { // NUMBER
        push_num(block_height);
        break;
      }
      case 0x44: { // DIFFICULTY
        push_num(0);
        break;
      }
      case 0x45: { // GASLIMIT
        push_num(100000000);
        break;
      }
      case 0x46: { // CHAINID
        push_num(0);
        break;
      }
      case 0x48: { // BASEFEE
        push_num(0);
        break;
      }
      case 0x47: { // SELFBALANCE
        push_num(contract.balance);
        break;
      }
      case 0x50: { // POP
        if (stack.empty()) throw std::runtime_error("stack underflow");
        stack.pop_back();
        break;
      }
      case 0x56: { // JUMP
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 dest = pop_num();
        size_t d = dest.convert_to<size_t>();
        if (d >= code.size() || !jumpdests.count(d))
          throw std::runtime_error("bad jump dest 0x56");
        pc = d;
        break;
      }
      case 0x57: { // JUMPI
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 dest = pop_num();
        uint256 cond = pop_num();
        if (cond != 0) {
          size_t d = dest.convert_to<size_t>();
          if (d >= code.size() || !jumpdests.count(d))
            throw std::runtime_error("bad jump dest 0x57");
          pc = d;
        }
        break;
      }
      case 0x58: { // PC
        push_num(pc - 1);
        break;
      }
      case 0x59: { // MSIZE
        push_num(memory.size());
        break;
      }
      case 0x5a: { // GAS
        push_num(1000000);
        break;
      }
      case 0x5b: { // JUMPDEST
        break;
      }
      case 0x51: { // MLOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 offset = pop_num();
        stack.push_back(memory[static_cast<uint64_t>(offset)]);
        break;
      }
      case 0x52: { // MSTORE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 offset = pop_num();
        Value value = pop_value();
        memory[static_cast<uint64_t>(offset)] = value;
        break;
      }
      case 0x53: { // MSTORE8
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 offset = pop_num();
        uint256 value = pop_num();
        memory[static_cast<uint64_t>(offset)] = Value(value & 0xff);
        break;
      }
      case 0x54: { // SLOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 key = pop_num();
        push_num(contract.storage[key]);
        break;
      }
      case 0x55: { // SSTORE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 key = pop_num();
        uint256 value = pop_num();
        contract.storage[key] = value;
        break;
      }
      case 0x80 ... 0x8f: { // DUP1 through DUP16
        unsigned n = op - 0x7f; // 1..16
        if (stack.size() < n) throw std::runtime_error("stack underflow");
        stack.push_back(stack[stack.size() - n]);
        break;
      }
      case 0x90 ... 0x9f: { // SWAP1 through SWAP16
        unsigned n = op - 0x8f; // 1..16
        if (stack.size() <= n) throw std::runtime_error("stack underflow");
        std::swap(stack[stack.size() - 1], stack[stack.size() - 1 - n]);
        break;
      }
      case 0xa0: { // TRANSFER
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 dest_id = pop_num();
        uint256 amount = pop_num();
        auto it = id_map.find(dest_id.convert_to<uint64_t>());
        if (it != id_map.end())
          transfer(self, it->second, std::to_string(amount.convert_to<uint64_t>()), contract.owner);
        break;
      }
      case 0xa1: { // LOG
        if (stack.empty()) throw std::runtime_error("stack underflow");
        Value value = pop_value();
        if (!value.is_string) contract.logs.push_back(value.num);
        break;
      }
      case 0xa2: // LOG2
      case 0xa3: // LOG3
      case 0xa4: { // LOG4
        if (stack.empty()) throw std::runtime_error("stack underflow");
        Value value = pop_value();
        if (!value.is_string) contract.logs.push_back(value.num);
        break;
      }
      case 0xff: { // SELFDESTRUCT
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 dest_id = pop_num();
        auto it = id_map.find(dest_id.convert_to<uint64_t>());
        if (it != id_map.end())
          destroy(self, it->second, contract.owner);
        return 0;
      }
      case 0x5f: { // PUSH0
        push_num(0);
        break;
      }
      case 0x60 ... 0x7f: { // PUSH1 through PUSH32
        unsigned push_bytes = op - 0x5f;
        if (pc + push_bytes > code.size()) throw std::runtime_error("unexpected EOF");
        uint256 v = 0;
        for (unsigned i = 0; i < push_bytes; ++i) {
          v = (v << 8) | code[pc++];
        }
        push_num(v);
        break;
      }
      case 0xf0: { // CREATE
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 value = pop_num();
        uint256 offset = pop_num();
        uint256 size = pop_num();
        std::vector<uint8_t> bytecode;
        for (uint64_t i = 0; i < size.convert_to<uint64_t>(); ++i)
        {
          Value mv = memory[(offset + i).convert_to<uint64_t>()];
          uint256 b = mv.is_string ? 0 : mv.num;
          bytecode.push_back(b.convert_to<uint8_t>());
        }
        std::string addr = deploy(contract.owner, bytecode);
        contracts[addr].balance += value.convert_to<uint64_t>();
        contract.balance -= value.convert_to<uint64_t>();
        push_num(contracts[addr].id);
        break;
      }
      case 0xf1: // CALL
      case 0xf2: // CALLCODE
      case 0xf4: // DELEGATECALL
      case 0xfa: { // STATICCALL
        if (stack.size() < 7) throw std::runtime_error("stack underflow");
        uint256 to = pop_num();
        uint256 value = pop_num();
        uint256 in_off = pop_num();
        uint256 in_size = pop_num();
        uint256 out_off = pop_num();
        uint256 out_size = pop_num();
        auto it = id_map.find(to.convert_to<uint64_t>());
        if (it == id_map.end()) { push_num(0); break; }
        std::vector<uint8_t> data;
        for (uint64_t i = 0; i < in_size.convert_to<uint64_t>(); ++i)
        {
          Value mv = memory[(in_off + i).convert_to<uint64_t>()];
          uint256 b = mv.is_string ? 0 : mv.num;
          data.push_back(b.convert_to<uint8_t>());
        }
        int64_t ret = call(it->second, data, block_height, timestamp, self, value.convert_to<uint64_t>());
        uint256 r = static_cast<uint256>(ret >= 0 ? ret : 0);
        last_return_data.resize(32);
        for (int i = 31; i >= 0; --i)
        {
          last_return_data[i] = (r & 0xff).convert_to<uint8_t>();
          r >>= 8;
        }
        for (uint64_t i = 0; i < out_size.convert_to<uint64_t>() && i < last_return_data.size(); ++i)
          memory[(out_off + i).convert_to<uint64_t>()] = Value(last_return_data[i]);
        push_num(ret >= 0 ? 1 : 0);
        break;
      }
      case 0xf5: { // CREATE2
        if (stack.size() < 4) throw std::runtime_error("stack underflow");
        uint256 value = pop_num();
        uint256 offset = pop_num();
        uint256 size = pop_num();
        pop_num(); // salt (ignored)
        std::vector<uint8_t> bytecode;
        for (uint64_t i = 0; i < size.convert_to<uint64_t>(); ++i)
        {
          Value mv = memory[(offset + i).convert_to<uint64_t>()];
          uint256 b = mv.is_string ? 0 : mv.num;
          bytecode.push_back(b.convert_to<uint8_t>());
        }
        std::string addr = deploy(contract.owner, bytecode);
        contracts[addr].balance += value.convert_to<uint64_t>();
        contract.balance -= value.convert_to<uint64_t>();
        push_num(contracts[addr].id);
        break;
      }
      case 0xfd: { // REVERT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        pop_value(); // size
        pop_value(); // offset
        MWARNING("EVM REVERT at pc with stack size " << stack.size());
        return -1;
      }
      case 0xfe: { // INVALID
        return -1;
      }
      case 0xf3: { // RETURN
        if (stack.empty())
          return 0;
        if (stack.size() == 1) {
          Value v = stack.back();
          if (v.is_string) return 0;
          last_return_data.resize(32);
          uint256 r = v.num;
          for (int i = 31; i >= 0; --i)
          {
            last_return_data[i] = (r & 0xff).convert_to<uint8_t>();
            r >>= 8;
          }
          return static_cast<int64_t>(v.num);
        }
        uint256 offset = pop_num();
        pop_value(); // size
        Value mv = memory[static_cast<uint64_t>(offset)];
        if (mv.is_string) return 0;
        last_return_data.resize(32);
        uint256 r = mv.num;
        for (int i = 31; i >= 0; --i)
        {
          last_return_data[i] = (r & 0xff).convert_to<uint8_t>();
          r >>= 8;
        }
        return mv.num.convert_to<int64_t>();
      }
      default:
        MWARNING("EVM unsupported opcode 0x" << std::hex << int(op) << std::dec);
        throw std::runtime_error("unsupported opcode");
    }
  }
  if (stack.empty())
    return 0;
  if (stack.back().is_string)
    return 0;
  return static_cast<int64_t>(stack.back().num);
}

bool EVM::save(const std::string& path) const
{
  State state;
  state.contracts = contracts;
  state.next_id = next_id;
  state.id_map = id_map;
  state.smart_map = smart_map;
  return tools::serialize_obj_to_file(state, path);
}

bool EVM::load(const std::string& path)
{
  State state;
  if (!::boost::filesystem::exists(path))
    return true;
  if (!tools::unserialize_obj_from_file(state, path))
    return false;
  contracts = std::move(state.contracts);
  next_id = state.next_id;
  id_map = std::move(state.id_map);
  smart_map = std::move(state.smart_map);
  return true;
}

} // namespace CryptoNote
