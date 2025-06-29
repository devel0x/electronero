// Business Source License 1.1
// License text copyright (c) 2017 MariaDB Corporation Ab, All Rights Reserved.
// "Business Source License" is a trademark of MariaDB Corporation Ab.
// -----------------------------------------------------------------------------
// Parameters
// Licensor:             Electronero Network (electronero.org)
// Licensed Work:        Cryptonote Token Subsystem
//                       The Licensed Work is (c) 2025 Electronero Network
// Additional Use Grant: Any uses listed and defined at
//                       electronero.org/licenses
// Change Date:          The earlier of 2029-06-29 or a date specified at
//                       electronero.org/licenses
// Change License:       MIT License
// -----------------------------------------------------------------------------
// Terms
// The Licensor hereby grants you the right to copy, modify, create derivative works, redistribute, and make non-production use of the Licensed Work. The Licensor may make an Additional Use Grant, above, permitting limited production use.
// Effective on the Change Date, or the fourth anniversary of the first publicly available distribution of a specific version of the Licensed Work under this License, whichever comes first, the Licensor hereby grants you rights under the terms of the Change License, and the rights granted in the paragraph above terminate.
// If your use of the Licensed Work does not comply with the requirements currently in effect as described in this License, you must purchase a commercial license from the Licensor, its affiliated entities, or authorized resellers, or you must refrain from using the Licensed Work.
// All copies of the original and modified Licensed Work, and derivative works of the Licensed Work, are subject to this License. This License applies separately for each version of the Licensed Work and the Change Date may vary for each version of the Licensed Work released by Licensor.
// You must conspicuously display this License on each original or modified copy of the Licensed Work. If you receive the Licensed Work in original or modified form from a third party, the terms and conditions set forth in this License apply to your use of that work.
// Any use of the Licensed Work in violation of this License will automatically terminate your rights under this License for the current and all other versions of the Licensed Work.
// This License does not grant you any right in any trademark or logo of Licensor or its affiliates (provided that you may use a trademark or logo of Licensor as expressly required by this License).
// TO THE EXTENT PERMITTED BY APPLICABLE LAW, THE LICENSED WORK IS PROVIDED ON AN "AS IS" BASIS. LICENSOR HEREBY DISCLAIMS ALL WARRANTIES AND CONDITIONS, EXPRESS OR IMPLIED, INCLUDING (WITHOUT LIMITATION) WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, AND TITLE.
// MariaDB hereby grants you permission to use this License’s text to license your works, and to refer to it using the trademark "Business Source License", as long as you comply with the Covenants of Licensor below.
// -----------------------------------------------------------------------------
// Covenants of Licensor
// In consideration of the right to use this License’s text and the "Business Source License" name and trademark, Licensor covenants to MariaDB, and to all other recipients of the licensed work to be provided by Licensor:
// 1. To specify as the Change License the GPL Version 2.0 or any later version,    or a license that is compatible with GPL Version 2.0 or a later version,    where "compatible" means that software provided under the Change License can    be included in a program with software provided under GPL Version 2.0 or a    later version. Licensor may specify additional Change Licenses without    limitation.
// 2. To either: (a) specify an additional grant of rights to use that does not    impose any additional restriction on the right granted in this License, as    the Additional Use Grant; or (b) insert the text "None".
// 3. To specify a Change Date.
// 4. Not to modify this License in any other way.
// -----------------------------------------------------------------------------
// Notice
// The Business Source License (this document, or the "License") is not an Open Source license. However, the Licensed Work will eventually be made available under an Open Source License, as stated in this License.

#include "token.h"
#include <fstream>
#include <boost/archive/binary_iarchive.hpp>
#include <boost/archive/binary_oarchive.hpp>
#include <sstream>
#include <algorithm>
#include <boost/filesystem.hpp>
#include "common/util.h"
#include "crypto/hash.h"
#include "crypto/crypto.h"
#include "string_tools.h"
#include <boost/filesystem.hpp>
#include "common/util.h"
#include "misc_log_ex.h"
#include "cryptonote_basic/cryptonote_basic_impl.h"
#include "cryptonote_config.h"

#undef MONERO_DEFAULT_LOG_CATEGORY
#define MONERO_DEFAULT_LOG_CATEGORY "wallet.token"

namespace {
bool parse_any_address(const std::string &str,
                       cryptonote::address_parse_info &info,
                       cryptonote::network_type &net)
{
    const cryptonote::network_type nets[] = {cryptonote::MAINNET, cryptonote::TESTNET, cryptonote::STAGENET};
    for (auto n : nets)
    {
        if (cryptonote::get_account_address_from_str(info, n, str))
        {
            net = n;
            return true;
        }
    }
    return false;
}
}

bool token_store::load(const std::string &file) {
    std::ifstream ifs(file, std::ios::binary);
    if (!ifs)
    {
        MERROR("Failed to open token store " << file);
        return false;
    }
    try
    {
        boost::archive::binary_iarchive ia(ifs);
        token_store_data data;
        ia >> data;
        tokens = std::move(data.tokens);
        transfer_history = std::move(data.transfers);
        rebuild_indexes();
    }
    catch(const std::exception &e)
    {
        MERROR("Failed to load token store " << file << ": " << e.what());
        return false;
    }
    return true;
}

bool token_store::load_from_string(const std::string &blob) {
    std::istringstream iss(blob);
    boost::archive::binary_iarchive ia(iss);
    token_store_data data;
    ia >> data;
    tokens = std::move(data.tokens);
    transfer_history = std::move(data.transfers);
    rebuild_indexes();
    return true;
}

bool token_store::merge_from_string(const std::string &blob) {
    std::istringstream iss(blob);
    boost::archive::binary_iarchive ia(iss);
    token_store_data data;
    ia >> data;
    for (const auto &kv : data.tokens) {
        if (tokens.find(kv.first) == tokens.end())
            tokens.emplace(kv);
    }
    transfer_history.insert(transfer_history.end(), data.transfers.begin(), data.transfers.end());
    rebuild_indexes();
    return true;
}

bool token_store::save(const std::string &file) {
    std::ofstream ofs(file, std::ios::binary | std::ios::trunc);
    if (!ofs)
    {
        MERROR("Failed to open token store for write: " << file);
        return false;
    }
    try
    {
        boost::archive::binary_oarchive oa(ofs);
        token_store_data data{tokens, transfer_history};
        oa << data;
    }
    catch(const std::exception &e)
    {
        MERROR("Failed to save token store " << file << ": " << e.what());
        return false;
    }
    return true;
}

bool token_store::store_to_string(std::string &blob) const {
    std::ostringstream oss;
    boost::archive::binary_oarchive oa(oss);
    token_store_data data{tokens, transfer_history};
    oa << data;
    blob = oss.str();
    return true;
}

token_info &token_store::create(const std::string &name, const std::string &symbol,
                                uint64_t supply, const std::string &creator,
                                uint64_t creator_fee, const std::string &address) {
    auto &tok = tokens[name];
    tok.name = name;
    tok.symbol = symbol;
    tok.creator = creator;
    tok.total_supply = supply;
    tok.creator_fee = creator_fee;
    tok.creator_fee_locked = false;
    tok.paused = false;
    tok.balances[creator] = supply;
    if (address.empty()) {
        // incorporate some random bytes to ensure unique hash even when called repeatedly
        uint64_t nonce = crypto::rand<uint64_t>();
        std::string data = creator + name + symbol + std::to_string(tokens.size()) + std::to_string(nonce);
        crypto::hash h;
        crypto::cn_fast_hash(data.data(), data.size(), h);
        std::string hex = epee::string_tools::pod_to_hex(h);
        tok.address = std::string("cEVM") + hex.substr(0, 46);
    } else {
        tok.address = address;
    }
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
    if (!tok || tok->paused) return false;
        if (tok->frozen_accounts.count(from) || tok->frozen_accounts.count(to)) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    fit->second -= amount;
    tok->balances[to] += amount;
    record_transfer(tok->address, from, to, amount);
    cryptonote::address_parse_info info;
    cryptonote::network_type net;
    if (parse_any_address(to, info, net) && info.has_payment_id)
    {
        std::string base = cryptonote::get_account_address_as_str(net, info.is_subaddress, info.address);
        tok->allowances[to][base] += amount;
    }
    return true;
}

bool token_store::transfer_by_address(const std::string &address, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get_by_address(address);
    if (!tok || tok->paused) return false;
        if (tok->frozen_accounts.count(from) || tok->frozen_accounts.count(to)) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    fit->second -= amount;
    tok->balances[to] += amount;
    record_transfer(address, from, to, amount);
    cryptonote::address_parse_info info;
    cryptonote::network_type net;
    if (parse_any_address(to, info, net) && info.has_payment_id)
    {
        std::string base = cryptonote::get_account_address_as_str(net, info.is_subaddress, info.address);
        tok->allowances[to][base] += amount;
    }
    return true;
}

bool token_store::approve(const std::string &name, const std::string &owner, const std::string &spender, uint64_t amount, const std::string &caller) {
    token_info *tok = get(name);
    if (!tok) return false;
    if (caller != owner)
        return false;
    auto fit = tok->balances.find(owner);
    if (fit == tok->balances.end())
        return false;
    tok->allowances[owner][spender] = amount;
    return true;
}

bool token_store::transfer_from(const std::string &name, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get(name);
    if (!tok || tok->paused) return false;
    if (tok->frozen_accounts.count(spender) || tok->frozen_accounts.count(from) || tok->frozen_accounts.count(to)) return false;
    auto &allowed = tok->allowances[from][spender];
    if (allowed < amount) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    allowed -= amount;
    fit->second -= amount;
    tok->balances[to] += amount;
    record_transfer(tok->address, from, to, amount);
    return true;
}

bool token_store::transfer_from_by_address(const std::string &address, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount) {
    token_info *tok = get_by_address(address);
    if (!tok || tok->paused) return false;
    if (tok->frozen_accounts.count(spender) || tok->frozen_accounts.count(from) || tok->frozen_accounts.count(to)) return false;
    auto &allowed = tok->allowances[from][spender];
    if (allowed < amount) return false;
    auto fit = tok->balances.find(from);
    if (fit == tok->balances.end() || fit->second < amount) return false;
    allowed -= amount;
    fit->second -= amount;
    tok->balances[to] += amount;
    record_transfer(address, from, to, amount);
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

uint64_t token_store::allowance_of_by_address(const std::string &address, const std::string &owner, const std::string &spender) const {
    auto itn = address_index.find(address);
    if (itn == address_index.end()) return 0;
    return allowance_of(itn->second, owner, spender);
}

bool token_store::burn(const std::string &address, const std::string &owner, uint64_t amount) {
    token_info *tok = get_by_address(address);
    if(!tok) return false;
    if (tok->frozen_accounts.count(owner)) return false;
    auto it = tok->balances.find(owner);
    if(it == tok->balances.end() || it->second < amount) return false;
    it->second -= amount;
    tok->total_supply -= amount;
    record_transfer(address, owner, "", amount);
    return true;
}

bool token_store::mint(const std::string &address, const std::string &creator, uint64_t amount) {
    token_info *tok = get_by_address(address);
    if(!tok || tok->creator != creator) return false;
    if (tok->frozen_accounts.count(creator)) return false;
    tok->total_supply += amount;
    tok->balances[creator] += amount;
    record_transfer(address, "", creator, amount);
    return true;
}

bool token_store::set_creator_fee(const std::string &address, const std::string &creator, uint64_t fee)
{
    token_info *tok = get_by_address(address);
    if(!tok || tok->creator != creator || tok->creator_fee_locked)
        return false;
    tok->creator_fee = fee;
    return true;
}

bool token_store::lock_creator_fee(const std::string &address, const std::string &creator)
{
    token_info *tok = get_by_address(address);
    if(!tok || tok->creator != creator || tok->creator_fee_locked)
        return false;
    tok->creator_fee_locked = true;
    return true;
}

bool token_store::set_paused(const std::string &address, const std::string &creator, bool p)
{
    token_info *tok = get_by_address(address);
    if(!tok || tok->creator != creator)
        return false;
    tok->paused = p;
    return true;
}

bool token_store::set_frozen(const std::string &address, const std::string &creator, const std::string &account, bool f)
{
    token_info *tok = get_by_address(address);
    if(!tok || creator != GOVERNANCE_WALLET_ADDRESS)
        return false;
    if(f)
        tok->frozen_accounts.insert(account);
    else
        tok->frozen_accounts.erase(account);
    return true;
}

bool token_store::transfer_ownership(const std::string &address, const std::string &creator, const std::string &new_owner)
{
    token_info *tok = get_by_address(address);
    if(!tok || tok->creator != creator)
        return false;
    auto itn = address_index.find(address);
    if(itn == address_index.end())
        return false;
    const std::string &name = itn->second;
    auto &old_list = creator_tokens[creator];
    old_list.erase(std::remove(old_list.begin(), old_list.end(), name), old_list.end());
    tok->creator = new_owner;
    creator_tokens[new_owner].push_back(name);
    return true;
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

void token_store::list_by_balance(const std::string &account, std::vector<token_info> &out) const {
    for(const auto &kv : tokens) {
        auto it = kv.second.balances.find(account);
        if(it != kv.second.balances.end() && it->second > 0)
            out.push_back(kv.second);
    }
}

std::string make_token_extra(token_op_type op, const std::vector<std::string> &fields)
{
    std::ostringstream oss;
    oss << static_cast<int>(op);
    for(const auto &f : fields)
        oss << '\t' << f;
    return oss.str();
}

std::string make_signed_token_extra(token_op_type op, const std::vector<std::string> &fields,
                                    const crypto::public_key &pub, const crypto::secret_key &sec)
{
    std::string base = make_token_extra(op, fields);
    crypto::hash h;
    crypto::cn_fast_hash(base.data(), base.size(), h);
    crypto::signature sig;
    crypto::generate_signature(h, pub, sec, sig);
    return base + '\t' + epee::string_tools::pod_to_hex(sig);
}

bool parse_token_extra(const std::string &data, token_op_type &op, std::vector<std::string> &fields,
                       crypto::signature &sig, bool &has_sig)
{
    std::istringstream iss(data);
    int op_int;
    if(!(iss >> op_int))
        return false;
    op = static_cast<token_op_type>(op_int);
    if (iss.peek() == '\t')
        iss.get();
    std::string field;
    while(std::getline(iss, field, '\t'))
        fields.push_back(field);
    has_sig = false;
    if(!fields.empty())
    {
        std::string sig_hex = fields.back();
        if(sig_hex.size() == sizeof(crypto::signature) * 2 && epee::string_tools::hex_to_pod(sig_hex, sig))
        {
            fields.pop_back();
            has_sig = true;
        }
    }
    return true;
}

bool verify_token_extra(token_op_type op, const std::vector<std::string> &fields,
                        const crypto::public_key &pub, const crypto::signature &sig)
{
    std::string base = make_token_extra(op, fields);
    crypto::hash h;
    crypto::cn_fast_hash(base.data(), base.size(), h);
    return crypto::check_signature(h, pub, sig);
}

void token_store::record_transfer(const std::string &token_address, const std::string &from, const std::string &to, uint64_t amount)
{
    token_transfer_record rec;
    rec.token_address = token_address;
    rec.from = from;
    rec.to = to;
    rec.amount = amount;
    transfer_history.push_back(rec);
}

void token_store::history_by_token(const std::string &token_address, std::vector<token_transfer_record> &out) const
{
    for(const auto &r : transfer_history)
        if(r.token_address == token_address)
            out.push_back(r);
}

void token_store::history_by_account(const std::string &account, std::vector<token_transfer_record> &out) const
{
    for(const auto &r : transfer_history)
        if(r.from == account || r.to == account)
            out.push_back(r);
}

void token_store::history_by_token_account(const std::string &token_address, const std::string &account, std::vector<token_transfer_record> &out) const
{
    for(const auto &r : transfer_history)
        if(r.token_address == token_address && (r.from == account || r.to == account))
            out.push_back(r);
}

