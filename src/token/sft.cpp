#include "sft.h"
#include <fstream>
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>
#include <sstream>
#include "crypto/hash.h"
#include "crypto/crypto.h"
#include "string_tools.h"
#include "common/util.h"
#include "misc_log_ex.h"

#undef MONERO_DEFAULT_LOG_CATEGORY
#define MONERO_DEFAULT_LOG_CATEGORY "wallet.sft"

bool sft_store::load(const std::string &file)
{
    std::ifstream ifs(file, std::ios::binary);
    if(!ifs)
    {
        MERROR("Failed to open SFT store " << file);
        return false;
    }
    try
    {
        boost::archive::binary_iarchive ia(ifs);
        sft_store_data data;
        ia >> data;
        tokens = std::move(data.tokens);
        rebuild_indexes();
    }
    catch(const std::exception &e)
    {
        MERROR("Failed to load SFT store " << file << ": " << e.what());
        return false;
    }
    return true;
}

bool sft_store::save(const std::string &file)
{
    std::ofstream ofs(file, std::ios::binary | std::ios::trunc);
    if(!ofs)
    {
        MERROR("Failed to open SFT store for write: " << file);
        return false;
    }
    try
    {
        boost::archive::binary_oarchive oa(ofs);
        sft_store_data data{tokens};
        oa << data;
    }
    catch(const std::exception &e)
    {
        MERROR("Failed to save SFT store " << file << ": " << e.what());
        return false;
    }
    return true;
}

bool sft_store::load_from_string(const std::string &blob)
{
    std::istringstream iss(blob);
    boost::archive::binary_iarchive ia(iss);
    sft_store_data data;
    ia >> data;
    tokens = std::move(data.tokens);
    rebuild_indexes();
    return true;
}

bool sft_store::merge_from_string(const std::string &blob)
{
    std::istringstream iss(blob);
    boost::archive::binary_iarchive ia(iss);
    sft_store_data data;
    ia >> data;
    for(const auto &kv : data.tokens)
    {
        if(tokens.find(kv.first) == tokens.end())
            tokens.emplace(kv);
    }
    rebuild_indexes();
    return true;
}

bool sft_store::store_to_string(std::string &blob) const
{
    std::ostringstream oss;
    boost::archive::binary_oarchive oa(oss);
    sft_store_data data{tokens};
    oa << data;
    blob = oss.str();
    return true;
}

sft_info &sft_store::create(const std::string &name, const std::string &symbol,
                            const std::vector<std::pair<uint64_t,uint64_t>> &id_supply,
                            const std::string &creator, uint64_t creator_fee)
{
    auto &tok = tokens[name];
    tok.name = name;
    tok.symbol = symbol;
    tok.creator = creator;
    tok.creator_fee = creator_fee;
    for(const auto &p : id_supply)
    {
        tok.total_supply[p.first] = p.second;
        tok.balances[p.first][creator] = p.second;
    }
    uint64_t nonce = crypto::rand<uint64_t>();
    std::string data = creator + name + symbol + std::to_string(tokens.size()) + std::to_string(nonce);
    crypto::hash h;
    crypto::cn_fast_hash(data.data(), data.size(), h);
    std::string hex = epee::string_tools::pod_to_hex(h);
    tok.address = std::string("cSFT") + hex.substr(0, 46);
    address_index[tok.address] = name;
    return tok;
}

const sft_info *sft_store::get_by_address(const std::string &address) const
{
    auto it = address_index.find(address);
    if(it == address_index.end()) return nullptr;
    auto it2 = tokens.find(it->second);
    if(it2 == tokens.end()) return nullptr;
    return &it2->second;
}

sft_info *sft_store::get_by_address(const std::string &address)
{
    auto it = address_index.find(address);
    if(it == address_index.end()) return nullptr;
    auto it2 = tokens.find(it->second);
    if(it2 == tokens.end()) return nullptr;
    return &it2->second;
}

bool sft_store::transfer(const std::string &address, uint64_t id,
                         const std::string &from, const std::string &to, uint64_t amount)
{
    auto itn = address_index.find(address);
    if(itn == address_index.end()) return false;
    auto &tok = tokens[itn->second];
    auto fit = tok.balances[id].find(from);
    if(fit == tok.balances[id].end() || fit->second < amount) return false;
    fit->second -= amount;
    tok.balances[id][to] += amount;
    return true;
}

bool sft_store::mint(const std::string &address, uint64_t id,
                     const std::string &creator, uint64_t amount)
{
    auto itn = address_index.find(address);
    if(itn == address_index.end()) return false;
    auto &tok = tokens[itn->second];
    if(tok.creator != creator) return false;
    tok.total_supply[id] += amount;
    tok.balances[id][creator] += amount;
    return true;
}

bool sft_store::burn(const std::string &address, uint64_t id,
                     const std::string &owner, uint64_t amount)
{
    auto itn = address_index.find(address);
    if(itn == address_index.end()) return false;
    auto &tok = tokens[itn->second];
    auto it = tok.balances[id].find(owner);
    if(it == tok.balances[id].end() || it->second < amount) return false;
    it->second -= amount;
    tok.total_supply[id] -= amount;
    return true;
}

void sft_store::rebuild_indexes()
{
    address_index.clear();
    for(const auto &kv : tokens)
        address_index[kv.second.address] = kv.first;
}

void sft_store::list_all(std::vector<sft_info> &out) const
{
    for(const auto &kv : tokens)
        out.push_back(kv.second);
}

uint64_t sft_store::balance_of(const std::string &address, uint64_t id, const std::string &owner) const
{
    const sft_info *info = get_by_address(address);
    if(!info) return 0;
    auto itb = info->balances.find(id);
    if(itb == info->balances.end()) return 0;
    auto it = itb->second.find(owner);
    if(it == itb->second.end()) return 0;
    return it->second;
}

