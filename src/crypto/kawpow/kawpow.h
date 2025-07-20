#ifndef BITCOIN_CRYPTO_KAWPOW_H
#define BITCOIN_CRYPTO_KAWPOW_H

#include <stdint.h>
#include "uint256.h"
#include <primitives/block.h>

namespace kawpow {

// Verify the PoW hash for a given block header hash
bool verify(const uint256& headerHash,
            const uint256& mixHash,
            uint64_t nonce,
            int height);

} // namespace kawpow

uint256 GetKAWPOWHash(const CBlock& block, int height);

#endif // BITCOIN_CRYPTO_KAWPOW_H
