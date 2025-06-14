#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>
#include <boost/serialization/vector.hpp>
#include <boost/serialization/unordered_map.hpp>
#include <boost/serialization/string.hpp>

namespace CryptoNote {

class EVM {
public:
  struct Contract {
    std::vector<uint8_t> code;
    uint64_t balance = 0;
    std::string owner;
    std::unordered_map<uint64_t, uint64_t> storage;
    std::vector<uint64_t> logs;
    uint64_t id = 0;

    template<class Archive>
    void serialize(Archive& ar, const unsigned int /*version*/)
    {
      ar & code;
      ar & balance;
      ar & owner;
      ar & storage;
      ar & logs;
      ar & id;
    }
  };

  const std::unordered_map<std::string, Contract>& get_contracts() const { return contracts; }
  void set_state(const std::unordered_map<std::string, Contract>& c, uint64_t id) { contracts = c; next_id = id; rebuild_id_map(); }

  std::string deploy(const std::string& owner, const std::vector<uint8_t>& bytecode);
  int64_t call(const std::string& address, const std::vector<uint8_t>& input,
               uint64_t block_height = 0, uint64_t timestamp = 0);
  bool transfer(const std::string& from, const std::string& to, uint64_t amount, const std::string& caller);
  bool destroy(const std::string& address, const std::string& dest, const std::string& caller);
  bool deposit(const std::string& address, uint64_t amount);
  bool transfer_owner(const std::string& address, const std::string& new_owner, const std::string& caller);
  uint64_t balance_of(const std::string& address) const;
  bool is_owner(const std::string& contract, const std::string& address) const;
  std::string owner_of(const std::string& address) const;
  uint64_t storage_at(const std::string& address, uint64_t key) const;
  const std::vector<uint64_t>& logs_of(const std::string& address) const;
  const std::vector<uint8_t>& code_of(const std::string& address) const;
  std::vector<std::string> contracts_of_owner(const std::string& owner) const;
  std::vector<std::string> all_addresses() const;
  bool save(const std::string& path) const;
  bool load(const std::string& path);
  void rebuild_id_map();

private:
  struct State {
    std::unordered_map<std::string, Contract> contracts;
    uint64_t next_id = 0;
    std::unordered_map<uint64_t, std::string> id_map;

    template<class Archive>
    void serialize(Archive& ar, const unsigned int /*version*/)
    {
      ar & contracts;
      ar & next_id;
      ar & id_map;
    }
  };

  int64_t execute(const std::string& self, Contract& c, const std::vector<uint8_t>& input,
                  uint64_t block_height, uint64_t timestamp);

  std::unordered_map<std::string, Contract> contracts;
  std::unordered_map<uint64_t, std::string> id_map;
  uint64_t next_id = 0;
};

} // namespace CryptoNote
