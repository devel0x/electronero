# Token Operations Signing

Token RPC commands construct a `TokenOperation` that is signed by the wallet
before being submitted to the ledger. To prevent tampering, the signature must
cover every field in the operation. The helper `BuildTokenMsg()` formats the
operation into a deterministic string used for signing and verification.

During verification, `TokenLedger::VerifySignature` reconstructs the same string
and checks the signature with `MessageVerify`. It also ensures the signer
matches the address expected for the operation (the `from` field or `spender` in
`TRANSFERFROM`). If any field is altered or the signer does not match, the
operation is rejected.
