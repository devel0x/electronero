#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace CryptoNote {

class EVM {
public:
  std::string deploy(const std::string& owner, const std::vector<uint8_t>& bytecode);
  int64_t call(const std::string& address, const std::vector<uint8_t>& input);
  bool transfer(const std::string& from, const std::string& to, uint64_t amount);
  bool deposit(const std::string& address, uint64_t amount);
  uint64_t balance_of(const std::string& address) const;

private:
  int64_t execute(const std::vector<uint8_t>& code, const std::vector<uint8_t>& input) const;

  struct Contract {
    std::vector<uint8_t> code;
    uint64_t balance = 0;
  };

  std::unordered_map<std::string, Contract> contracts;
  uint64_t next_id = 0;
};

} // namespace CryptoNote
