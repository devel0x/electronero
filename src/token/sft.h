#ifndef SFT_H
#define SFT_H

#include <string>
#include <unordered_map>
#include <vector>
#include <boost/serialization/serialization.hpp>
#include <boost/serialization/string.hpp>
#include <boost/serialization/unordered_map.hpp>
#include <boost/serialization/vector.hpp>

enum class sft_op_type : uint8_t {
    create = 0,
    transfer = 1,
    mint = 2,
    burn = 3
};

struct sft_info {
    std::string name;
    std::string symbol;
    std::string address;
    std::string creator;
    uint64_t creator_fee = 0;
    std::unordered_map<uint64_t, uint64_t> total_supply;
    std::unordered_map<uint64_t, std::unordered_map<std::string, uint64_t>> balances;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & name;
        a & symbol;
        a & address;
        a & creator;
        a & creator_fee;
        a & total_supply;
        a & balances;
    }
};

struct sft_store_data {
    std::unordered_map<std::string, sft_info> tokens;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & tokens;
    }
};

class sft_store {
public:
    bool load(const std::string &file);
    bool save(const std::string &file);
    bool load_from_string(const std::string &blob);
    bool merge_from_string(const std::string &blob);
    bool store_to_string(std::string &blob) const;

    sft_info &create(const std::string &name, const std::string &symbol,
                     const std::vector<std::pair<uint64_t,uint64_t>> &id_supply,
                     const std::string &creator, uint64_t creator_fee = 0);

    const sft_info *get_by_address(const std::string &address) const;
    sft_info *get_by_address(const std::string &address);

    bool transfer(const std::string &address, uint64_t id,
                  const std::string &from, const std::string &to, uint64_t amount);
    bool mint(const std::string &address, uint64_t id,
              const std::string &creator, uint64_t amount);
    bool burn(const std::string &address, uint64_t id,
              const std::string &owner, uint64_t amount);

private:
    std::unordered_map<std::string, sft_info> tokens;
    std::unordered_map<std::string, std::string> address_index;

    void rebuild_indexes();

public:
    void list_all(std::vector<sft_info> &out) const;
    uint64_t balance_of(const std::string &address, uint64_t id, const std::string &owner) const;
};

std::string make_sft_extra(sft_op_type op, const std::vector<std::string> &fields);
bool parse_sft_extra(const std::string &data, sft_op_type &op, std::vector<std::string> &fields);

#endif // SFT_H
