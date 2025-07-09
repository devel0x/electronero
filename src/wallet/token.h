#ifndef BITCOIN_WALLET_TOKEN_H
#define BITCOIN_WALLET_TOKEN_H

#include <amount.h>
#include <map>
#include <string>
#include <tuple>
#include <sync.h>

bool IsValidTokenId(const std::string& token);

class TokenLedger {
public:
    void CreateToken(const std::string& wallet, const std::string& token, CAmount amount);
    CAmount Balance(const std::string& wallet, const std::string& token) const;
    void Approve(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount);
    CAmount Allowance(const std::string& owner, const std::string& spender, const std::string& token) const;
    bool Transfer(const std::string& from, const std::string& to, const std::string& token, CAmount amount);
    bool TransferFrom(const std::string& spender, const std::string& from, const std::string& to, const std::string& token, CAmount amount);

private:
    mutable RecursiveMutex m_mutex;
    std::map<std::pair<std::string,std::string>, CAmount> m_balances;
    std::map<std::tuple<std::string,std::string,std::string>, CAmount> m_allowances;
};

extern TokenLedger g_token_ledger;

#endif // BITCOIN_WALLET_TOKEN_H
