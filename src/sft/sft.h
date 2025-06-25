#ifndef SFT_H
#define SFT_H

#include <string>
#include <vector>
#include <unordered_map>
#include <boost/serialization/serialization.hpp>
// #define BOOST_SERIALIZATION_VERSION_HPP
#include <boost/serialization/version.hpp>
#include <boost/serialization/library_version_type.hpp>
#include <boost/serialization/string.hpp>
#include <boost/serialization/vector.hpp>
#include <boost/serialization/unordered_map.hpp>

enum class sft_op_type : uint8_t {
    create = 0,
    transfer = 1,
    approve = 2,
    transfer_from = 3,
    set_fee = 4,
    burn = 5,
    mint = 6,
    transfer_ownership = 7,
    mint_id = 8,
    transfer_id = 9,
    approve_id = 10,
    transfer_from_id = 11,
    set_uri = 12
};

struct sft_unit {
    uint64_t total_supply = 0;
    std::unordered_map<std::string, uint64_t> balances;
    std::unordered_map<std::string, std::unordered_map<std::string, uint64_t>> allowances;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & total_supply;
        a & balances;
        a & allowances;
    }
};

struct sft_info {
    std::string name;
    std::string symbol;
    std::string address;
    std::string creator;
    uint64_t creator_fee = 0;
    std::string base_uri;
    std::unordered_map<uint64_t, sft_unit> ids;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & name;
        a & symbol;
        a & address;
        a & creator;
        a & creator_fee;
        a & base_uri;
        a & ids;
    }
};

struct sft_transfer_record {
    std::string token_address;
    std::string from;
    std::string to;
    uint64_t id = 0;
    uint64_t amount = 0;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & token_address;
        a & from;
        a & to;
        a & amount;
        a & id;
    }
};

struct sft_store_data
{
    std::unordered_map<std::string, sft_info> tokens;
    std::vector<sft_transfer_record> transfers;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & tokens;
        a & transfers;
    }
};

class sft_store {
public:
    bool load(const std::string &file);
    bool save(const std::string &file);
    bool load_from_string(const std::string &blob);
    bool merge_from_string(const std::string &blob);
    bool store_to_string(std::string &blob) const;

    const sft_info *get(const std::string &name) const;
    sft_info *get(const std::string &name);
    const sft_info *get_by_address(const std::string &address) const;
    sft_info *get_by_address(const std::string &address);

    sft_info &create(const std::string &name, const std::string &symbol,
                     const std::string &creator, const std::string &base_uri,
                     uint64_t creator_fee = 0,
                     const std::string &address = std::string());

    void list_all(std::vector<sft_info> &out) const;
    void list_by_creator(const std::string &creator, std::vector<sft_info> &out) const;

    bool transfer(const std::string &name, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_by_address(const std::string &address, const std::string &from, const std::string &to, uint64_t amount);
    bool approve(const std::string &name, const std::string &owner, const std::string &spender, uint64_t amount, const std::string &caller);
    bool transfer_from(const std::string &name, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_from_by_address(const std::string &address, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    uint64_t balance_of(const std::string &name, const std::string &account) const;
    uint64_t balance_of_by_address(const std::string &address, const std::string &account) const;
    uint64_t allowance_of(const std::string &name, const std::string &owner, const std::string &spender) const;

    bool approve_id(const std::string &address, uint64_t id, const std::string &owner, const std::string &spender, uint64_t amount, const std::string &caller);
    bool transfer_id_by_address(const std::string &address, uint64_t id, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_from_id_by_address(const std::string &address, uint64_t id, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    uint64_t balance_of_id(const std::string &address, uint64_t id, const std::string &account) const;

    bool burn(const std::string &address, const std::string &owner, uint64_t amount);
    bool mint(const std::string &address, const std::string &creator, uint64_t amount);
    bool mint_id(const std::string &address, const std::string &creator, uint64_t id, uint64_t amount);

    bool set_creator_fee(const std::string &address, const std::string &creator, uint64_t fee);
    bool set_uri(const std::string &address, const std::string &creator, const std::string &uri);
    std::string uri(const std::string &address, uint64_t id) const;

    bool transfer_ownership(const std::string &address, const std::string &creator, const std::string &new_owner);

    void history_by_token(const std::string &token_address, std::vector<sft_transfer_record> &out) const;
    void history_by_account(const std::string &account, std::vector<sft_transfer_record> &out) const;
    void history_by_token_account(const std::string &token_address, const std::string &account, std::vector<sft_transfer_record> &out) const;

    size_t size() const { return tokens.size(); }

private:
    std::unordered_map<std::string, sft_info> tokens;
    std::unordered_map<std::string, std::string> address_index;
    std::unordered_map<std::string, std::vector<std::string>> creator_tokens;
    std::vector<sft_transfer_record> transfer_history;

    void rebuild_indexes();
    void record_transfer(const std::string &token_address, const std::string &from, const std::string &to, uint64_t id, uint64_t amount);
};

#include "crypto/crypto.h"

std::string make_sft_extra(sft_op_type op, const std::vector<std::string> &fields);
std::string make_signed_sft_extra(sft_op_type op, const std::vector<std::string> &fields,
                                  const crypto::public_key &pub, const crypto::secret_key &sec);
bool parse_sft_extra(const std::string &data, sft_op_type &op, std::vector<std::string> &fields,
                     crypto::signature &sig, bool &has_sig);
bool verify_sft_extra(sft_op_type op, const std::vector<std::string> &fields,
                      const crypto::public_key &pub, const crypto::signature &sig);

#endif // SFT_H
