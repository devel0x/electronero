#ifndef BITCOIN_WALLET_TOKEN_H
#define BITCOIN_WALLET_TOKEN_H

#include <amount.h>
#include <map>
#include <string>
#include <tuple>
#include <sync.h>
#include <set>
#include <vector>
#include <hash.h>
#include <serialize.h>

enum class TokenOp : uint8_t {
    CREATE=0,
    TRANSFER=1,
    APPROVE=2,
    TRANSFERFROM=3,
    INCREASE_ALLOWANCE=4,
    DECREASE_ALLOWANCE=5,
    BURN=6
};

struct TokenOperation {
    TokenOp op{TokenOp::CREATE};
    std::string from;
    std::string to;
    std::string spender;
    std::string token;
    CAmount amount{0};

    SERIALIZE_METHODS(TokenOperation, obj)
    {
        READWRITE(obj.op, obj.from, obj.to, obj.spender, obj.token, obj.amount);
    }
};

uint256 TokenOperationHash(const TokenOperation& op);

void BroadcastTokenOp(const TokenOperation& op);

bool IsValidTokenId(const std::string& token);

class TokenLedger {
public:
    bool ApplyOperation(const TokenOperation& op, bool broadcast = true);

    CAmount Balance(const std::string& wallet, const std::string& token) const;
    CAmount Allowance(const std::string& owner, const std::string& spender, const std::string& token) const;
    CAmount TotalSupply(const std::string& token) const;

private:
    void CreateToken(const std::string& wallet, const std::string& token, CAmount amount);
    void Approve(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    void IncreaseAllowance(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    void DecreaseAllowance(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    bool Transfer(const std::string& from, const std::string& to, const std::string& token, CAmount amount);
    bool TransferFrom(const std::string& spender, const std::string& from, const std::string& to, const std::string& token, CAmount amount);
    bool Burn(const std::string& wallet, const std::string& token, CAmount amount);

    mutable RecursiveMutex m_mutex;
    std::map<std::pair<std::string,std::string>, CAmount> m_balances;
    std::map<std::tuple<std::string,std::string,std::string>, CAmount> m_allowances;
    std::map<std::string, CAmount> m_totalSupply;
    std::set<uint256> m_seen_ops;
};

extern TokenLedger g_token_ledger;

#endif // BITCOIN_WALLET_TOKEN_H
