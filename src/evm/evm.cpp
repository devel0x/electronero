#include "evm.h"

#include <stdexcept>

namespace CryptoNote {

void EVM::deploy(const std::string& account, const std::vector<uint8_t>& bytecode) {
  contracts[account] = bytecode;
}

int64_t EVM::call(const std::string& account, const std::vector<uint8_t>& input) const {
  auto it = contracts.find(account);
  if (it == contracts.end()) {
    return 0;
  }
  return execute(it->second, input);
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
