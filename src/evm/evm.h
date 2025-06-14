#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

namespace CryptoNote {

class EVM {
public:
  void deploy(const std::string& account, const std::vector<uint8_t>& bytecode);
  int64_t call(const std::string& account, const std::vector<uint8_t>& input) const;

private:
  int64_t execute(const std::vector<uint8_t>& code, const std::vector<uint8_t>& input) const;

  std::unordered_map<std::string, std::vector<uint8_t>> contracts;
};

} // namespace CryptoNote
