#include "evm.h"

#include <stdexcept>

namespace CryptoNote {

std::string EVM::deploy(const std::string& owner, const std::vector<uint8_t>& bytecode) {
  std::string address = "c" + std::to_string(++next_id);
  contracts[address].code = bytecode;
  return address;
}

bool EVM::deposit(const std::string& address, uint64_t amount)
{
  auto it = contracts.find(address);
  if (it == contracts.end()) return false;
  it->second.balance += amount;
  return true;
}

bool EVM::transfer(const std::string& from, const std::string& to, uint64_t amount)
{
  auto it_from = contracts.find(from);
  if (it_from == contracts.end() || it_from->second.balance < amount)
    return false;
  it_from->second.balance -= amount;
  contracts[to].balance += amount;
  return true;
}

uint64_t EVM::balance_of(const std::string& address) const
{
  auto it = contracts.find(address);
  return it == contracts.end() ? 0 : it->second.balance;
}

int64_t EVM::call(const std::string& address, const std::vector<uint8_t>& input) {
  auto it = contracts.find(address);
  if (it == contracts.end()) {
    return 0;
  }
  return execute(it->second.code, input);
}

int64_t EVM::execute(const std::vector<uint8_t>& code, const std::vector<uint8_t>& /*input*/) const {
  std::vector<uint64_t> stack;
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
      case 0x60: { // PUSH1
        if (pc >= code.size()) throw std::runtime_error("unexpected EOF");
        stack.push_back(code[pc++]);
        break;
      }
      case 0xf3: { // RETURN
        return stack.empty() ? 0 : static_cast<int64_t>(stack.back());
      }
      default:
        throw std::runtime_error("unsupported opcode");
    }
  }
  return stack.empty() ? 0 : static_cast<int64_t>(stack.back());
}

} // namespace CryptoNote
