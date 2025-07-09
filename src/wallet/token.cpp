#include <wallet/token.h>
#include <util/strencodings.h>
#include <net.h>
#include <protocol.h>
#include <wallet/wallet.h>
#include <wallet/coincontrol.h>
#include <script/standard.h>
#include <outputtype.h>
#include <util/translation.h>

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
void TokenLedger::RegisterToken(const std::string& token, const std::string& name, const std::string& symbol)
{
    m_token_meta[token] = {name, symbol};
}

void TokenLedger::CreateToken(const std::string& wallet, const std::string& token, CAmount amount, const std::string& name, const std::string& symbol)
{
    m_balances[{wallet, token}] += amount;
    m_totalSupply[token] += amount;
    if (m_token_meta.count(token) == 0) {
        RegisterToken(token, name, symbol);
    }
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

std::vector<std::tuple<std::string,std::string,std::string>> TokenLedger::ListAllTokens() const
{
    LOCK(m_mutex);
    std::vector<std::tuple<std::string,std::string,std::string>> out;
    for (const auto& kv : m_token_meta) {
        out.emplace_back(kv.first, kv.second.name, kv.second.symbol);
    }
    return out;
}

std::vector<std::tuple<std::string,std::string,std::string>> TokenLedger::ListWalletTokens(const std::string& wallet) const
{
    LOCK(m_mutex);
    std::set<std::string> tokens;
    for (const auto& kv : m_balances) {
        if (kv.first.first == wallet && kv.second > 0) {
            tokens.insert(kv.first.second);
        }
    }
    std::vector<std::tuple<std::string,std::string,std::string>> out;
    for (const auto& token : tokens) {
        auto it = m_token_meta.find(token);
        std::string name, symbol;
        if (it != m_token_meta.end()) {
            name = it->second.name;
            symbol = it->second.symbol;
        }
        out.emplace_back(token, name, symbol);
    }
    return out;
}

bool TokenLedger::SendGovernanceFee(const std::string& wallet, CAmount fee)
{
    std::shared_ptr<CWallet> from = GetWallet(wallet);
    std::shared_ptr<CWallet> dest_wallet = GetWallet(m_governance_wallet);
    if (!from || !dest_wallet) return false;

    LOCK(from->cs_wallet);
    LOCK(dest_wallet->cs_wallet);

    CTxDestination dest;
    std::string error;
    if (!dest_wallet->GetNewDestination(OutputType::BECH32, "", dest, error)) return false;

    CRecipient recipient{GetScriptForDestination(dest), fee, false};
    CCoinControl cc;
    std::vector<CRecipient> vecSend{recipient};
    CAmount nFeeRequired;
    int nChangePosRet = -1;
    bilingual_str err;
    CTransactionRef tx;
    FeeCalculation fee_calc;

    bool created = from->CreateTransaction(vecSend, tx, nFeeRequired, nChangePosRet, err, cc, fee_calc, !from->IsWalletFlagSet(WALLET_FLAG_DISABLE_PRIVATE_KEYS));
    if (!created) return false;
    from->CommitTransaction(tx, {}, {});
    return true;
}

bool TokenLedger::ApplyOperation(const TokenOperation& op, bool broadcast)
{
    LOCK(m_mutex);
    uint256 hash = TokenOperationHash(op);
    if (!m_seen_ops.insert(hash).second) return false;
    bool ok = true;
    switch (op.op) {
    case TokenOp::CREATE:
        CreateToken(op.from, op.token, op.amount, op.name, op.symbol);
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
        // charge a network fee of 1 sat/vB and send it to the governance wallet
        unsigned int vsize = GetSerializeSize(op, SER_NETWORK, PROTOCOL_VERSION);
        CAmount fee = vsize; // 1 sat per vbyte
        if (SendGovernanceFee(op.from, fee)) {
            m_governance_fees += fee;
        }
    }

    if (broadcast && ok) BroadcastTokenOp(op);
    return ok;
}

TokenLedger g_token_ledger;

