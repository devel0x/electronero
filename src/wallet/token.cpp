#include <wallet/token.h>
#include <util/strencodings.h>
#include <net.h>
#include <protocol.h>

extern std::unique_ptr<CConnman> g_connman;

bool IsValidTokenId(const std::string& token)
{
    if (token.size() != 57) return false;
    if (token.substr(54) != "tok") return false;
    for (size_t i = 0; i < 54; ++i) {
        if (HexDigit(token[i]) < 0) return false;
    }
    return true;
}

uint256 TokenOperationHash(const TokenOperation& op)
{
    return SerializeHash(op);
}

void BroadcastTokenOp(const TokenOperation& op)
{
    if (!g_connman) return;
    g_connman->ForEachNode([&](CNode* pnode) {
        CNetMsgMaker msgMaker(pnode->GetCommonVersion());
        g_connman->PushMessage(pnode, msgMaker.Make(NetMsgType::TOKENTX, op));
    });
}

void TokenLedger::SetGovernanceWallet(const std::string& wallet)
{
    LOCK(m_mutex);
    m_governance_wallet = wallet;
}

CAmount TokenLedger::GovernanceBalance() const
{
    LOCK(m_mutex);
    return m_governance_fees;
}
void TokenLedger::CreateToken(const std::string& wallet, const std::string& token, CAmount amount)
{
    m_balances[{wallet, token}] += amount;
    m_totalSupply[token] += amount;
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

void TokenLedger::IncreaseAllowance(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    m_allowances[{owner, spender, token}] += amount;
}

void TokenLedger::DecreaseAllowance(const std::string& owner, const std::string& spender, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    auto& val = m_allowances[{owner, spender, token}];
    if (val <= amount) {
        m_allowances.erase({owner, spender, token});
    } else {
        val -= amount;
    }
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

bool TokenLedger::Burn(const std::string& wallet, const std::string& token, CAmount amount)
{
    LOCK(m_mutex);
    CAmount& bal = m_balances[{wallet, token}];
    if (bal < amount) return false;
    bal -= amount;
    m_totalSupply[token] -= amount;
    return true;
}

CAmount TokenLedger::TotalSupply(const std::string& token) const
{
    LOCK(m_mutex);
    auto it = m_totalSupply.find(token);
    if (it == m_totalSupply.end()) return 0;
    return it->second;
}

bool TokenLedger::ApplyOperation(const TokenOperation& op, bool broadcast)
{
    LOCK(m_mutex);
    uint256 hash = TokenOperationHash(op);
    if (!m_seen_ops.insert(hash).second) return false;
    bool ok = true;
    switch (op.op) {
    case TokenOp::CREATE:
        CreateToken(op.from, op.token, op.amount);
        break;
    case TokenOp::TRANSFER:
        ok = Transfer(op.from, op.to, op.token, op.amount);
        break;
    case TokenOp::APPROVE:
        Approve(op.from, op.to, op.token, op.amount);
        break;
    case TokenOp::TRANSFERFROM:
        ok = TransferFrom(op.spender, op.from, op.to, op.token, op.amount);
        break;
    case TokenOp::INCREASE_ALLOWANCE:
        IncreaseAllowance(op.from, op.to, op.token, op.amount);
        break;
    case TokenOp::DECREASE_ALLOWANCE:
        DecreaseAllowance(op.from, op.to, op.token, op.amount);
        break;
    case TokenOp::BURN:
        ok = Burn(op.from, op.token, op.amount);
        break;
    }
    if (ok) {
        // charge a network fee of 1 sat/vB and credit the governance wallet
        unsigned int vsize = GetSerializeSize(op, SER_NETWORK, PROTOCOL_VERSION);
        m_governance_fees += vsize; // 1 sat per vbyte
    }

    if (broadcast && ok) BroadcastTokenOp(op);
    return ok;
}

TokenLedger g_token_ledger;

