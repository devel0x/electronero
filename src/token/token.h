#ifndef TOKEN_H
#define TOKEN_H

#include <string>
#include <vector>
#include <unordered_map>
#include <boost/serialization/serialization.hpp>
#include <boost/serialization/unordered_map.hpp>
#include <boost/serialization/string.hpp>

struct token_info {
    std::string name;
    std::string symbol;
    std::string address;
    std::string creator;
    uint64_t total_supply = 0;
    std::unordered_map<std::string, uint64_t> balances;
    std::unordered_map<std::string, std::unordered_map<std::string, uint64_t>> allowances;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & name;
        a & symbol;
        a & total_supply;
        a & address;
        a & creator;
        a & balances;
        a & allowances;
    }
};

class token_store {
public:
    bool load(const std::string &file);
    bool save(const std::string &file);
    bool load_from_string(const std::string &blob);
    bool store_to_string(std::string &blob) const;

    const token_info *get(const std::string &name) const;
    token_info *get(const std::string &name);
    const token_info *get_by_address(const std::string &address) const;
    token_info *get_by_address(const std::string &address);

    token_info &create(const std::string &name, const std::string &symbol, uint64_t supply, const std::string &creator);

    void list_all(std::vector<token_info> &out) const;
    void list_by_creator(const std::string &creator, std::vector<token_info> &out) const;

    bool transfer(const std::string &name, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_by_address(const std::string &address, const std::string &from, const std::string &to, uint64_t amount);
    bool approve(const std::string &name, const std::string &owner, const std::string &spender, uint64_t amount);
    bool transfer_from(const std::string &name, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_from_by_address(const std::string &address, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    uint64_t balance_of(const std::string &name, const std::string &account) const;
    uint64_t balance_of_by_address(const std::string &address, const std::string &account) const;
    uint64_t allowance_of(const std::string &name, const std::string &owner, const std::string &spender) const;

private:
    std::unordered_map<std::string, token_info> tokens;
    std::unordered_map<std::string, std::string> address_index;
    std::unordered_map<std::string, std::vector<std::string>> creator_tokens;

    void rebuild_indexes();
};

#endif // TOKEN_H
