#include "evm.h"

#include <stdexcept>
#include "misc_log_ex.h"
#include "common/boost_serialization_helper.h"
#include <boost/filesystem.hpp>

#include <unordered_map>
#include <ctime>
#include <cstring>
#include "cryptonote_config.h"
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

bool EVM::deposit(const std::string& address, uint64_t amount)
{
  auto it = contracts.find(address);
  if (it == contracts.end()) return false;
  it->second.balance += amount;
  return true;
}

bool EVM::transfer(const std::string& from, const std::string& to, uint64_t amount, const std::string& caller)
{
  auto it_from = contracts.find(from);
  if (it_from == contracts.end() || it_from->second.balance < amount)
    return false;
  if (it_from->second.owner != caller)
    return false;
  it_from->second.balance -= amount;
  contracts[to].balance += amount;
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
  int64_t res = execute(address, it->second, input, block_height, timestamp, caller, call_value);
  MDEBUG("EVM::call result:" << res);
  return res;
}

int64_t EVM::execute(const std::string& self, Contract& contract, const std::vector<uint8_t>& input,
                     uint64_t block_height, uint64_t timestamp,
                     const std::string& caller, uint64_t call_value) {
  std::vector<uint256> stack;
  std::unordered_map<uint64_t, uint256> memory;
  const auto& code = contract.code;
  std::unordered_set<size_t> jumpdests;
  for (size_t i = 0; i < code.size(); ++i)
    if (code[i] == 0x5b)
      jumpdests.insert(i);

  for (size_t pc = 0; pc < code.size();) {
    uint8_t op = code[pc++];
    switch (op) {
      case 0x00: // STOP
        return stack.empty() ? 0 : static_cast<int64_t>(stack.back());
      case 0x01: { // ADD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a + b);
        break;
      }
      case 0x02: { // MUL
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a * b);
        break;
      }
      case 0x03: { // SUB
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a - b);
        break;
      }
      case 0x04: { // DIV
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(b == 0 ? 0 : a / b);
        break;
      }
      case 0x06: { // MOD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(b == 0 ? 0 : a % b);
        break;
      }
      case 0x07: { // SMOD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 b = static_cast<int256>(stack.back()); stack.pop_back();
        int256 a = static_cast<int256>(stack.back()); stack.pop_back();
        if (b == 0) stack.push_back(0);
        else stack.push_back(static_cast<uint256>(a % b));
        break;
      }
      case 0x05: { // SDIV
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 b = static_cast<int256>(stack.back()); stack.pop_back();
        int256 a = static_cast<int256>(stack.back()); stack.pop_back();
        stack.push_back(b == 0 ? 0 : static_cast<uint256>(a / b));
        break;
      }
      case 0x08: { // ADDMOD
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 c = stack.back(); stack.pop_back();
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(c == 0 ? 0 : (a + b) % c);
        break;
      }
      case 0x09: { // MULMOD
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 m = stack.back(); stack.pop_back();
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        if (m == 0) { stack.push_back(0); break; }
        stack.push_back((a * b) % m);
        break;
      }
      case 0x10: { // LT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a < b);
        break;
      }
      case 0x11: { // GT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a > b);
        break;
      }
      case 0x12: { // SLT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 b = static_cast<int256>(stack.back()); stack.pop_back();
        int256 a = static_cast<int256>(stack.back()); stack.pop_back();
        stack.push_back(a < b);
        break;
      }
      case 0x13: { // SGT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        int256 b = static_cast<int256>(stack.back()); stack.pop_back();
        int256 a = static_cast<int256>(stack.back()); stack.pop_back();
        stack.push_back(a > b);
        break;
      }
      case 0x14: { // EQ
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a == b);
        break;
      }
      case 0x15: { // ISZERO
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a == 0);
        break;
      }
      case 0x16: { // AND
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a & b);
        break;
      }
      case 0x17: { // OR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a | b);
        break;
      }
      case 0x18: { // XOR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 b = stack.back(); stack.pop_back();
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(a ^ b);
        break;
      }
      case 0x19: { // NOT
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 a = stack.back(); stack.pop_back();
        stack.push_back(~a);
        break;
      }
      case 0x1a: { // BYTE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 pos = stack.back(); stack.pop_back();
        uint256 word = stack.back(); stack.pop_back();
        unsigned int p = pos.convert_to<unsigned int>();
        if (p >= 32) stack.push_back(0);
        else stack.push_back((word >> ((31 - p) * 8)) & 0xff);
        break;
      }
      case 0x1b: { // SHL
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 shift = stack.back(); stack.pop_back();
        uint256 value = stack.back(); stack.pop_back();
        const unsigned s = shift.convert_to<unsigned>();
        stack.push_back(s >= 256 ? 0 : (value << s));
        break;
      }
      case 0x1c: { // SHR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 shift = stack.back(); stack.pop_back();
        uint256 value = stack.back(); stack.pop_back();
        const unsigned s = shift.convert_to<unsigned>();
        stack.push_back(s >= 256 ? 0 : (value >> s));
        break;
      }
      case 0x1d: { // SAR
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 shift = stack.back(); stack.pop_back();
        int256 value = static_cast<int256>(stack.back()); stack.pop_back();
        const unsigned s = shift.convert_to<unsigned>();
        if (s >= 256)
          stack.push_back(value < 0 ? static_cast<uint256>(-1) : 0);
        else
          stack.push_back(static_cast<uint256>(value >> s));
        break;
      }
      case 0x20: { // KECCAK256
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 offset = stack.back(); stack.pop_back();
        uint256 len = stack.back(); stack.pop_back();
        const uint64_t off = offset.convert_to<uint64_t>();
        const uint64_t l = len.convert_to<uint64_t>();
        std::vector<uint8_t> buf;
        buf.reserve(len.convert_to<size_t>());
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          uint256 v = memory[static_cast<uint64_t>((offset + i).convert_to<uint64_t>())];
          buf.push_back(v.convert_to<uint8_t>());
        }
        crypto::hash h;
        crypto::cn_fast_hash(buf.data(), buf.size(), h);
        uint256 v = 0;
        for (int i = 0; i < 32; ++i)
        {
          v <<= 8;
          v |= ((const unsigned char*)&h)[i];
        }
        stack.push_back(v);
        break;
      }
      case 0x34: { // CALLVALUE
        stack.push_back(call_value);
        break;
      }
      case 0x35: { // CALLDATALOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 off = stack.back(); stack.pop_back();
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
        stack.push_back(v);
        break;
      }
      case 0x36: { // CALLDATASIZE
        stack.push_back(input.size());
        break;
      }
      case 0x37: { // CALLDATACOPY
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 dest = stack.back(); stack.pop_back();
        uint256 src = stack.back(); stack.pop_back();
        uint256 len = stack.back(); stack.pop_back();
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          size_t pos = (src + i).convert_to<size_t>();
          uint256 b = pos < input.size() ? input[pos] : 0;
          memory[(dest + i).convert_to<uint64_t>()] = b;
        }
        break;
      }
      case 0x38: { // CODESIZE
        stack.push_back(code.size());
        break;
      }
      case 0x39: { // CODECOPY
        if (stack.size() < 3) throw std::runtime_error("stack underflow");
        uint256 dest = stack.back(); stack.pop_back();
        uint256 src = stack.back(); stack.pop_back();
        uint256 len = stack.back(); stack.pop_back();
        for (uint64_t i = 0; i < len.convert_to<uint64_t>(); ++i)
        {
          size_t pos = (src + i).convert_to<size_t>();
          uint256 b = pos < code.size() ? code[pos] : 0;
          memory[(dest + i).convert_to<uint64_t>()] = b;
        }
        break;
      }
      case 0x30: { // ADDRESS
        // push the current contract id onto the stack
        stack.push_back(contract.id);
        break;
      }
      case 0x31: { // BALANCE
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 id = stack.back(); stack.pop_back();
        auto it = id_map.find(id.convert_to<uint64_t>());
        if (it == id_map.end()) { stack.push_back(0); break; }
        stack.push_back(balance_of(it->second));
        break;
      }
      case 0x33: { // CALLER
        if (caller.empty())
        {
          stack.push_back(0);
        }
        else
        {
          auto itc = contracts.find(caller);
          if (itc != contracts.end())
          {
            stack.push_back(itc->second.id);
          }
          else
          {
            crypto::hash h = crypto::cn_fast_hash(caller.data(), caller.size());
            uint256 v = 0;
            for (int i = 0; i < 20; ++i)
            {
              v = (v << 8) | static_cast<uint8_t>(h.data[i]);
            }
            stack.push_back(v);
          }
        }
        break;
      }
      case 0x42: { // TIMESTAMP
        stack.push_back(timestamp);
        break;
      }
      case 0x43: { // NUMBER
        stack.push_back(block_height);
        break;
      }
      case 0x50: { // POP
        if (stack.empty()) throw std::runtime_error("stack underflow");
        stack.pop_back();
        break;
      }
      case 0x56: { // JUMP
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 dest = stack.back(); stack.pop_back();
        size_t d = dest.convert_to<size_t>();
        if (d >= code.size() || !jumpdests.count(d))
          throw std::runtime_error("bad jump dest");
        pc = d;
        break;
      }
      case 0x57: { // JUMPI
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 dest = stack.back(); stack.pop_back();
        uint256 cond = stack.back(); stack.pop_back();
        if (cond != 0) {
          size_t d = dest.convert_to<size_t>();
          if (d >= code.size() || !jumpdests.count(d))
            throw std::runtime_error("bad jump dest");
          pc = d;
        }
        break;
      }
      case 0x58: { // PC
        stack.push_back(pc - 1);
        break;
      }
      case 0x5a: { // GAS
        stack.push_back(0);
        break;
      }
      case 0x5b: { // JUMPDEST
        break;
      }
      case 0x51: { // MLOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 offset = stack.back(); stack.pop_back();
        stack.push_back(memory[static_cast<uint64_t>(offset)]);
        break;
      }
      case 0x52: { // MSTORE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 offset = stack.back(); stack.pop_back();
        uint256 value = stack.back(); stack.pop_back();
        memory[static_cast<uint64_t>(offset)] = value;
        break;
      }
      case 0x53: { // MSTORE8
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 offset = stack.back(); stack.pop_back();
        uint256 value = stack.back(); stack.pop_back();
        memory[static_cast<uint64_t>(offset)] = value & 0xff;
        break;
      }
      case 0x54: { // SLOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 key = stack.back(); stack.pop_back();
        stack.push_back(contract.storage[key]);
        break;
      }
      case 0x55: { // SSTORE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint256 key = stack.back(); stack.pop_back();
        uint256 value = stack.back(); stack.pop_back();
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
        uint256 dest_id = stack.back(); stack.pop_back();
        uint256 amount = stack.back(); stack.pop_back();
        auto it = id_map.find(dest_id.convert_to<uint64_t>());
        if (it != id_map.end())
          transfer(self, it->second, amount.convert_to<uint64_t>(), contract.owner);
        break;
      }
      case 0xa1: { // LOG
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 value = stack.back(); stack.pop_back();
        contract.logs.push_back(value);
        break;
      }
      case 0xa2: // LOG2
      case 0xa3: // LOG3
      case 0xa4: { // LOG4
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 value = stack.back(); stack.pop_back();
        contract.logs.push_back(value);
        break;
      }
      case 0xff: { // SELFDESTRUCT
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint256 dest_id = stack.back(); stack.pop_back();
        auto it = id_map.find(dest_id.convert_to<uint64_t>());
        if (it != id_map.end())
          destroy(self, it->second, contract.owner);
        return 0;
      }
      case 0x5f: { // PUSH0
        stack.push_back(0);
        break;
      }
      case 0x60 ... 0x7f: { // PUSH1 through PUSH32
        unsigned push_bytes = op - 0x5f;
        if (pc + push_bytes > code.size()) throw std::runtime_error("unexpected EOF");
        uint256 v = 0;
        for (unsigned i = 0; i < push_bytes; ++i) {
          v = (v << 8) | code[pc++];
        }
        stack.push_back(v);
        break;
      }
      case 0xfd: { // REVERT
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        stack.pop_back(); // size
        stack.pop_back(); // offset
        return -1;
      }
      case 0xf3: { // RETURN
        if (stack.empty())
          return 0;
        if (stack.size() == 1)
          return static_cast<int64_t>(stack.back());
        uint256 offset = stack.back(); stack.pop_back();
        stack.pop_back(); // size
        return memory[static_cast<uint64_t>(offset)].convert_to<int64_t>();
      }
      default:
        throw std::runtime_error("unsupported opcode");
    }
  }
  return stack.empty() ? 0 : static_cast<int64_t>(stack.back());
}

bool EVM::save(const std::string& path) const
{
  State state;
  state.contracts = contracts;
  state.next_id = next_id;
  state.id_map = id_map;
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
  return true;
}

} // namespace CryptoNote
