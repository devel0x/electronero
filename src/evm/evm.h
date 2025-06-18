#pragma once

#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>
#include <boost/multiprecision/cpp_int.hpp>
#include <boost/serialization/vector.hpp>
#include <boost/serialization/unordered_map.hpp>
#include <boost/serialization/string.hpp>
#include <boost/multiprecision/cpp_int.hpp>
#include <boost/serialization/split_free.hpp>
#include "cryptonote_basic/cryptonote_boost_serialization.h"
#include "crypto/crypto.h"
#include "cryptonote_basic/account.h"
#include "memwipe.h"

namespace mp = boost::multiprecision;

namespace CryptoNote {

using uint256 = boost::multiprecision::uint256_t;
using int256 = boost::multiprecision::int256_t;

namespace detail {
  template<class Archive>
  void save(Archive& ar, const uint256& v)
  {
    std::string s = v.convert_to<std::string>();
    ar & s;
  }

  template<class Archive>
  void load(Archive& ar, uint256& v)
  {
    std::string s;
    ar & s;
    v = uint256(s);
  }
}

template<class Archive>
void serialize(Archive& ar, uint256& v, const unsigned int)
{
  boost::serialization::split_free(ar, v, 0);
}

namespace boost { namespace serialization {
template<class Archive>
void save(Archive& ar, const CryptoNote::uint256& v, const unsigned int)
{
  CryptoNote::detail::save(ar, v);
}

template<class Archive>
void load(Archive& ar, CryptoNote::uint256& v, const unsigned int)
{
  CryptoNote::detail::load(ar, v);
}
} }

class EVM {
public:
  struct Contract {
    std::vector<uint8_t> code;
    uint64_t balance = 0;
    std::string owner;
    std::unordered_map<uint256, uint256> storage;
    std::vector<uint256> logs;
    uint64_t id = 0;
    crypto::hash secret_enc;

    template<class Archive>
    void serialize(Archive& ar, const unsigned int /*version*/)
    {
      ar & code;
      ar & balance;
      ar & owner;
      ar & storage;
      ar & logs;
      ar & id;
      ar & secret_enc;
    }
  };

  const std::unordered_map<std::string, Contract>& get_contracts() const { return contracts; }
  void set_state(const std::unordered_map<std::string, Contract>& c, uint64_t id) { contracts = c; next_id = id; rebuild_id_map(); }

  std::string deploy(const std::string& owner, const std::vector<uint8_t>& bytecode);
  int64_t call(const std::string& address, const std::vector<uint8_t>& input,
               uint64_t block_height = 0, uint64_t timestamp = 0,
               const std::string& caller = std::string(), uint64_t call_value = 0);
  bool transfer(const std::string& from, const std::string& to, const std::string& amount, const std::string& caller);
  bool destroy(const std::string& address, const std::string& dest, const std::string& caller);
  bool deposit(const std::string& address, const std::string& amount);
  bool transfer_owner(const std::string& address, const std::string& new_owner, const std::string& caller);
  uint64_t balance_of(const std::string& address) const;
  bool is_owner(const std::string& contract, const std::string& address) const;
  std::string owner_of(const std::string& address) const;
  uint256 storage_at(const std::string& address, uint256 key) const;
  const std::vector<uint256>& logs_of(const std::string& address) const;
  const std::vector<uint8_t>& code_of(const std::string& address) const;
  cryptonote::account_public_address deposit_address(const std::string& address) const;
  std::vector<std::string> contracts_of_owner(const std::string& owner) const;
  std::vector<std::string> all_addresses() const;
  bool save(const std::string& path) const;
  bool load(const std::string& path);
  void rebuild_id_map();

  bool get_contract_keys(const std::string& address, crypto::secret_key &spend, crypto::secret_key &view) const;

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
                  uint64_t block_height, uint64_t timestamp,
                  const std::string& caller, uint64_t call_value);

  std::unordered_map<std::string, Contract> contracts;
  std::unordered_map<uint64_t, std::string> id_map;
  uint64_t next_id = 0;
};

} // namespace CryptoNote
