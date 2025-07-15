# Token Operations Security

This document provides an overview of how token operations are transmitted and verified within Interchained Core. It focuses on signature verification and the network handling of `TOKENTX` messages.

## Signing operations

Token operations are signed using a wallet's private key. The wallet selects a signer address and builds a deterministic string over all fields of the operation. This message is then signed using the standard message signing utilities.

```cpp
std::string message = BuildTokenMsg(op);
CKey key;
if (!spk_man->GetKey(keyID, key)) return false;
if (!MessageSign(key, message, op.signature)) return false;
```

The `BuildTokenMsg` helper constructs the message in a stable format so that both the signer and verifier operate on the same data.

```cpp
std::string BuildTokenMsg(const TokenOperation& op) {
    return strprintf(
        "op=%d|from=%s|to=%s|spender=%s|token=%s|amount=%d|name=%s|symbol=%s|decimals=%d",
        (int)op.op,
        op.from,
        op.to,
        op.spender,
        op.token,
        op.amount,
        op.name,
        op.symbol,
        op.decimals
    );
}
```

## Verifying signatures

Every received operation is checked with `VerifySignature`. The verifier reconstructs the same message and calls `MessageVerify` to ensure that the signature matches the declared signer. It also verifies that the signer is the expected address for the operation.

```cpp
CTxDestination dest = DecodeDestination(op.signer);
if (!IsValidDestination(dest)) {
    return false;
}
std::string message = BuildTokenMsg(op);
MessageVerificationResult result = MessageVerify(op.signer, op.signature, message);
if (result != MessageVerificationResult::OK) {
    return false;
}
const std::string& expected = op.op == TokenOp::TRANSFERFROM ? op.spender : op.from;
if (op.signer != expected) {
    return false;
}
```

Only if all checks pass does the ledger apply the operation.

## Network processing of token operations

Token operations are propagated as `TOKENTX` messages. A node broadcasts an operation with `BroadcastTokenOp`:

```cpp
if (!g_connman) return;
g_connman->ForEachNode([&](CNode* pnode) {
    CNetMsgMaker msgMaker(pnode->GetCommonVersion());
    g_connman->PushMessage(pnode, msgMaker.Make(NetMsgType::TOKENTX, op));
});
```

Peers receiving the message handle it in `ProcessMessage` inside `net_processing.cpp`. The operation is deserialized and executed locally through `ApplyOperation`. Invalid messages increment the peer's misbehavior score.

```cpp
if (msg_type == NetMsgType::TOKENTX) {
    TokenOperation op;
    vRecv >> op;
    if (!g_token_ledger.ApplyOperation(op, op.wallet_name, /*broadcast=*/false)) {
        Misbehaving(pfrom.GetId(), 10, "invalid token operation");
    }
    return;
}
```

Through this mechanism, every node independently validates the authenticity of incoming token operations before applying them to its ledger.

## Replay during synchronization

When a node synchronizes the blockchain or rescans from disk, token operations
embedded in blocks are processed with `ReplayOperation`. This helper performs
the same balance and allowance updates as `ApplyOperation`, but **does not**
create new transactions or broadcast messages. The function simply updates the
in-memory ledger and history:

```cpp
bool TokenLedger::ReplayOperation(const TokenOperation& op, int64_t height) {
    if (!VerifySignature(op)) return false;
    uint256 hash = TokenOperationHash(op);
    if (!m_seen_ops.insert(hash).second) return false;
    // execute the operation without side effects such as fees or broadcast
    ...
    if (ok) m_history[op.token].push_back(op);
    return ok;
}
```

This means that replaying an operation from a block does not attempt to pay the
governance fee or record an additional transaction. The transaction that carried
the original `OP_RETURN` already paid any required fee when it was mined, so no
new wallet activity is triggered during replay.

## Wallet interaction in `ApplyOperation`

`ApplyOperation` is used when a token operation is generated locally or received
from a peer. The `wallet_name` argument allows the function to charge the
governance fee from the originating wallet. If the named wallet is not present
on the receiving node, `SendGovernanceFee` fails gracefully and no transaction is
created:

```cpp
bool TokenLedger::SendGovernanceFee(const std::string& wallet, CAmount fee) {
    std::shared_ptr<CWallet> from = GetWallet(wallet);
    if (!from) {
        LogPrintf("❌ Source wallet not found: %s\n", wallet);
        return false; // no fee transaction attempted
    }
    ...
}
```

As a result, replaying a `TOKENTX` received over the network does not lead to a
second on-chain transaction. If the wallet specified in `wallet_name` does not
exist locally (which is common when just relaying peer messages), the node simply
applies the operation to its ledger and moves on.
