#ifndef TOKEN_MARKETPLACE_H
#define TOKEN_MARKETPLACE_H

#include <string>
#include <vector>
#include <unordered_map>
#include <boost/serialization/serialization.hpp>
#include <boost/serialization/vector.hpp>
#include <boost/serialization/unordered_map.hpp>
#include "token.h"

struct market_order
{
    uint64_t id = 0;
    std::string seller;
    std::string token;
    std::string coin;
    uint64_t price = 0; // coins per token
    uint64_t remaining = 0;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/)
    {
        a & id;
        a & seller;
        a & token;
        a & coin;
        a & price;
        a & remaining;
    }
};

struct market_pair
{
    std::string token;
    std::string coin;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/)
    {
        a & token;
        a & coin;
    }
};

struct marketplace_data
{
    uint64_t next_id = 0;
    std::unordered_map<uint64_t, market_order> orders;
    std::unordered_map<std::string, std::vector<uint64_t>> pair_index;
    std::vector<market_pair> pairs;
    std::unordered_map<std::string, bool> pair_exists;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/)
    {
        a & next_id;
        a & orders;
        a & pair_index;
        a & pairs;
        a & pair_exists;
    }
};

enum class marketplace_op_type : uint8_t { place = 0, cancel = 1, buy = 2 };

std::string make_marketplace_extra(marketplace_op_type op, const std::vector<std::string> &fields);
bool parse_marketplace_extra(const std::string &data, marketplace_op_type &op, std::vector<std::string> &fields);

class token_marketplace
{
public:
    token_marketplace(token_store &store, const std::string &market_address);

    bool load(const std::string &file);
    bool save(const std::string &file) const;

    uint64_t place_sell_order(const std::string &seller, const std::string &token,
                              const std::string &coin, uint64_t amount,
                              uint64_t price);

    bool cancel_sell_order(uint64_t order_id);

    bool buy(uint64_t order_id, const std::string &buyer, uint64_t amount);

    void list_pairs(std::vector<market_pair> &out) const;

    void list_orders(const std::string &token, const std::string &coin,
                     std::vector<market_order> &out) const;

private:
    token_store &m_tokens;
    std::string m_address;
    uint64_t m_next_id = 0;
    std::unordered_map<uint64_t, market_order> m_orders;
    std::unordered_map<std::string, std::vector<uint64_t>> m_pair_index;
    std::vector<market_pair> m_pairs;
    std::unordered_map<std::string, bool> m_pair_exists;

    std::string pair_key(const std::string &token, const std::string &coin) const;
};

#endif // TOKEN_MARKETPLACE_H
