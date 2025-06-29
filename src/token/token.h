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

#ifndef TOKEN_H
#define TOKEN_H

#include <string>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <boost/serialization/serialization.hpp>
// #define BOOST_SERIALIZATION_VERSION_HPP
#include <boost/serialization/version.hpp>
#include <boost/serialization/string.hpp>
#include <boost/serialization/vector.hpp>
#include <boost/serialization/unordered_set.hpp>
#include <boost/serialization/unordered_map.hpp>

enum class token_op_type : uint8_t {
    create = 0,
    transfer = 1,
    approve = 2,
    transfer_from = 3,
    set_fee = 4,
    burn = 5,
    mint = 6,
    transfer_ownership = 7,
    pause = 8,
    freeze = 9,
    lock_fee = 10
};

struct token_info {
    std::string name;
    std::string symbol;
    std::string address;
    std::string creator;
    uint64_t total_supply = 0;
    uint64_t creator_fee = 0;
    bool creator_fee_locked = false;
    bool paused = false;
    std::unordered_set<std::string> frozen_accounts;
    std::unordered_map<std::string, uint64_t> balances;
    std::unordered_map<std::string, std::unordered_map<std::string, uint64_t>> allowances;

    template<class Archive>
    void serialize(Archive &a, const unsigned int ver) {
        a & name;
        a & symbol;
        a & total_supply;
        a & address;
        a & creator;
        a & creator_fee;
        a & balances;
        a & allowances;
        if(ver > 0)
            a & paused;
        else if(Archive::is_loading::value)
            paused = false;
        if(ver > 1)
            a & frozen_accounts;
        else if(Archive::is_loading::value)
            frozen_accounts.clear();
        if(ver > 2)
            a & creator_fee_locked;
        else if(Archive::is_loading::value)
            creator_fee_locked = false;
    }
};

struct token_transfer_record {
    std::string token_address;
    std::string from;
    std::string to;
    uint64_t amount = 0;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & token_address;
        a & from;
        a & to;
        a & amount;
    }
};

struct token_store_data
{
    std::unordered_map<std::string, token_info> tokens;
    std::vector<token_transfer_record> transfers;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & tokens;
        a & transfers;
    }
};

class token_store {
public:
    bool load(const std::string &file);
    bool save(const std::string &file);
    bool load_from_string(const std::string &blob);
    bool merge_from_string(const std::string &blob);
    bool store_to_string(std::string &blob) const;

    const token_info *get(const std::string &name) const;
    token_info *get(const std::string &name);
    const token_info *get_by_address(const std::string &address) const;
    token_info *get_by_address(const std::string &address);

    token_info &create(const std::string &name, const std::string &symbol, uint64_t supply,
                       const std::string &creator, uint64_t creator_fee = 0,
                       const std::string &address = std::string());

    void list_all(std::vector<token_info> &out) const;
    void list_by_creator(const std::string &creator, std::vector<token_info> &out) const;
    void list_by_balance(const std::string &account, std::vector<token_info> &out) const;

    bool transfer(const std::string &name, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_by_address(const std::string &address, const std::string &from, const std::string &to, uint64_t amount);
    bool approve(const std::string &name, const std::string &owner, const std::string &spender, uint64_t amount, const std::string &caller);
    bool transfer_from(const std::string &name, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    bool transfer_from_by_address(const std::string &address, const std::string &spender, const std::string &from, const std::string &to, uint64_t amount);
    uint64_t balance_of(const std::string &name, const std::string &account) const;
    uint64_t balance_of_by_address(const std::string &address, const std::string &account) const;
    uint64_t allowance_of(const std::string &name, const std::string &owner, const std::string &spender) const;
    uint64_t allowance_of_by_address(const std::string &address, const std::string &owner, const std::string &spender) const;

    bool burn(const std::string &address, const std::string &owner, uint64_t amount);
    bool mint(const std::string &address, const std::string &creator, uint64_t amount);

    bool set_creator_fee(const std::string &address, const std::string &creator, uint64_t fee);
    bool lock_creator_fee(const std::string &address, const std::string &creator);

    bool set_paused(const std::string &address, const std::string &creator, bool p);
    bool set_frozen(const std::string &address, const std::string &creator, const std::string &account, bool f);

    bool transfer_ownership(const std::string &address, const std::string &creator, const std::string &new_owner);

    void history_by_token(const std::string &token_address, std::vector<token_transfer_record> &out) const;
    void history_by_account(const std::string &account, std::vector<token_transfer_record> &out) const;
    void history_by_token_account(const std::string &token_address, const std::string &account, std::vector<token_transfer_record> &out) const;

    size_t size() const { return tokens.size(); }

private:
    std::unordered_map<std::string, token_info> tokens;
    std::unordered_map<std::string, std::string> address_index;
    std::unordered_map<std::string, std::vector<std::string>> creator_tokens;
    std::vector<token_transfer_record> transfer_history;

    void rebuild_indexes();
    void record_transfer(const std::string &token_address, const std::string &from, const std::string &to, uint64_t amount);
};

#include "crypto/crypto.h"

std::string make_token_extra(token_op_type op, const std::vector<std::string> &fields);
std::string make_signed_token_extra(token_op_type op, const std::vector<std::string> &fields,
                                    const crypto::public_key &pub, const crypto::secret_key &sec);
bool parse_token_extra(const std::string &data, token_op_type &op, std::vector<std::string> &fields,
                       crypto::signature &sig, bool &has_sig);
bool verify_token_extra(token_op_type op, const std::vector<std::string> &fields,
                        const crypto::public_key &pub, const crypto::signature &sig);

BOOST_CLASS_VERSION(token_info, 3)

#endif // TOKEN_H
