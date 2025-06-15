#include "evm.h"

#include <stdexcept>
#include "misc_log_ex.h"
#include "common/boost_serialization_helper.h"
#include <boost/filesystem.hpp>

#include <unordered_map>
#include <ctime>
#include "cryptonote_config.h"
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

const std::vector<uint64_t>& EVM::logs_of(const std::string& address) const
{
  static const std::vector<uint64_t> empty;
  auto it = contracts.find(address);
  return it == contracts.end() ? empty : it->second.logs;
}

const std::vector<uint8_t>& EVM::code_of(const std::string& address) const
{
  static const std::vector<uint8_t> empty;
  auto it = contracts.find(address);
  return it == contracts.end() ? empty : it->second.code;
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

uint64_t EVM::storage_at(const std::string& address, uint64_t key) const
{
  auto it = contracts.find(address);
  if (it == contracts.end())
    return 0;
  auto jt = it->second.storage.find(key);
  return jt == it->second.storage.end() ? 0 : jt->second;
}

int64_t EVM::call(const std::string& address, const std::vector<uint8_t>& input,
                  uint64_t block_height, uint64_t timestamp) {
  auto it = contracts.find(address);
  if (it == contracts.end()) {
    return 0;
  }
  return execute(address, it->second, input, block_height, timestamp);
}

int64_t EVM::execute(const std::string& self, Contract& contract, const std::vector<uint8_t>& input,
                     uint64_t block_height, uint64_t timestamp) {
  std::vector<uint64_t> stack;
  std::unordered_map<uint64_t, uint64_t> memory;
  const auto& code = contract.code;
  for (size_t pc = 0; pc < code.size();) {
    uint8_t op = code[pc++];
    switch (op) {
      case 0x00: // STOP
        return stack.empty() ? 0 : static_cast<int64_t>(stack.back());
      case 0x01: { // ADD
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t b = stack.back(); stack.pop_back();
        uint64_t a = stack.back(); stack.pop_back();
        stack.push_back(a + b);
        break;
      }
      case 0x02: { // MUL
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t b = stack.back(); stack.pop_back();
        uint64_t a = stack.back(); stack.pop_back();
        stack.push_back(a * b);
        break;
      }
      case 0x03: { // SUB
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t b = stack.back(); stack.pop_back();
        uint64_t a = stack.back(); stack.pop_back();
        stack.push_back(a - b);
        break;
      }
      case 0x04: { // DIV
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t b = stack.back(); stack.pop_back();
        uint64_t a = stack.back(); stack.pop_back();
        stack.push_back(b == 0 ? 0 : a / b);
        break;
      }
      case 0x35: { // CALLDATALOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint64_t off = stack.back(); stack.pop_back();
        uint64_t v = 0;
        for (unsigned i = 0; i < 8 && off < input.size(); ++i, ++off) {
          v = (v << 8) | input[off];
        }
        stack.push_back(v);
        break;
      }
      case 0x36: { // CALLDATASIZE
        stack.push_back(input.size());
        break;
      }
      case 0x30: { // ADDRESS
        // push the current contract id onto the stack
        stack.push_back(contract.id);
        break;
      }
      case 0x31: { // BALANCE
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint64_t id = stack.back(); stack.pop_back();
        auto it = id_map.find(id);
        if (it == id_map.end()) { stack.push_back(0); break; }
        stack.push_back(balance_of(it->second));
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
      case 0x51: { // MLOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint64_t offset = stack.back(); stack.pop_back();
        stack.push_back(memory[offset]);
        break;
      }
      case 0x52: { // MSTORE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t offset = stack.back(); stack.pop_back();
        uint64_t value = stack.back(); stack.pop_back();
        memory[offset] = value;
        break;
      }
      case 0x54: { // SLOAD
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint64_t key = stack.back(); stack.pop_back();
        stack.push_back(contract.storage[key]);
        break;
      }
      case 0x55: { // SSTORE
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t key = stack.back(); stack.pop_back();
        uint64_t value = stack.back(); stack.pop_back();
        contract.storage[key] = value;
        break;
      }
      case 0xa0: { // TRANSFER
        if (stack.size() < 2) throw std::runtime_error("stack underflow");
        uint64_t dest_id = stack.back(); stack.pop_back();
        uint64_t amount = stack.back(); stack.pop_back();
        auto it = id_map.find(dest_id);
        if (it != id_map.end())
          transfer(self, it->second, amount, contract.owner);
        break;
      }
      case 0xa1: { // LOG
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint64_t value = stack.back(); stack.pop_back();
        contract.logs.push_back(value);
        break;
      }
      case 0xff: { // SELFDESTRUCT
        if (stack.empty()) throw std::runtime_error("stack underflow");
        uint64_t dest_id = stack.back(); stack.pop_back();
        auto it = id_map.find(dest_id);
        if (it != id_map.end())
          destroy(self, it->second, contract.owner);
        return 0;
      }
      case 0x60 ... 0x7f: { // PUSH1 through PUSH32
        unsigned push_bytes = op - 0x5f;
        if (pc + push_bytes > code.size()) throw std::runtime_error("unexpected EOF");
        uint64_t v = 0;
        for (unsigned i = 0; i < push_bytes; ++i) {
          v = (v << 8) | code[pc++];
        }
        stack.push_back(v);
        break;
      }
      case 0xfd: // REVERT
        return -1;
      case 0xf3: { // RETURN
        return stack.empty() ? 0 : static_cast<int64_t>(stack.back());
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
  if (!boost::filesystem::exists(path))
    return true;
  if (!tools::unserialize_obj_from_file(state, path))
    return false;
  contracts = std::move(state.contracts);
  next_id = state.next_id;
  id_map = std::move(state.id_map);
  return true;
}

} // namespace CryptoNote
