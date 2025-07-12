// Copyright (c) 2009-2010 Satoshi Nakamoto
// Copyright (c) 2009-2020 The Interchained Core developers
// Distributed under the MIT software license, see the accompanying
// file COPYING or http://www.opensource.org/licenses/mit-license.php.

#include <hash.h>            // For CHashWriter
#include <key.h>             // For CKey
#include <key_io.h>          // For DecodeDestination()
#include <pubkey.h>          // For CPubKey
#include <script/standard.h> // For CTxDestination, IsValidDestination(), PKHash
#include <serialize.h>       // For SER_GETHASH
#include <util/message.h>
#include <util/strencodings.h> // For DecodeBase64()
#include <logging.h>   
#include <string>
#include <vector>

/**
 * Text used to signify that a signed message follows and to prevent
 * inadvertently signing a transaction.
 */
const std::string MESSAGE_MAGIC = "Interchained Signed Message:\n";

MessageVerificationResult MessageVerify(
    const std::string& address,
    const std::string& signature,
    const std::string& message)
{
    CTxDestination destination = DecodeDestination(address);
    if (!IsValidDestination(destination)) {
        LogPrintf("❌ MessageVerify: Invalid address '%s'\n", address);
        return MessageVerificationResult::ERR_INVALID_ADDRESS;
    }

    if (!boost::get<PKHash>(&destination) && !boost::get<WitnessV0KeyHash>(&destination)) {
        LogPrintf("❌ MessageVerify: Unsupported address type for '%s'\n", address);
        return MessageVerificationResult::ERR_ADDRESS_NO_KEY;
    }

    std::vector<unsigned char> signature_bytes;
    if (!DecodeBase64ToBytes(signature, signature_bytes)) {
        LogPrintf("❌ MessageVerify: Failed to decode base64 signature for '%s'\n", address);
        return MessageVerificationResult::ERR_MALFORMED_SIGNATURE;
    }
    LogPrintf("🔏 MessageVerify: Signature (base64): %s\n", signature);
    LogPrintf("🔏 MessageVerify: Digest being signed: %s\n", MessageHash(message).ToString());

    uint256 digest = MessageHash(message);
    LogPrintf("🔍 MessageVerify: Digest for verification: %s\n", digest.ToString());

    CPubKey pubkey;
    if (!pubkey.RecoverCompact(digest, signature_bytes)) {
        LogPrintf("❌ MessageVerify: Failed to recover public key from signature\n");
        return MessageVerificationResult::ERR_PUBKEY_NOT_RECOVERED;
    }

    if (auto pkhash = boost::get<PKHash>(&destination)) {
        if (PKHash(pubkey) != *pkhash) {
            LogPrintf("❌ MessageVerify: Recovered pubkey does not match PKHash for '%s'\n", address);
            return MessageVerificationResult::ERR_NOT_SIGNED;
        }
    } else if (auto wpkh = boost::get<WitnessV0KeyHash>(&destination)) {
        if (WitnessV0KeyHash(pubkey) != *wpkh) {
            LogPrintf("❌ MessageVerify: Recovered pubkey does not match WPKH for '%s'\n", address);
            return MessageVerificationResult::ERR_NOT_SIGNED;
        }
    } else {
        LogPrintf("❌ MessageVerify: Address type did not resolve as expected\n");
        return MessageVerificationResult::ERR_ADDRESS_NO_KEY;
    }

    LogPrintf("✅ MessageVerify: Signature is valid for '%s'\n", address);
    return MessageVerificationResult::OK;
}

bool MessageSign(
    const CKey& privkey,
    const std::string& message,
    std::string& signature)
{
    std::vector<unsigned char> signature_bytes;

    if (!privkey.SignCompact(MessageHash(message), signature_bytes)) {
        return false;
    }

    signature = EncodeBase64(signature_bytes);
    
    LogPrintf("🔏 MessageSign: Signature (base64): %s\n", signature);
    LogPrintf("🔏 MessageSign: Digest being signed: %s\n", MessageHash(message).ToString());

    return true;
}

uint256 MessageHash(const std::string& message)
{
    CHashWriter hasher(SER_GETHASH, 0);
    hasher << MESSAGE_MAGIC << message;

    return hasher.GetHash();
}

std::string SigningResultString(const SigningResult res)
{
    switch (res) {
        case SigningResult::OK:
            return "No error";
        case SigningResult::PRIVATE_KEY_NOT_AVAILABLE:
            return "Private key not available";
        case SigningResult::SIGNING_FAILED:
            return "Sign failed";
        // no default case, so the compiler can warn about missing cases
    }
    assert(false);
}
