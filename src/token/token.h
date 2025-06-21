#ifndef TOKEN_H
#define TOKEN_H

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

enum class token_op_type : uint8_t {
    create = 0,
    transfer = 1,
    approve = 2,
    transfer_from = 3,
    set_fee = 4,
    burn = 5,
    mint = 6,
    proposal_create = 7,
    proposal_vote = 8,
    proposal_end = 9
};

struct token_info {
    std::string name;
    std::string symbol;
    std::string address;
    std::string creator;
    uint64_t total_supply = 0;
    uint64_t creator_fee = 0;
    std::unordered_map<std::string, uint64_t> balances;
    std::unordered_map<std::string, std::unordered_map<std::string, uint64_t>> allowances;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & name;
        a & symbol;
        a & total_supply;
        a & address;
        a & creator;
        a & creator_fee;
        a & balances;
        a & allowances;
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

struct proposal_info {
    std::string id;
    std::string title;
    std::string creator;
    bool active = true;
    uint64_t yes = 0;
    uint64_t no = 0;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & id;
        a & title;
        a & creator;
        a & active;
        a & yes;
        a & no;
    }
};

struct token_store_data
{
    std::unordered_map<std::string, token_info> tokens;
    std::vector<token_transfer_record> transfers;
    std::unordered_map<std::string, proposal_info> proposals;

    template<class Archive>
    void serialize(Archive &a, const unsigned int /*version*/) {
        a & tokens;
        a & transfers;
        a & proposals;
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

    token_info &create(const std::string &name, const std::string &symbol, uint64_t supply, const std::string &creator, uint64_t creator_fee = 0);

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

    bool burn(const std::string &address, const std::string &owner, uint64_t amount);
    bool mint(const std::string &address, const std::string &creator, uint64_t amount);

    bool set_creator_fee(const std::string &address, const std::string &creator, uint64_t fee);

    proposal_info &create_proposal(const std::string &title, const std::string &creator);
    bool vote_proposal(const std::string &id, bool yes);
    bool end_proposal(const std::string &id, const std::string &creator);
    void list_proposals(std::vector<proposal_info> &out) const;
    void list_active_proposals(std::vector<proposal_info> &out) const;
    const proposal_info *get_proposal(const std::string &id_or_title) const;
    proposal_info *get_proposal(const std::string &id_or_title);

    void history_by_token(const std::string &token_address, std::vector<token_transfer_record> &out) const;
    void history_by_account(const std::string &account, std::vector<token_transfer_record> &out) const;
    void history_by_token_account(const std::string &token_address, const std::string &account, std::vector<token_transfer_record> &out) const;

    size_t size() const { return tokens.size(); }

private:
    std::unordered_map<std::string, token_info> tokens;
    std::unordered_map<std::string, std::string> address_index;
    std::unordered_map<std::string, std::vector<std::string>> creator_tokens;
    std::vector<token_transfer_record> transfer_history;
    std::unordered_map<std::string, proposal_info> proposals;

    void rebuild_indexes();
    void record_transfer(const std::string &token_address, const std::string &from, const std::string &to, uint64_t amount);
};

std::string make_token_extra(token_op_type op, const std::vector<std::string> &fields);
bool parse_token_extra(const std::string &data, token_op_type &op, std::vector<std::string> &fields);

#endif // TOKEN_H
