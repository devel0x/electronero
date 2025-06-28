#include "token_marketplace.h"
#include "misc_log_ex.h"
#include <fstream>
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>

#undef MONERO_DEFAULT_LOG_CATEGORY
#define MONERO_DEFAULT_LOG_CATEGORY "wallet.token.market"

std::string token_marketplace::pair_key(const std::string &token, const std::string &coin) const
{
    return token + ":" + coin;
}

token_marketplace::token_marketplace(token_store &store, const std::string &market_address)
  : m_tokens(store), m_address(market_address)
{
}

bool token_marketplace::load(const std::string &file)
{
    std::ifstream ifs(file, std::ios::binary);
    if(!ifs)
        return false;
    try
    {
        boost::archive::binary_iarchive ia(ifs);
        marketplace_data data;
        ia >> data;
        m_next_id = data.next_id;
        m_orders = std::move(data.orders);
        m_pair_index = std::move(data.pair_index);
        m_pairs = std::move(data.pairs);
        m_pair_exists = std::move(data.pair_exists);
    }
    catch(const std::exception &e)
    {
        MERROR("Failed to load marketplace " << file << ": " << e.what());
        return false;
    }
    return true;
}

bool token_marketplace::save(const std::string &file) const
{
    std::ofstream ofs(file, std::ios::binary | std::ios::trunc);
    if(!ofs)
        return false;
    try
    {
        boost::archive::binary_oarchive oa(ofs);
        marketplace_data data{m_next_id, m_orders, m_pair_index, m_pairs, m_pair_exists};
        oa << data;
    }
    catch(const std::exception &e)
    {
        MERROR("Failed to save marketplace " << file << ": " << e.what());
        return false;
    }
    return true;
}

std::string make_marketplace_extra(marketplace_op_type op, const std::vector<std::string> &fields)
{
    std::ostringstream oss;
    oss << static_cast<int>(op);
    for(const auto &f : fields)
        oss << '\t' << f;
    return oss.str();
}

bool parse_marketplace_extra(const std::string &data, marketplace_op_type &op, std::vector<std::string> &fields)
{
    std::istringstream iss(data);
    int op_int;
    if(!(iss >> op_int))
        return false;
    op = static_cast<marketplace_op_type>(op_int);
    if (iss.peek() == '\t')
        iss.get();
    std::string field;
    while(std::getline(iss, field, '\t'))
        fields.push_back(field);
    return true;
}

uint64_t token_marketplace::place_sell_order(const std::string &seller, const std::string &token,
                                            const std::string &coin, uint64_t amount,
                                            uint64_t price)
{
    if (amount == 0 || price == 0)
        throw std::runtime_error("invalid amount or price");
    if (!m_tokens.transfer_by_address(token, seller, m_address, amount))
        throw std::runtime_error("token transfer failed");
    uint64_t id = m_next_id++;
    market_order ord{id, seller, token, coin, price, amount};
    m_orders[id] = ord;
    std::string key = pair_key(token, coin);
    m_pair_index[key].push_back(id);
    if (!m_pair_exists[key])
    {
        m_pair_exists[key] = true;
        m_pairs.push_back({token, coin});
    }
    return id;
}

bool token_marketplace::cancel_sell_order(uint64_t order_id)
{
    auto it = m_orders.find(order_id);
    if (it == m_orders.end())
        return false;
    market_order &ord = it->second;
    if (ord.remaining == 0)
        return false;
    if (!m_tokens.transfer_by_address(ord.token, m_address, ord.seller, ord.remaining))
        return false;
    ord.remaining = 0;
    return true;
}

bool token_marketplace::buy(uint64_t order_id, const std::string &buyer, uint64_t amount)
{
    auto it = m_orders.find(order_id);
    if (it == m_orders.end())
        return false;
    market_order &ord = it->second;
    if (amount == 0 || amount > ord.remaining)
        return false;
    if (!m_tokens.transfer_by_address(ord.token, m_address, buyer, amount))
        return false;
    ord.remaining -= amount;
    return true;
}

void token_marketplace::list_pairs(std::vector<market_pair> &out) const
{
    out = m_pairs;
}

void token_marketplace::list_orders(const std::string &token, const std::string &coin,
                                   std::vector<market_order> &out) const
{
    std::string key = pair_key(token, coin);
    auto it = m_pair_index.find(key);
    if (it == m_pair_index.end())
        return;
    for (uint64_t id : it->second)
    {
        auto oit = m_orders.find(id);
        if (oit != m_orders.end() && oit->second.remaining > 0)
            out.push_back(oit->second);
    }
}
