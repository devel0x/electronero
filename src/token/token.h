#ifndef TOKEN_H
#define TOKEN_H

#include <string>
#include <unordered_map>
#include <boost/serialization/serialization.hpp>
#include <boost/serialization/unordered_map.hpp>
#include <boost/serialization/string.hpp>

struct token_info {
    std::string name;
    uint64_t total_supply = 0;
    std::unordered_map<std::string, uint64_t> balances;
    std::unordered_map<std::string, std::unordered_map<std::string, uint64_t>> allowances;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & name;
        a & total_supply;
        a & balances;
        a & allowances;
    }
};

class token_store {
public:
    bool load(const std::string &file);
    bool save(const std::string &file);

    token_info &create(const std::string &name, uint64_t supply, const std::string &creator);
    token_info *get(const std::string &name);

    bool transfer(const std::string &name, const std::string &from, const std::string &to, uint64_t amount);
    bool approve(const std::string &name, const std::string &owner, const std::string &spender, uint64_t amount);
    bool transfer_from(const std::string &name, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    uint64_t balance_of(const std::string &name, const std::string &account) const;
    uint64_t allowance_of(const std::string &name, const std::string &owner, const std::string &spender) const;

private:
    std::unordered_map<std::string, token_info> tokens;
};

#endif // TOKEN_H
