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
  bool transfer(const std::string& from, const std::string& to, uint64_t amount, const std::string& caller);
  bool deposit(const std::string& address, uint64_t amount);
  uint64_t balance_of(const std::string& address) const;
  bool is_owner(const std::string& contract, const std::string& address) const;

private:
  struct Contract {
    std::vector<uint8_t> code;
    uint64_t balance = 0;
    std::string owner;
    std::unordered_map<uint64_t, uint64_t> storage;
  };

  int64_t execute(Contract& c, const std::vector<uint8_t>& input);

  std::unordered_map<std::string, Contract> contracts;
  uint64_t next_id = 0;
};

} // namespace CryptoNote
