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
    std::string name;
    std::string symbol;

    SERIALIZE_METHODS(TokenOperation, obj)
    {
        READWRITE(obj.op, obj.from, obj.to, obj.spender, obj.token, obj.amount, obj.name, obj.symbol);
    }
};

struct TokenMeta {
    std::string name;
    std::string symbol;
};

uint256 TokenOperationHash(const TokenOperation& op);

void BroadcastTokenOp(const TokenOperation& op);

bool IsValidTokenId(const std::string& token);

class TokenLedger {
public:
    bool ApplyOperation(const TokenOperation& op, bool broadcast = true);

    //! Set the wallet that will receive network fees
    void SetGovernanceWallet(const std::string& wallet);

    //! Total fees collected for the governance wallet
    CAmount GovernanceBalance() const;

    CAmount Balance(const std::string& wallet, const std::string& token) const;
    CAmount Allowance(const std::string& owner, const std::string& spender, const std::string& token) const;
    CAmount TotalSupply(const std::string& token) const;

    std::vector<std::tuple<std::string,std::string,std::string>> ListWalletTokens(const std::string& wallet) const;
    std::vector<std::tuple<std::string,std::string,std::string>> ListAllTokens() const;

    //! Return history of operations for a token, optionally filtered by address
    std::vector<TokenOperation> TokenHistory(const std::string& token, const std::string& address_filter = "") const;

private:
    void CreateToken(const std::string& wallet, const std::string& token, CAmount amount, const std::string& name, const std::string& symbol);
    void RegisterToken(const std::string& token, const std::string& name, const std::string& symbol);
    void Approve(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    void IncreaseAllowance(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    void DecreaseAllowance(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    bool Transfer(const std::string& from, const std::string& to, const std::string& token, CAmount amount);
    bool TransferFrom(const std::string& spender, const std::string& from, const std::string& to, const std::string& token, CAmount amount);
    bool Burn(const std::string& wallet, const std::string& token, CAmount amount);

    //! Send the governance fee as a coin transaction
    bool SendGovernanceFee(const std::string& wallet, CAmount fee);

    mutable RecursiveMutex m_mutex;
    std::map<std::pair<std::string,std::string>, CAmount> m_balances;
    std::map<std::tuple<std::string,std::string,std::string>, CAmount> m_allowances;
    std::map<std::string, CAmount> m_totalSupply;
    std::map<std::string, TokenMeta> m_token_meta;
    std::set<uint256> m_seen_ops;

    // per-token list of operations in order applied
    std::map<std::string, std::vector<TokenOperation>> m_history;

    std::string m_governance_wallet{"governance"};
    CAmount m_governance_fees{0};
};

extern TokenLedger g_token_ledger;

#endif // BITCOIN_WALLET_TOKEN_H
