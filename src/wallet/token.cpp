#include <wallet/token.h>
#include <util/strencodings.h>
#include <net.h>
#include <protocol.h>
#include <wallet/wallet.h>
#include <util/message.h>
#include <key_io.h>
#include <wallet/coincontrol.h>
#include <script/standard.h>
#include <outputtype.h>
#include <util/translation.h>
#include <random.h>
#include <dbwrapper.h>
#include <util/system.h>
#include <chainparams.h>
#include <validation.h>
#include <validationinterface.h>
#include <optional.h>

extern std::unique_ptr<CConnman> g_connman;

static std::unique_ptr<CDBWrapper> g_token_db;

namespace {
class TokenValidationInterface : public CValidationInterface {
public:
    void BlockConnected(const std::shared_ptr<const CBlock>& block, const CBlockIndex* index) override {
        g_token_ledger.ProcessBlock(*block, index->nHeight);
    }
    void BlockDisconnected(const std::shared_ptr<const CBlock>& block, const CBlockIndex* index) override {
        g_token_ledger.RescanFromHeight(index->nHeight);
    }
};

std::shared_ptr<TokenValidationInterface> g_token_validation;
}

void RegisterTokenValidationInterface()
{
    if (!g_token_validation) {
        g_token_validation = std::make_shared<TokenValidationInterface>();
        RegisterSharedValidationInterface(g_token_validation);
    }
}

void UnregisterTokenValidationInterface()
{
    if (g_token_validation) {
        UnregisterSharedValidationInterface(g_token_validation);
        g_token_validation.reset();
    }
}

bool IsValidTokenId(const std::string& token)
{
    if (token.size() != 59) return false;
    if (token.compare(0, 2, "0x") != 0) return false;
    if (token.substr(56) != "tok") return false;
    for (size_t i = 2; i < 56; ++i) {
        if (HexDigit(token[i]) < 0) return false;
    }
    return true;
}

std::string GenerateTokenId(const std::string& creator, const std::string& name)
{
    while (true) {
        CHashWriter hasher(SER_GETHASH, 0);
        hasher << creator << name << GetRandHash();
        uint256 hash = hasher.GetHash();
        std::string hex = hash.GetHex();
        std::string token = "0x" + hex.substr(0, 54) + "tok";
        if (!g_token_ledger.ListAllTokens().empty()) {
            // Ensure uniqueness
            bool exists = false;
            for (const auto& item : g_token_ledger.ListAllTokens()) {
                if (std::get<0>(item) == token) {
                    exists = true;
                    break;
                }
            }
            if (exists) continue;
        }
        return token;
    }
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

CAmount TokenLedger::GovernanceBalance() const
{
    LOCK(m_mutex);
    return m_governance_fees;
}
void TokenLedger::RegisterToken(const std::string& token, const std::string& name, const std::string& symbol, uint8_t decimals, const std::string& owner, int64_t height)
{
    m_token_meta[token] = {name, symbol, decimals, owner, height};
}

void TokenLedger::CreateToken(const std::string& wallet, const std::string& token, CAmount amount, const std::string& name, const std::string& symbol, uint8_t decimals, int64_t height)
{
    m_balances[{wallet, token}] += amount;
    m_totalSupply[token] += amount;
    if (m_token_meta.count(token) == 0) {
        RegisterToken(token, name, symbol, decimals, wallet, height);
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

Optional<TokenMeta> TokenLedger::GetTokenMeta(const std::string& token) const
{
    LOCK(m_mutex);
    auto it = m_token_meta.find(token);
    if (it == m_token_meta.end()) return nullopt;
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

std::string TokenLedger::GetSignerAddress(const std::string& wallet, CWallet& w)
{
    LOCK(m_mutex);
    auto it = m_wallet_signers.find(wallet);
    if (it != m_wallet_signers.end()) return it->second;
    CTxDestination dest;
    std::string error;
    if (!w.GetNewDestination(OutputType::BECH32, "", dest, error)) return "";
    std::string addr = EncodeDestination(dest);
    m_wallet_signers[wallet] = addr;
    Flush();
    return addr;
}

bool TokenLedger::VerifySignature(const TokenOperation& op)
{
    std::string wallet = op.op == TokenOp::TRANSFERFROM ? op.spender : op.from;
    auto it = m_wallet_signers.find(wallet);
    TokenOperation tmp = op;
    tmp.signature.clear();
    tmp.signer.clear();
    uint256 h = TokenOperationHash(tmp);
    std::string msg = h.GetHex();

    // Validate the provided signature against the signer address
    bool valid = MessageVerify(op.signer, op.signature, msg) == MessageVerificationResult::OK;
    if (!valid) return false;

    if (it == m_wallet_signers.end()) {
        // First time seeing this wallet, remember its signer
        m_wallet_signers[wallet] = op.signer;
        Flush();
        return true;
    }

    return it->second == op.signer;
}

bool TokenLedger::RecordOperationOnChain(const std::string& wallet, const TokenOperation& op)
{
    std::shared_ptr<CWallet> from = GetWallet(wallet);
    if (!from) return false;
    LOCK(from->cs_wallet);
    CDataStream ss(SER_NETWORK, PROTOCOL_VERSION);
    ss << op;
    CScript script;
    script << OP_RETURN << ToByteVector(ss);
    CRecipient recipient{script, 0, false};
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
    if (!VerifySignature(op)) return false;
    uint256 hash = TokenOperationHash(op);
    if (!m_seen_ops.insert(hash).second) return false;
    bool ok = true;
    switch (op.op) {
    case TokenOp::CREATE: {
        int64_t height = ::ChainActive().Height();
        CreateToken(op.from, op.token, op.amount, op.name, op.symbol, op.decimals, height);
        break;
    }
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
    case TokenOp::MINT: {
        auto it = m_token_meta.find(op.token);
        if (it == m_token_meta.end() || it->second.operator_wallet != op.from) return false;
        int64_t height = ::ChainActive().Height();
        CreateToken(op.from, op.token, op.amount, it->second.name, it->second.symbol, it->second.decimals, height);
        break;
    }
    }
    if (ok) {
        // charge a network fee per configured rate and send it to the governance wallet
        unsigned int vsize = GetSerializeSize(op, SER_NETWORK, PROTOCOL_VERSION);
        CAmount rate = (op.op == TokenOp::CREATE) ? m_create_fee_per_vbyte : m_fee_per_vbyte;
        CAmount fee = vsize * rate;
        if (SendGovernanceFee(op.from, fee)) {
            m_governance_fees += fee;
        }
        m_history[op.token].push_back(op);
        LogPrintf("token op %u token=%s from=%s to=%s amount=%d\n", uint8_t(op.op), op.token, op.from, op.to, op.amount);
        Flush();
        RecordOperationOnChain(op.from, op);
    }

    if (broadcast && ok) BroadcastTokenOp(op);
    return ok;
}

TokenLedger g_token_ledger;

std::vector<TokenOperation> TokenLedger::TokenHistory(const std::string& token, const std::string& address_filter) const
{
    LOCK(m_mutex);
    std::vector<TokenOperation> out;
    auto it = m_history.find(token);
    if (it == m_history.end()) return out;
    for (const auto& op : it->second) {
        if (!address_filter.empty()) {
            if (op.from != address_filter && op.to != address_filter && op.spender != address_filter) {
                continue;
            }
        }
        out.push_back(op);
    }
    return out;
}

static bool DecodeTokenOp(const CScript& script, TokenOperation& op)
{
    CScript::const_iterator it = script.begin();
    opcodetype opcode;
    std::vector<unsigned char> data;
    if (!script.GetOp(it, opcode)) return false;
    if (opcode != OP_RETURN) return false;
    if (!script.GetOp(it, opcode, data)) return false;
    if (data.empty()) return false;
    if (opcode > OP_PUSHDATA4) return false;
    try {
        CDataStream ss(data, SER_NETWORK, PROTOCOL_VERSION);
        ss >> op;
    } catch (...) {
        return false;
    }
    return true;
}

bool TokenLedger::ReplayOperation(const TokenOperation& op, int64_t height)
{
    if (!VerifySignature(op)) return false;
    uint256 hash = TokenOperationHash(op);
    if (!m_seen_ops.insert(hash).second) return false;
    bool ok = true;
    switch (op.op) {
    case TokenOp::CREATE:
        CreateToken(op.from, op.token, op.amount, op.name, op.symbol, op.decimals, height);
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
    case TokenOp::MINT: {
        auto it = m_token_meta.find(op.token);
        if (it == m_token_meta.end() || it->second.operator_wallet != op.from) return false;
        CreateToken(op.from, op.token, op.amount, it->second.name, it->second.symbol, it->second.decimals, height);
        break;
    }
    }
    if (ok) {
        m_history[op.token].push_back(op);
    }
    return ok;
}

bool TokenLedger::RescanFromHeight(int from_height)
{
    if (from_height < Params().TokenActivationHeight()) {
        from_height = Params().TokenActivationHeight();
    }
    {
        LOCK(m_mutex);
        m_balances.clear();
        m_allowances.clear();
        m_totalSupply.clear();
        m_token_meta.clear();
        m_history.clear();
        m_seen_ops.clear();
        m_governance_fees = 0;
    }

    for (int h = from_height; h <= ::ChainActive().Height(); ++h) {
        const CBlockIndex* index = ::ChainActive()[h];
        if (!index) continue;
        CBlock block;
        if (!ReadBlockFromDisk(block, index, Params().GetConsensus())) continue;
        for (const auto& tx : block.vtx) {
            for (const auto& out : tx->vout) {
                TokenOperation op;
                if (DecodeTokenOp(out.scriptPubKey, op)) {
                    LOCK(m_mutex);
                    ReplayOperation(op, h);
                }
            }
        }
    }
    LOCK(m_mutex);
    m_tip_height = ::ChainActive().Height();
    Flush();
    return true;
}

bool TokenLedger::Load()
{
    LOCK(m_mutex);
    if (!g_token_db) {
        g_token_db = std::make_unique<CDBWrapper>(GetDataDir() / "tokens", 1 << 20, false, false, true);
    }
    uint32_t version = 0;
    g_token_db->Read('v', version);
    TokenLedgerState state;
    if (!g_token_db->Read('s', state)) return false;
    if (version > TOKEN_DB_VERSION) return false;
    if (version < TOKEN_DB_VERSION) {
        // future migrations could be handled here
        state.version = TOKEN_DB_VERSION;
        g_token_db->Write('v', TOKEN_DB_VERSION);
        g_token_db->Write('s', state);
    }
    m_balances = state.balances;
    m_allowances = state.allowances;
    m_totalSupply = state.totalSupply;
    m_token_meta = state.token_meta;
    m_history = state.history;
    m_governance_fees = state.governance_fees;
    m_fee_per_vbyte = state.fee_per_vbyte;
    m_create_fee_per_vbyte = state.create_fee_per_vbyte;
    m_wallet_signers = state.wallet_signers;
    m_tip_height = state.tip_height;
    if (m_tip_height == 0) m_tip_height = Params().TokenActivationHeight() - 1;
    m_governance_wallet = Params().GovernanceWallet();
    return true;
}

bool TokenLedger::Flush() const
{
    LOCK(m_mutex);
    if (!g_token_db) {
        g_token_db = std::make_unique<CDBWrapper>(GetDataDir() / "tokens", 1 << 20, false, false, true);
    }
    TokenLedgerState state;
    state.balances = m_balances;
    state.allowances = m_allowances;
    state.totalSupply = m_totalSupply;
    state.token_meta = m_token_meta;
    state.history = m_history;
    state.governance_fees = m_governance_fees;
    state.fee_per_vbyte = m_fee_per_vbyte;
    state.create_fee_per_vbyte = m_create_fee_per_vbyte;
    state.wallet_signers = m_wallet_signers;
    state.tip_height = m_tip_height;
    state.version = TOKEN_DB_VERSION;
    CDBBatch batch(*g_token_db);
    batch.Write('s', state);
    batch.Write('v', TOKEN_DB_VERSION);
    return g_token_db->WriteBatch(batch, true);
}

void TokenLedger::SetFeeRate(CAmount fee_per_vbyte)
{
    LOCK(m_mutex);
    m_fee_per_vbyte = fee_per_vbyte;
}

CAmount TokenLedger::FeeRate() const
{
    LOCK(m_mutex);
    return m_fee_per_vbyte;
}

void TokenLedger::ProcessBlock(const CBlock& block, int height)
{
    for (const auto& tx : block.vtx) {
        for (const auto& out : tx->vout) {
            TokenOperation op;
            if (DecodeTokenOp(out.scriptPubKey, op)) {
                LOCK(m_mutex);
                ReplayOperation(op, height);
            }
        }
    }
    LOCK(m_mutex);
    m_tip_height = height;
    Flush();
}

