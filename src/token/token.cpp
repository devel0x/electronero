#include "token.h"
#include <fstream>
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>
#include <sstream>
#include "crypto/hash.h"
#include "crypto/crypto.h"
#include "string_tools.h"

bool token_store::load(const std::string &file) {
    std::ifstream ifs(file, std::ios::binary);
    if (!ifs)
        return false;
    boost::archive::binary_iarchive ia(ifs);
    ia >> tokens;
    rebuild_indexes();
    return true;
}

bool token_store::load_from_string(const std::string &blob) {
    std::istringstream iss(blob);
    boost::archive::binary_iarchive ia(iss);
    ia >> tokens;
    rebuild_indexes();
    return true;
}

bool token_store::save(const std::string &file) {
    std::ofstream ofs(file, std::ios::binary | std::ios::trunc);
    if (!ofs)
        return false;
    boost::archive::binary_oarchive oa(ofs);
    oa << tokens;
    return true;
}

bool token_store::store_to_string(std::string &blob) const {
    std::ostringstream oss;
    boost::archive::binary_oarchive oa(oss);
    oa << tokens;
    blob = oss.str();
    return true;
}

token_info &token_store::create(const std::string &name, const std::string &symbol, uint64_t supply, const std::string &creator) {
    auto &tok = tokens[name];
    tok.name = name;
    tok.symbol = symbol;
    tok.creator = creator;
    tok.total_supply = supply;
    tok.balances[creator] = supply;
    // incorporate some random bytes to ensure unique hash even when called repeatedly
    uint64_t nonce = crypto::rand<uint64_t>();
    std::string data = creator + name + symbol + std::to_string(tokens.size()) + std::to_string(nonce);
    crypto::hash h;
    crypto::cn_fast_hash(data.data(), data.size(), h);
    std::string hex = epee::string_tools::pod_to_hex(h);
    tok.address = std::string("cEVM") + hex.substr(0, 46);
    creator_tokens[creator].push_back(name);
    address_index[tok.address] = name;
    return tok;
}

token_info *token_store::get(const std::string &name) {
    auto it = tokens.find(name);
    if (it == tokens.end()) return nullptr;
    return &it->second;
}

const token_info *token_store::get(const std::string &name) const {
    auto it = tokens.find(name);
    if (it == tokens.end()) return nullptr;
    return &it->second;
}

token_info *token_store::get_by_address(const std::string &address) {
    auto itn = address_index.find(address);
    if (itn == address_index.end()) return nullptr;
    return get(itn->second);
}

const token_info *token_store::get_by_address(const std::string &address) const {
    auto itn = address_index.find(address);
    if (itn == address_index.end()) return nullptr;
    auto it = tokens.find(itn->second);
    if (it == tokens.end()) return nullptr;
    return &it->second;
}

bool token_store::transfer(const std::string &name, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get(name);
    if (!tok) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    fit->second -= amount;
    tok->balances[to] += amount;
    return true;
}

bool token_store::transfer_by_address(const std::string &address, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get_by_address(address);
    if (!tok) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    fit->second -= amount;
    tok->balances[to] += amount;
    return true;
}

bool token_store::approve(const std::string &name, const std::string &owner, const std::string &spender, uint64_t amount) {
    token_info *tok = get(name);
    if (!tok) return false;
    tok->allowances[owner][spender] = amount;
    return true;
}

bool token_store::transfer_from(const std::string &name, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get(name);
    if (!tok) return false;
    auto &allowed = tok->allowances[from][spender];
    if (allowed < amount) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    allowed -= amount;
    fit->second -= amount;
    tok->balances[to] += amount;
    return true;
}

bool token_store::transfer_from_by_address(const std::string &address, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get_by_address(address);
    if (!tok) return false;
    auto &allowed = tok->allowances[from][spender];
    if (allowed < amount) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    allowed -= amount;
    fit->second -= amount;
    tok->balances[to] += amount;
    return true;
}

uint64_t token_store::balance_of(const std::string &name, const std::string &account) const {
    auto it = tokens.find(name);
    if (it == tokens.end()) return 0;
    auto fit = it->second.balances.find(account);
    return fit == it->second.balances.end() ? 0 : fit->second;
}

uint64_t token_store::balance_of_by_address(const std::string &address, const std::string &account) const {
    auto itn = address_index.find(address);
    if (itn == address_index.end()) return 0;
    return balance_of(itn->second, account);
}

uint64_t token_store::allowance_of(const std::string &name, const std::string &owner, const std::string &spender) const {
    auto it = tokens.find(name);
    if (it == tokens.end()) return 0;
    auto oit = it->second.allowances.find(owner);
    if (oit == it->second.allowances.end()) return 0;
    auto sit = oit->second.find(spender);
    return sit == oit->second.end() ? 0 : sit->second;
}

void token_store::rebuild_indexes() {
    address_index.clear();
    creator_tokens.clear();
    for (const auto &kv : tokens) {
        address_index[kv.second.address] = kv.first;
        creator_tokens[kv.second.creator].push_back(kv.first);
    }
}

void token_store::list_all(std::vector<token_info> &out) const {
    for (const auto &kv : tokens)
        out.push_back(kv.second);
}

void token_store::list_by_creator(const std::string &creator, std::vector<token_info> &out) const {
    auto it = creator_tokens.find(creator);
    if(it == creator_tokens.end()) return;
    for(const auto &name : it->second) {
        auto tit = tokens.find(name);
        if(tit != tokens.end())
            out.push_back(tit->second);
    }
}

