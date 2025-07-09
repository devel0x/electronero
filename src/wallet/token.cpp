#include <wallet/token.h>
#include <util/strencodings.h>

bool IsValidTokenId(const std::string& token)
{
    if (token.size() != 57) return false;
    if (token.substr(54) != "tok") return false;
    for (size_t i = 0; i < 54; ++i) {
        if (HexDigit(token[i]) < 0) return false;
    }
    return true;
}

void TokenLedger::CreateToken(const std::string& wallet, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    m_balances[{wallet, token}] += amount;
}

CAmount TokenLedger::Balance(const std::string& wallet, const std::string& token) const
{
    LOCK(m_mutex);
    auto it = m_balances.find({wallet, token});
    if (it == m_balances.end()) return 0;
    return it->second;
}

void TokenLedger::Approve(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    m_allowances[{owner, spender, token}] = amount;
}

CAmount TokenLedger::Allowance(const std::string& owner, const std::string& spender, const std::string& token) const
{
    LOCK(m_mutex);
    auto it = m_allowances.find({owner, spender, token});
    if (it == m_allowances.end()) return 0;
    return it->second;
}

bool TokenLedger::Transfer(const std::string& from, const std::string& to, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    CAmount& from_bal = m_balances[{from, token}];
    if (from_bal < amount) return false;
    from_bal -= amount;
    m_balances[{to, token}] += amount;
    return true;
}

bool TokenLedger::TransferFrom(const std::string& spender, const std::string& from, const std::string& to, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    auto key = std::make_tuple(from, spender, token);
    auto it = m_allowances.find(key);
    if (it == m_allowances.end() || it->second < amount) return false;
    CAmount& from_bal = m_balances[{from, token}];
    if (from_bal < amount) return false;
    from_bal -= amount;
    m_balances[{to, token}] += amount;
    it->second -= amount;
    return true;
}

TokenLedger g_token_ledger;

